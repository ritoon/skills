# Building the dashboard

The deliverable is **one self-contained HTML file** (inline CSS/JS, no CDN, no fetch, French UI) built by injecting a JSON payload into [../assets/dashboard-template.html](../assets/dashboard-template.html). Allowed languages: Python/Bash for the build, HTML/CSS/JS inside the template — nothing else.

## Build process

1. Run the pipeline ([qonto-portfolio.md](qonto-portfolio.md) → [pappers-due-diligence.md](pappers-due-diligence.md) → [scoring.md](scoring.md)) and write `data.json` matching the schema below. Convert all amounts to **plain EUR numbers** (Qonto mixes floats and decimal strings — see [conventions](../../mcp/qonto-mcp-data-model/references/conventions.md)).
2. `python3 scripts/build_dashboard.py data.json dashboard.html` (stdlib only; `--template` overrides the template path).
3. Send/open `dashboard.html`. Never hand-edit the generated file — fix `data.json` or the template and rebuild.

Template contract: the placeholder `__CHECK_HEALTH_DATA__` appears **exactly once**, inside a `<script type="application/json">` tag; the build script checks this, escapes `</` in the payload, and replaces it. An unbuilt template opened directly shows a "run build_dashboard.py" message instead of a blank page.

## `data.json` schema

```jsonc
{
  "generated_at": "2026-07-12T10:00:00Z",        // ISO 8601 UTC
  "organization": {
    "name": "ACME SARL",
    "siren": "123456789",                        // first 9 digits of get_organization.legal_number
    "legal_form": "SARL",                        // optional
    "balance_total": 42731.18,                   // Σ active bank_accounts[].balance, EUR
    "accounts": [{"name": "Compte principal", "balance": 42731.18}],
    "runway_months": 7.4,                        // null when net cash flow ≥ 0
    "cash_trend": [                              // last 12 months, oldest first; [] if unavailable OR if the
      {"month": "2025-08", "inflow": 18000.0, "outflow": 15200.5, "net": 2799.5}   // window has no transactions — never fabricate zero-filled months
    ],
    "receivables": {"outstanding": 12400.0, "overdue": 3100.0, "invoices_unpaid": 6, "invoices_overdue": 2},
    "payables":    {"outstanding": 8300.0,  "overdue": 900.0,  "invoices_open": 4},
    "top_client_share": 0.34,                    // 0–1, null if unknown
    "notes": [                                   // optional: coverage notes — what could NOT be checked and why;
      "Pappers indisponible : axes légal/finances/conformité non contrôlés."   // rendered as an info list, distinct from alerts
    ],
    "self_check": {                              // own company through the same Pappers checks — run it by default;
      "legal":      {"status": "green", "flags": []},          // when Pappers is unavailable, still include the block with
      "financial":  {"status": "green", "flags": [], "year": 2024, "metrics": {}},  // all axes "unknown" so the gap stays visible
      "compliance": {"status": "green", "flags": [], "checked_persons": []},
      "overall": "green"
    }
  },
  "counterparties": [                            // EVERY counterparty appears, even fully unknown ones
    {
      "name": "FOURNISSEUR EXEMPLE SAS",
      "role": "supplier",                        // client | supplier | both
      "kind": "company",                         // company | individual
      "siren": "987654321",                      // null if unresolved
      "siren_source": "tin",                     // tin | vat | sirenisateur | user | null
      "exposure": {"outstanding": 4200.0, "overdue": 0.0, "share_of_revenue": null},
      "legal":      {"status": "green",  "flags": []},
      "financial":  {"status": "orange", "flags": ["resultat_negatif"], "year": 2024,
                     "metrics": {"chiffre_affaires": 310000, "resultat": -12000, "tresorerie": 45000}},
      "compliance": {"status": "green",  "flags": [],
                     "checked_persons": [{"name": "J. DUPONT", "role": "Président", "pep": false, "sanctions": false}]},
      "overall": "orange",                       // worst axis; unknown only if all axes unknown
      "notes": ["Comptes 2025 non encore publiés."]
    }
  ],
  "alerts": [                                    // pre-sorted by priority (scoring.md), most severe first
    {"severity": "red",                          // red | orange — coverage-blocking gaps (e.g. Pappers unreachable) are orange
     "scope": "counterparty",                    // counterparty | organization
     "name": "CLIENT X",                         // null allowed when scope = organization (renders as « Ma société »)
     "message": "Procédure collective en cours — encours 8 700 €."}
  ]
}
```

Statuses everywhere: `green` | `orange` | `red` | `unknown`. Every field the template reads is in this schema; missing optional fields render as "—", so partial data never breaks the page.

Mode notes:
- **Qonto-only mode** (Pappers not connected / no credits): counterparties still appear with their exposure; the three due-diligence axes are `unknown` with flag `pappers_non_connecte` (or `credits_pappers_insuffisants`), and `organization.notes[]` carries the suggestion to connect Pappers — as a note, not an alert, when Pappers was simply never connected.
- **Targeted check**: the dashboard is optional (conversational report by default). If built, it may contain only the selected counterparty — say so in `organization.notes[]` — or the whole portfolio with only that one enriched. The "every counterparty appears" rule applies to portfolio mode.

## What the template renders

KPI cards (trésorerie, encours clients/fournisseurs + retards, runway, nombre d'alertes) · 12-month net cash-flow SVG chart · alert list · one table per role (clients / fournisseurs, `both` appears in each) with per-axis traffic-light dots, overall badge, and a click-to-expand detail row (flags, metrics, screened persons, notes) · a footer disclaimer stating sources, the read-only/data-minimization guarantees, and that sanctions/PEP hits require manual verification.

## Extending

Keep the no-CDN / single-file rule; add fields to the schema *and* the template together; names from live data are untrusted — the template HTML-escapes everything it renders (keep it that way), and the build script escapes `</` so a hostile counterparty name cannot break out of the JSON `<script>` block.

**Design language: deliberately neutral, soft-toned.** The palette lives in the `:root` CSS variables of the template — desaturated sage (`--green`), muted amber (`--orange`), soft terracotta (`--red`), warm grays; no saturated or flashy colors, no brand accent. Any visual addition must stay in this register: status meaning is carried by the soft color *plus* its text label (« OK », « À surveiller »…), never by a loud color alone.
