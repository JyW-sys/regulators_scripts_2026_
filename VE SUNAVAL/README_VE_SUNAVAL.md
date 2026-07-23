# VE SUNAVAL — Superintendencia Nacional de Valores (Venezuela)

Jira: [DECD-4399](https://moodysdatapipeline.atlassian.net/browse/DECD-4399) (parent: DECD-3438)

## Regulatory Lists

| RegCtry | RegCode  | ListNr | ListName (EN)                                     | URL                                                              | Comments                                       |
|---------|----------|--------|---------------------------------------------------|------------------------------------------------------------------|------------------------------------------------|
| VE      | SUNAVAL  | 1      | Investment Advisors (Legal Persons)               | https://www.sunaval.gob.ve/asesores-de-inversion-jur/            | Table populated via XHR; address via row button |
| VE      | SUNAVAL  | 2      | Investment Brokerage Companies                    | https://www.sunaval.gob.ve/sociedades-de-corretaje-de-inversion/ | Same pattern                                   |
| VE      | SUNAVAL  | 3      | Agricultural Products Brokerage Houses            | https://www.sunaval.gob.ve/casas-de-bolsas-de-productos-agricolas/ | Same pattern                                   |
| VE      | SUNAVAL  | 4      | Mutual Funds                                      | https://www.sunaval.gob.ve/fondos-mutuales/                      | Same pattern                                   |
| VE      | SUNAVAL  | 5      | Management Companies (Sociedades Administradoras) | https://www.sunaval.gob.ve/sociedades-administradoras/           | Same pattern                                   |
| VE      | SUNAVAL  | 6      | Risk Rating Companies                             | https://www.sunaval.gob.ve/sociedades-calificadoras-de-riesgos/  | Same pattern                                   |
| VE      | SUNAVAL  | 7      | Transfer Agents (Agente de Traspasos)             | https://www.sunaval.gob.ve/agente-de-traspasos/                  | Same pattern                                   |
| VE      | SUNAVAL  | 8      | Securitization Companies                          | https://www.sunaval.gob.ve/sociedad-titularizadora/              | Same pattern                                   |
| VE      | SUNAVAL  | 9      | Other Entities (Otro Ente)                        | https://www.sunaval.gob.ve/otro-ente/                            | Same pattern                                   |

## Site behaviour

- The portal is developed by SUNAVAL's IT office (PHP backend; the static HTML returns an empty `<table>`).
- Rows are filled in via an **XHR** call after the page loads.
- Each row has a **"Ficha"** action button; clicking it reveals the entity's address details (typically `Dirección`, `Teléfono`, sometimes `Correo`, etc.) in a modal/panel.
- Tables are in **Spanish**; column headers like `RIF`, `Descripción`, `Estado`, `Ficha`.

## Two unknowns to capture before first real run

Open one list URL in Chrome and use **DevTools → Network → Fetch/XHR**:

1. **XHR endpoint + payload** of the call that populates the table.
   - If it returns JSON, the scraper can hit it directly via `requests` and skip Selenium for the list step.
   - Set `XHR_ENDPOINT` and `XHR_PAYLOADS` in the notebook (currently `None`).
2. **Detail-button selector** (the "Ficha" button) and the **detail-panel selector** that appears after clicking.
   - Set `DETAIL_BUTTON_SELECTOR` and `DETAIL_PANEL_SELECTOR` in the notebook.
   - Defaults are guesses (`td:last-child a, td:last-child button` and `.modal.show .modal-body, .ficha-detalle`).

Once those are set, the loop already handles: scroll-into-view, click (with JS-click fallback), wait for the panel, parse Spanish-labelled lines, close, and pad the sqldict row.

## Output

`VE SUNAVAL SQL Ready <timestamp>.xlsx`, sheet **`SQL Ready`**, written into the regulator folder.

Standard `sqldict` schema; Spanish-language source. After the first successful run translate `Name` / `Address_1` / `City` to English in the target columns (see the `regulator-translate` skill).
