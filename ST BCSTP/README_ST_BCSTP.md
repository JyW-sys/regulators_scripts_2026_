# ST BCSTP — Banco Central de São Tomé e Príncipe

- **Jira:** DECD-5814 (epic DECD-3438, Regulators 2026 – Internal Crawlers)
- **Source site:** https://www.bcstp.st
- **Language:** Portuguese (translate entity fields → English)
- **RegCtry / RegCode:** ST / BCSTP
- **RegulationType:** Regulated

## Lists (from Jira ticket)

| ListNr | ListName | URL | Notes |
|---|---|---|---|
| 1 | Bancos Comerciais (Commercial Banks) | https://www.bcstp.st/Instituicoes-Financeiras-Detalhes?cod=BAN | Click *selecionar*, then open each entity for detail |
| 2 | Empresas de Seguro (Insurance Companies) | https://www.bcstp.st/Instituicoes-Financeiras-Detalhes?cod=SEG | Click *selecionar*, then open each entity |
| 3 | Casas de Câmbio (Exchange Houses) | https://www.bcstp.st/Instituicoes-Financeiras-Detalhes?cod=CAM | Click *selecionar*, then open each entity |
| 4 | Instituições de Microfinanças (Microfinance) | https://www.bcstp.st/Instituicoes_financeiras_mais.aspx?cod=MIC | **NEW LIST** — click *selecionar*, open each entity |
| 5 | Prestadores de Serviços de Pagamento (Payment Service Providers) | https://www.bcstp.st/Instituicoes_financeiras_mais.aspx?cod=PSP | **NEW LIST** — click *selecionar*, open each entity |
| 6 | Operadores de Sistema de Pagamento (Payment System Operators) | https://www.bcstp.st/Instituicoes_financeiras_mais.aspx?cod=OSP | **NEW LIST** — click *selecionar*, open each entity |

## ListLabel convention (project rule)
1 = bank, 2 = insurance, 3 = bank & insurance, 4 = other.
→ List 1 = 1, List 2 = 2, Lists 3/4/5/6 = 4.

## Status
- [x] v1 scraper built — `ST_BCSTP_v1.py` (2026-07-01)
- [x] Validated vs live site — 15 entities (5/2/2/2/2/2), all fields match `Inst_select` + `inst_selected` endpoint

## Implementation notes (v1)
- No Selenium needed: list pages expose `<select id="Inst_select">` (option text = entity name);
  detail via `POST /I_Function.aspx/inst_selected` JSON `{"value": id}` → `.d` HTML fragment.
- Both page templates (`Instituicoes-Financeiras-Detalhes`, `Instituicoes_financeiras_mais.aspx`)
  share the same control + endpoint → one code path.
- `E-Mail` cell sometimes holds a website (no `@`) → routed to Website.
- `Data de Licença` → RegulationDate (ISO); `Tipo de Actividade` → CoType (PT→EN map, PT fallback).
- Output: `ST BCSTP SQL Ready <timestamp>.xlsx` (43-col SQL-Ready schema).

## Notes
- Two page templates: `Instituicoes-Financeiras-Detalhes` (lists 1–3) and `Instituicoes_financeiras_mais.aspx` (lists 4–6).
- Interaction: each list requires selecting from a *selecionar* control, then drilling into each entity's detail page.
