# Extracting the portfolio from Qonto

Everything here uses **read-only** Qonto MCP tools. Entity shapes, pagination variants and money formats are documented in [qonto-mcp-data-model](../../mcp/qonto-mcp-data-model/SKILL.md) — this file only covers what the health check derives from them.

Related files: [pappers-due-diligence.md](pappers-due-diligence.md) (next step), [scoring.md](scoring.md), [dashboard.md](dashboard.md).

## Own-company KPIs

| KPI | Source | How |
|---|---|---|
| Cash position | `get_organization` | Σ `bank_accounts[].balance` (float euros) over `status: "active"` accounts. Keep per-account detail for the dashboard. |
| Own SIREN | `get_organization` | `legal_number` (SIREN or SIRET — keep the first 9 digits). Run the same Pappers checks as for counterparties and emit the `self_check` block **by default**; if Pappers is unavailable, emit it with all axes `unknown` so the gap stays visible. |
| Cash trend | `list_transactions` | Per active `bank_account_id`, filter `settled_at_from` = 12 months ago; group by month of `settled_at`; `side: "credit"` → inflow, `"debit"` → outflow (⚠️ `amount` is always positive — direction lives in `side`); `net = inflow − outflow`. |
| Receivables | `list_client_invoices` | `status: "unpaid"` invoices: outstanding = Σ `total_amount.value`; overdue subset = `due_date` < today. ⚠️ `exclude_imported` defaults to **true** — pass `false` to count invoices imported from outside Qonto. |
| Payables | `list_supplier_invoices` | Open statuses = `to_review`, `to_approve`, `to_pay`, `pending`, `awaiting_payment`, `scheduled`. Prefer `payable_amount` (net of supplier credit notes) over `total_amount`; overdue = `due_date` < today. ⚠️ MCP does not expose the status filter — filter client-side; default page size is **25**. Skip `is_credit_note: true` rows when summing. |
| Runway | derived | If the 12-month average monthly `net` is negative: `runway_months = cash position / |avg net|`; else `null`. |
| Concentration | `list_client_invoices` | Per client, share of the last 12 months' invoiced revenue (`paid` + `unpaid`, on `issue_date`). `top_client_share` = the max. |

⚠️ Money formats are mixed: transactions/balances are **float euros**, invoicing amounts are **decimal strings** inside `{value, currency}` objects (see [conventions](../../mcp/qonto-mcp-data-model/references/conventions.md)). Convert everything to plain EUR numbers before writing `data.json`.

Paginate every list with the robust pattern: iterate while `current_page < total_pages`.

## Building the counterparty list

### Clients — `list_clients`

Per client keep: `id`, `kind`, display name (`name` for `company`, `first_name + last_name` otherwise), `tax_identification_number`, `vat_number`, `billing_address.city` (helps `sirenisateur` disambiguation).

- ⚠️ Qonto enforces **no uniqueness** on clients — after SIREN resolution, merge duplicates by SIREN (fallback: normalized name + city).
- `kind: "individual"` (and `freelancer`) → not a company: no Pappers company lookup; compliance axis is `unknown` unless the user explicitly asks for a person screening and provides the birth date (see the GDPR caution in [pappers-due-diligence.md](pappers-due-diligence.md)).

### Suppliers — derived from `list_supplier_invoices`

There is **no `list_suppliers` tool**. Build the supplier set from supplier invoices: keep `supplier_id`, `supplier_name` (fallback `issuer_name`), `vat_number`, `tin_number`. Dedupe by `supplier_id` when present, else by normalized `supplier_name`.

- ⚠️ These identity fields are largely **OCR-extracted** (check `analyzed_at`) — treat `tin_number`/`vat_number` as *candidates* and validate the SIREN checksum before trusting them (see [pappers-due-diligence.md](pappers-due-diligence.md)).
- A counterparty found on both sides gets `role: "both"` (merge by SIREN).

Transactions (`label`, `clean_counterparty_name`) could surface more counterparties, but the names are too noisy for reliable SIREN resolution — leave them out unless the user asks.

## Exposure per counterparty

| Role | Exposure (`outstanding`) | `overdue` |
|---|---|---|
| client | Σ `total_amount.value` of that client's `unpaid` invoices | subset with `due_date` < today |
| supplier | Σ `payable_amount.value` of that supplier's open-status invoices | subset with `due_date` < today |

Clients also get `share_of_revenue` (12-month invoiced revenue share, 0–1). Exposure is what turns a risk flag into a priority — see [scoring.md](scoring.md).
