# BR BCB Reference Data

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| BR | BCB | 1 | Conglomerados | https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento | Please select the corresponding list, choose the latest date available and click in "Baixar arquivo". |
| BR | BCB | 2 | Bancos comerciais, múltiplos e Caixa Econômica | https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento | Please select the corresponding list, choose the latest date available and click in "Baixar arquivo". |
| BR | BCB | 3 | Cooperativas de crédito | https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento | Please select the corresponding list, choose the latest date available and click in "Baixar arquivo". |
| BR | BCB | 4 | Bancos de Investimento, Bancos de Desenvolvimento, Sociedades Corretoras de TVM e Câmbio, Sociedades Distribuidoras de TVM, Sociedades de Crédito, Financiamento e Investimento, Sociedades de Crédito Imobiliário e APE, Sociedades de Arrendamento Mercantil, Sociedades de Investimento, Sociedades de Crédito ao Microempreendedor, Agências de Fomento, Companhias Hipotecárias e Instituições de Pagamento | https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento | Please select the corresponding list, choose the latest date available and click in "Baixar arquivo". |
| BR | BCB | 5 | Administradoras de consórcios | https://www.bcb.gov.br/estabilidadefinanceira/relacao_instituicoes_funcionamento | Please select the corresponding list, choose the latest date available and click in "Baixar arquivo". |
| BR | BCB | 8 | Supervised institutions - Foreign Institutions in Brazil | https://www.bcb.gov.br/en/statistics/evolutionmonthnfs?ano=2026 | BR BCB 8 is chart 10 - Representative of Foreign institutions in the Country |

## Scraper

`BR BCB_v_1_7.py` — current version. Run with the global Python (`python3 "BR BCB_v_1_7.py"`).
Output: `BR BCB SQL Ready <timestamp>.xlsx`, sheet `SQL Ready`, written next to the script.
`tempfolder/` is recreated at start and deleted on success — nothing is committed.

### How each list is reached

**Lists 1-5** live on one Angular page. There is no REST API behind it: the option data is
embedded in the page and the ZIP URL is built client-side on click, so a real browser is required.
The page carries exactly five `<ng-select>` widgets and five "Baixar arquivo" buttons, in ListNr
order (`NGSELECT_ORDER`). For each one the scraper opens the dropdown, takes option index 0
(the dropdown is sorted newest-first), and clicks the matching download button.

Two things the scraper depends on, both of which broke earlier versions:
- the dropdown only opens when the inner `.ng-select-container` is clicked, not the `<ng-select>` element;
- the widget/button counts are asserted to be 5 — if the page layout changes the run fails loudly
  instead of silently downloading the wrong month.

**List 8** is chart 10 of the monthly "Charts in spreadsheets" ZIP. The scraper reads the statistics
page to discover the newest `z<YYYYMM>.zip`, then downloads it with plain `requests`.
This list is published on a slower cadence than lists 1-5, so its `ListValidityDate` normally
lags by one month. That is expected, not a defect.

### Workbook parsing

All five institution workbooks share a shape: ~9 banner rows, a header row, the data, then a
`FONTE: INSTITUIÇÕES FINANCEIRAS...` footnote. The header row is found at runtime (first row with
≥3 non-null cells) rather than hard-coded, and the footnote plus blank rows are dropped.

Header names are matched through `norm()` (NFKD accent-strip + whitespace-collapse + uppercase) and
compared **exactly**, which is what keeps `MUNICIPIO` from colliding with `MUNICIPIO IBGE`. This also
absorbs the inconsistencies between files — `FONE` vs `TELEFONE`, `SÍTIO` vs `SITIO`,
`MUNICIPIO` vs `MUNICÍPIO` vs `CIDADE` — without per-list hard-coding.

`ListValidityDate` is read from the `Posição: 30.6.2026` banner (d.m.Y). Chart 10 uses
`Position: 05.31.2026` (m.d.Y); `parse_position_date` disambiguates on which component exceeds 12.

### Field mapping

Common to lists 2-5: `Address_1` = ENDEREÇO, `Address_2` = COMPLEMENTO + BAIRRO + UF,
`City` = MUNICIPIO/MUNICÍPIO/CIDADE, `Zip` = CEP (formatted `NNNNN-NNN`),
`InternalID_2` = MUNICIPIO IBGE (`InternalID_2_type` = `IBGE Municipality Code`),
`Phone` = DDD + FONE/TELEFONE recombined (`(11) 40044224`, or `0800 …` for non-geographic prefixes),
`Website` = SÍTIO NA INTERNET, `Email` = E-MAIL, `EntryType` = `Head Office` (the source sheets are
titled "SEDES DE …"), `Cntry` = `BR`.

Per-list specifics:

| ListNr | Name | CoType | License_Type | Name - Mother Company | Notes |
|---|---|---|---|---|---|
| 1 | NOME DO PARTICIPANTE | CLASSE DO CONGLOMERADO | TIPO PARTICIPAÇÃO | NOME DO CONGLOMERADO | `RegulationDate` = DATA INÍCIO; `Address_2` = UF (the file carries no street address) |
| 2 | NOME INSTITUIÇÃO | SEGMENTO | `Carteira Comercial: <CART COMERCIAL>` | — | |
| 3 | NOME INSTITUIÇÃO | CLASSE | CATEG COOP SING \| CRITÉRIO DE ASSOCIAÇÃO | FILIAÇÃO (central body) | |
| 4 | NOME INSTITUIÇÃO | SEGMENTO | — | — | |
| 5 | NOME INSTITUIÇÃO | `Administradora de Consórcio` (constant) | — | — | source has no segment column |
| 8 | Foreign Institution | Tipo de Pessoa (Jurídica/Física) | `Representative Office` | — | `EntryType` = `Representative: <Name of Representative>`; `Cntry` = ISO-2 of Country of Origin; address from the *Principal* columns; `City` = Municipality |

`InternalID_1` is the CNPJ. BCB publishes only the **8-digit CNPJ root**, dotted on lists 2-5
(`00.000.000`) and bare on lists 1 and 8 (`03516449`); `format_cnpj()` strips the punctuation so the
value is comparable across all six lists. On list 8 `InternalID_1_type` switches to `CPF` when
Tipo de Pessoa is *Física*.

`Typology` = the ListName. `RegulationType` = `Regulated` for every row.
`ListLanguage` = `PT` for lists 1-5, `EN` for list 8.
`ListLabel` = 1 for lists 1, 2, 3, 4 and 8 (banks); **4** for list 5, since consórcio administrators
are neither banks nor insurers.

### Known-good row counts (position 06/2026, list 8 at 05/2026)

| ListNr | Rows |
|---|---|
| 1 | 1091 |
| 2 | 154 |
| 3 | 756 |
| 4 | 714 |
| 5 | 131 |
| 8 | 48 |
| **Total** | **2894** |

### Expected gaps — do not treat as scrape failures

- List 1 has no street address, city or zip; the conglomerate file only carries UF. 48 of its rows
  have no CNPJ because they are offshore funds with no Brazilian registration.
- List 1 and list 8 contain legitimate repeated names: a fund can participate in two conglomerates,
  and one foreign institution can appoint several representatives. Rows differ by
  `Name - Mother Company` / `EntryType`, so they must **not** be deduplicated.
- Chart 10 publishes no email or website, and `TEL_COM` is filled for roughly half the rows.
