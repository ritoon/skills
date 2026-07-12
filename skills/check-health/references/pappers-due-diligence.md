# Due diligence via Pappers

Pappers (pappers.fr) exposes the French company registry, published accounts, directors/beneficial owners, and sanctions/PEP screening. Tool names below are the short forms; on the server they are prefixed (e.g. `mcp__claude_ai_Pappers__informations-entreprise`).

Accuracy note: parameter names and `return_fields` enum values below are **verbatim from the MCP tool schemas (July 2026)**; response shapes were not exhaustively captured — trust live tool output, and never invent `return_fields` values (the tools reject them).

Related files: [qonto-portfolio.md](qonto-portfolio.md) (where the counterparty list comes from), [scoring.md](scoring.md) (how results become statuses).

## Step 0 — availability check (Pappers is OPTIONAL)

Run this before promising any due diligence. The skill must never fail because Pappers is absent (SKILL rule 2):

1. **Look for Pappers tools among the tools available in the session** — match on the server name ("Pappers"/"pappers") rather than an exact prefix, since naming differs per platform. In Claude Code, tools may be *deferred*: search the deferred-tool list (e.g. ToolSearch query `pappers`) before concluding absence.
2. **Not connected** → Qonto-only mode: all due-diligence axes `unknown` with flag `pappers_non_connecte`, an `organization.notes[]` entry saying due diligence was not run, and a **suggestion to the user** (in conversation and in the notes, *not* as a red/orange alert): connect the Pappers connector — in the Claude apps via *Settings → Connectors*, in Claude Code via the claude.ai Pappers connector or an MCP server entry — then rerun the check.
3. **Connected but out of credits** → same degradation with flag `credits_pappers_insuffisants`; see the ⚠️ in the cost section below.
4. **Connected with credits** → portfolio or targeted mode, sections below.

## Targeted check — one counterparty selected by the user

When the user names a single client or supplier (*"vérifie le client X"*, *"fais la due diligence de Y"*):

1. **Locate it in Qonto** (`list_clients(filter: {name: …})`, or the supplier set from `list_supplier_invoices`) to pull identifiers and exposure. A company absent from Qonto is fine too — run a pure Pappers lookup and say the exposure is unknown.
2. **Resolve the SIREN** (order below). If it cannot be resolved confidently, **ask the user** for the SIREN/SIRET or the exact legal name + city rather than picking among ambiguous `sirenisateur` candidates.
3. **Run the full stack** (checks 1–3). On a single company the deep dives are cheap — offer `recherche-decisions-justice` and `cartographie-entreprise` proactively.
4. **Output**: a conversational summary by default (per-axis status, flags, what was and wasn't checkable); build the dashboard (with just this counterparty, or the whole portfolio with only it enriched) only if the user asks for the file. See [dashboard.md](dashboard.md).

## Pappers tool map (the subset this skill uses)

| Tool | Key params | Used for |
|---|---|---|
| `sirenisateur` | `country_code` (required, `"FR"`), `company_name` (required), `company_city?`, `company_postal_code?` | Name → SIREN fallback (returns `company_number` = SIREN) |
| `informations-entreprise` | `siren` (9 chars, required), `return_fields?` | Check 1 — legal status & identity |
| `comptes-entreprise` | `siren` (required), `annee?` (`"2024"` or `"2022,2023,2024"`), `return_fields?` | Check 2 — published accounts & ratios |
| `recherche-dirigeants` | `siren`, `return_fields?` | List directors of one company (with birth dates) |
| `conformite-personne-physique` | `nom`, `prenom`, `date_de_naissance` (all required; `AAAA-MM-JJ` or `AAAA-MM`) | Check 3 — PEP & sanctions per person |
| `recherche-decisions-justice` | `entreprise_siren`, `juridiction?` | Optional deep dive — litigation |
| `cartographie-entreprise` | `siren` | Optional deep dive — ownership/direction network |

- `recherche-entreprises` exists but **requires `return_fields`** and is meant for criteria searches, not for resolving one known company — prefer `sirenisateur`.
- `recherche-beneficiaires` is explicitly **not** for listing one company's beneficial owners — use `informations-entreprise` with `beneficiaires_effectifs` instead.

## SIREN resolution (do this before any check)

Resolution order — stop at the first hit:

```python
def siren_from_qonto(fields):
    """fields: tax_identification_number / vat_number as returned by Qonto."""
    tin = (fields.get("tax_identification_number") or fields.get("tin_number") or "").replace(" ", "")
    if tin.isdigit() and len(tin) == 9:  return tin, "tin"
    if tin.isdigit() and len(tin) == 14: return tin[:9], "tin"   # SIRET -> SIREN
    vat = (fields.get("vat_number") or "").replace(" ", "").upper()
    if vat.startswith("FR") and len(vat) == 13 and vat[4:].isdigit():
        return vat[4:], "vat"                                    # FR + 2-char key + 9-digit SIREN
    return None, None

def luhn_ok(siren):                                              # SIREN self-check
    digits = [int(c) for c in siren]
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
               for i, d in enumerate(reversed(digits))) % 10 == 0
```

3. **Fallback**: `sirenisateur(country_code: "FR", company_name, company_city)` — city from Qonto `billing_address.city` when available. Accept the result only if the returned `company_name` plausibly matches (normalize case/accents/legal-form suffixes); a common name with no city → leave `siren: null`, `siren_source: null`, add a note.

⚠️ Always run `luhn_ok` on OCR-sourced identifiers (supplier `tin_number`/`vat_number`) — a failed checksum means "unresolved", not "close enough". Record `siren_source` (`tin` | `vat` | `sirenisateur` | `user`) in `data.json` for traceability.

## Check 1 — legal status: `informations-entreprise`

Request only what the scoring needs (data minimization also applies to what you pull):

```
return_fields: ["nom_entreprise", "siren", "entreprise_cessee", "date_cessation",
                "statut_rcs", "procedure_collective_en_cours", "procedure_collective_existe",
                "procedures_collectives", "date_creation", "forme_juridique",
                "code_naf", "libelle_code_naf", "effectif", "capital",
                "sanctions", "personne_politiquement_exposee"]
```

- Map to flags per [scoring.md](scoring.md): `entreprise_cessee`, `procedure_collective_en_cours`, `statut_rcs`, company age (`date_creation`), past `procedures_collectives`; `sanctions` / `personne_politiquement_exposee` feed the compliance axis at company level.
- Sanity-check that `nom_entreprise` matches the Qonto-side name — a mismatch means the SIREN resolution went wrong; drop to `unknown` and note it.
- ⚠️ **Never add `scoring_financier` / `scoring_non_financier` to `return_fields`** — the schema itself warns they consume paid Pappers credits; only on the user's explicit, informed request.

## Check 2 — financials: `comptes-entreprise`

```
siren: …, annee: "<Y-2>,<Y-1>,<Y>",           # last 3 closed years
return_fields: ["chiffre_affaires", "resultat", "taux_croissance_chiffre_affaires",
                "tresorerie", "capacite_autofinancement", "ratio_endettement",
                "autonomie_financiere", "liquidite_generale",
                "delai_paiement_clients_jours", "delai_paiement_fournisseurs_jours"]
```

- Many French companies file accounts **confidentially or not at all** — an empty result is common and maps to financial status `unknown` with the note "comptes non publiés", never red (SKILL rule 6).
- Do not request `inclure_bilan_complet` (full fiscal bundles) for a portfolio sweep — only for a single-company deep dive.
- ⚠️ Verify the scale of ratio fields against live output before applying numeric thresholds (see the caveat in [scoring.md](scoring.md)); sign- and trend-based rules are safe regardless of scale.

## Check 3 — persons: `recherche-dirigeants` + `conformite-personne-physique`

1. `recherche-dirigeants(siren: …, return_fields: ["nom", "prenom", "date_de_naissance", "qualites", "actuel", "personne_morale"])`.
2. Keep **current** (`actuel`) physical persons; skip `personne_morale` entries and audit roles (`qualites` containing "Commissaire aux comptes").
3. For each: `conformite-personne-physique(nom, prenom, date_de_naissance)`. Birth dates in registry data are often partial (month/year) — pass `AAAA-MM` then; skip the person (and say so) if no birth date at all, since name-only screening is pure homonym noise.
4. Beneficial owners: `informations-entreprise(siren, return_fields: ["beneficiaires_effectifs"])` when the user wants owner-level screening too.

Cautions:
- **A hit is a lead, not a verdict.** Sanctions/PEP matching is name+birthdate based — homonyms happen. Report hits as "à vérifier manuellement" with the matched identity, never as established fact.
- **GDPR / person data**: directors and beneficial owners of *companies* are public registry data — fine. The user's `individual` Qonto clients are not; never screen them without explicit consent and user-provided birth data.

## Optional deep dives (on request, or on a red flag)

- `recherche-decisions-justice(entreprise_siren: …, juridiction: ["tribunaux de commerce"])` — litigation trail; widen `juridiction` only if asked.
- `cartographie-entreprise(siren)` — nodes/links of related companies & persons; useful when a counterparty belongs to a group and the user wants group-level risk.

## Volume & cost strategy

Base cost per company counterparty: 1 × `informations-entreprise` + 1 × `comptes-entreprise` (+ 1 × `recherche-dirigeants` + N × `conformite-personne-physique`). For portfolios above ~20 counterparties: run the full stack on the top of the list **sorted by exposure** ([qonto-portfolio.md](qonto-portfolio.md)), the legal check only on the rest, and state explicitly what was skipped — in `organization.notes[]` and per-counterparty `notes[]` ([dashboard.md](dashboard.md)) — silent partial coverage reads as full coverage.

⚠️ **Every Pappers MCP tool is credit-metered** (observed live, July 2026) — including `sirenisateur` and `recherche-entreprises`, not just the paid `scoring_*` fields. With an empty Pappers balance every call returns `{"error": "Vous n'avez pas de crédits suffisants pour exécuter cet outil. Commandez des crédits ici : https://moncompte.pappers.fr/credits"}`. Handle it as a **blocking coverage gap, not a risk signal**: **stop calling Pappers after the first such error** (every tool fails identically), set all Pappers axes to `unknown` with flag `credits_pappers_insuffisants`, summarize the gap in `organization.notes[]`, add an organization-scope alert (severity `orange`) telling the user to recharge, and still deliver the Qonto-only dashboard.
