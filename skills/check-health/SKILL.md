---
name: check-health
description: Build a company & counterparty health dashboard from a Qonto business account, optionally enriched with Pappers (pappers.fr) due diligence. Use when the user wants their company's financial health KPIs, a risk view of their clients/suppliers, or a compliance check (legal status, financials, sanctions & PEP screening) on the whole portfolio or on one selected client/supplier. Works with Qonto alone — Pappers is detected and suggested, never required.
---

# Check Health — Qonto × Pappers counterparty dashboard

Pulls the portfolio (clients, suppliers, cash position) from the **Qonto MCP server**, and — **when the Pappers MCP server is connected** — resolves each French counterparty to its **SIREN** and runs due-diligence checks through Pappers (legal status, published accounts, sanctions/PEP on directors). Scores everything and renders one **self-contained HTML dashboard** (no CDN, no external requests). Pappers is an optional enrichment: without it the skill still delivers the full Qonto financial dashboard. Allowed implementation languages: **Python, Bash, HTML, CSS, JS only**.

## Pipeline

```
Qonto MCP (read-only)                          Pappers MCP (OPTIONAL — mode-dependent)
─────────────────────                          ────────────────────────────────────────
get_organization ──────── own KPIs ─────┐
list_transactions ─────── cash trend ───┤
list_client_invoices ──── receivables ──┤
list_supplier_invoices ── payables ─────┤
      │                                 │
list_clients ────────┐                  │
supplier_name/TIN ───┴── counterparties ── SIREN resolution ──┬─ informations-entreprise   (legal)
     (from supplier invoices)                                 ├─ comptes-entreprise        (financials)
                                                              └─ recherche-dirigeants
                                                                 + conformite-personne-physique (PEP/sanctions)
                                        │
                          scoring  →  data.json  →  scripts/build_dashboard.py  →  dashboard.html
```

## The 8 rules that prevent most mistakes

1. **A health check is read-only.** Call only Qonto *read* tools (`get_*`, `list_*`). Never trigger writes as part of a check — and remember no Qonto MCP tool can move money anyway (see [qonto-mcp-data-model](../mcp/qonto-mcp-data-model/SKILL.md), rule 4).
2. **Pappers is an enrichment, never a dependency.** Detect its availability *before* promising due diligence (step 0 in [references/pappers-due-diligence.md](references/pappers-due-diligence.md)): not connected → run the Qonto-only mode, set the due-diligence axes to `unknown`, and **suggest connecting the Pappers connector**; connected but out of credits → same, with the credits flag. A missing Pappers must never fail or block the run.
3. **SIREN is the only join key.** Every Pappers detail tool takes a 9-digit SIREN. Resolve it from Qonto fields first (`tax_identification_number`, then FR `vat_number`), `sirenisateur` only as fallback — and never match companies by name alone. See [references/pappers-due-diligence.md](references/pappers-due-diligence.md).
4. **Data minimization toward Pappers.** Send only company name / SIREN / city. Never forward IBANs, emails, amounts, or any Qonto financial data to Pappers tools.
5. ⚠️ **`scoring_financier` / `scoring_non_financier` (Pappers `informations-entreprise`) consume paid credits.** Never request them without the user's explicit go-ahead — this skill's own scoring ([references/scoring.md](references/scoring.md)) does not need them.
6. **Absence of data ≠ risk.** Unpublished accounts, non-French companies, `individual` clients, Pappers not connected → status `unknown` (gray), never red. Say what could not be checked.
7. **Perimeter: Pappers covers French companies.** Foreign counterparties get `unknown` with a note. Never run person screening (`conformite-personne-physique`) on the user's *individual* clients without their explicit consent — directors of company counterparties (public registry data) are fine.
8. **The dashboard is one self-contained HTML file.** Inline CSS/JS, no CDN, no fetch. Build it by injecting `data.json` into the template via `scripts/build_dashboard.py` — never hand-edit generated output.

## Modes

| Mode | When | Pappers calls |
|---|---|---|
| **Qonto-only dashboard** | Pappers not connected or out of credits, or the user only wants the financial view | none — due-diligence axes `unknown` (flag `pappers_non_connecte`), connector suggested in the coverage notes |
| **Portfolio check** (default) | Pappers available and the user wants the health check | full stack per counterparty; volume strategy for large portfolios |
| **Targeted check** | the user names one client or supplier (*"vérifie le client X"*) | full stack + optional deep dives on that single company; conversational report by default, dashboard only on request |

## Reference files

| File | Read it when working on |
|---|---|
| [references/qonto-portfolio.md](references/qonto-portfolio.md) | Extracting own-company KPIs (cash, receivables, payables, concentration) and the client/supplier list from Qonto; exposure computation; amount-format traps |
| [references/pappers-due-diligence.md](references/pappers-due-diligence.md) | SIREN resolution order, the 3 checks (legal / financial / persons), Pappers tool parameters & `return_fields`, paid-field warning, GDPR & homonym cautions, volume strategy |
| [references/scoring.md](references/scoring.md) | Traffic-light rules per axis, overall status, exposure-weighted alert priority, own-company thresholds (runway, overdue share, concentration) |
| [references/dashboard.md](references/dashboard.md) | The `data.json` schema (contract with the template), build process, extension rules |

Companion assets: [assets/dashboard-template.html](assets/dashboard-template.html) (the template) and [scripts/build_dashboard.py](scripts/build_dashboard.py) (stdlib-only injector).

## Typical run

0. **Detect Pappers & pick the mode** (rule 2, step 0 of [references/pappers-due-diligence.md](references/pappers-due-diligence.md)).
1. **Qonto sweep** → `get_organization` (balances, own SIREN via `legal_number`), `list_transactions` (12-month cash trend), `list_client_invoices` + `list_supplier_invoices` (receivables/payables), `list_clients` (+ supplier names from supplier invoices) → counterparty list with per-counterparty exposure.
2. **SIREN resolution** for each company counterparty (rule 3). *(Pappers modes only.)*
3. **Pappers checks** per resolved SIREN → `informations-entreprise` (minimal `return_fields`), `comptes-entreprise`, then `recherche-dirigeants` + `conformite-personne-physique` per active director. Portfolios > ~20 counterparties: prioritize by exposure and tell the user what was skipped. *(Skipped entirely in Qonto-only mode.)*
4. **Score** each counterparty (green/orange/red/unknown per axis, worst-of overall) and the own company (runway, overdue share, top-client share).
5. **Render**: write `data.json`, run `python3 scripts/build_dashboard.py data.json dashboard.html`, hand the file to the user.

For a **targeted check** ("vérifie le client X"), skip the sweep: locate that one counterparty in Qonto (for identifiers and exposure), then follow the targeted-check flow in [references/pappers-due-diligence.md](references/pappers-due-diligence.md).

## Runtime environments

The skill runs both in **Claude Code** (installed as a project skill; MCP tool schemas may be deferred — load them via ToolSearch) and in the **Claude apps / claude.ai** (uploaded as a skill; Qonto and Pappers arrive as *connectors*). Tool naming differs per platform (`mcp__claude_ai_Pappers__…`, `Pappers:…`, …) — identify the servers by the "Qonto"/"Pappers" name in available tools, not by an exact prefix, and apply rule 2 when Pappers is absent.

Related skill: [qonto-mcp-data-model](../mcp/qonto-mcp-data-model/SKILL.md) — when available (same repo), load it for Qonto entity shapes, pagination variants, and money formats before touching any Qonto tool. When this skill is deployed standalone (e.g. uploaded to the Claude apps), those cross-repo links are absent — the essentials are restated in [references/qonto-portfolio.md](references/qonto-portfolio.md).
