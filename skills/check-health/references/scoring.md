# Scoring — from raw checks to traffic lights

Four statuses everywhere: `green` | `orange` | `red` | `unknown`. Principles:

- **Absence of data → `unknown`, never red** (SKILL rule 6). Every non-green status must come with human-readable `flags`/`notes` — the dashboard displays them, so the user can audit each verdict.
- **Qonto-only mode** (Pappers not connected / no credits): all three due-diligence axes are `unknown` with flag `pappers_non_connecte` (or `credits_pappers_insuffisants`) on every counterparty and on the self-check — the Qonto-side KPIs and exposure still score normally.
- **Prefer sign- and trend-based rules** (robust) over absolute thresholds. ⚠️ Where a rule below depends on a ratio's numeric scale, verify the scale against live `comptes-entreprise` output first — Pappers ratio units were not captured live for this skill.
- Inputs come from [qonto-portfolio.md](qonto-portfolio.md) (exposure, own KPIs) and [pappers-due-diligence.md](pappers-due-diligence.md) (checks).

## Axis 1 — Legal (from `informations-entreprise`)

| Signal | Status | Flag to record |
|---|---|---|
| `entreprise_cessee` true | red | `entreprise_cessee` |
| `procedure_collective_en_cours` true | red | `procedure_collective_en_cours` |
| `statut_rcs` = radié | red | `radie_rcs` |
| Past `procedures_collectives` only (none in progress) | orange | `procedure_collective_passee` |
| `date_creation` < 12 months ago | orange | `jeune_entreprise` |
| None of the above | green | — |
| No SIREN resolved / foreign company / individual | unknown | `hors_perimetre` or `siren_non_resolu` |

## Axis 2 — Financial (from `comptes-entreprise`, latest year ≤ 3 years old)

| Signal | Status | Flag |
|---|---|---|
| `resultat` < 0 on the two latest published years | red | `resultat_negatif_recurrent` |
| `resultat` < 0 latest year **and** `tresorerie` < 0 | red | `perte_et_tresorerie_negative` |
| `resultat` < 0 latest year only | orange | `resultat_negatif` |
| `tresorerie` < 0 | orange | `tresorerie_negative` |
| `capacite_autofinancement` < 0 | orange | `caf_negative` |
| Sharp revenue drop (`taux_croissance_chiffre_affaires` strongly negative — ⚠️ check scale live; intent ≈ −20 % or worse) | orange | `ca_en_forte_baisse` |
| Accounts published, none of the above | green | — |
| No published accounts, or latest year > 3 years old | unknown | `comptes_non_publies` / `comptes_anciens` |

Several orange signals on the same company → escalate the axis to red (`signaux_financiers_cumules`).

## Axis 3 — Compliance (company-level fields + person screenings)

| Signal | Status | Flag |
|---|---|---|
| Sanctions hit — company `sanctions` non-empty, or any screened person with a sanctions match | red | `sanction_entreprise` / `sanction_dirigeant` |
| PEP — company `personne_politiquement_exposee` true, or a screened person flagged PEP | orange | `ppe` |
| Checks ran, no hits | green | — |
| Not checkable (no SIREN, individual, screening skipped for volume) | unknown | `non_verifie` |

Remember: a sanctions/PEP hit is a **lead to verify manually** (homonyms) — the flag text and dashboard note must say so.

## Overall status & alert priority

- `overall` = worst of the three axes (`red` > `orange` > `green`); if **all** axes are `unknown` → `unknown`. A single `unknown` axis does not drag down an otherwise green counterparty — it is surfaced as a coverage note instead.
- Alert priority = severity weight (red = 2, orange = 1) × exposure normalized over the portfolio (`outstanding` / max outstanding, floor 0.1 so zero-exposure risks still appear). Sort `alerts[]` in `data.json` by this, most severe first, and phrase each alert with the exposure: *"Procédure collective en cours — encours 8 700 €"*.
- Coverage-blocking gaps (Pappers unreachable, screening skipped for volume) are `severity: "orange"`, `scope: "organization"` — and the detail of *what* was skipped goes in `organization.notes[]`, not in more alerts.

## Own-company thresholds (Qonto-side KPIs)

| KPI | orange | red |
|---|---|---|
| `runway_months` (only when net cash flow is negative) | < 6 | < 3 |
| Overdue share of receivables (`overdue / outstanding`) | > 25 % | > 50 % |
| `top_client_share` (12-month revenue concentration) | > 30 % | > 50 % |

These feed `alerts[]` with `scope: "organization"`. The optional Pappers self-check on the user's own SIREN reuses the three axes above unchanged.
