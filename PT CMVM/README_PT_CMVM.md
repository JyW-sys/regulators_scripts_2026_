# PT CMVM

## Regulator Information

- **Country/Region Code**: PT
- **Regulator Code**: CMVM
- **Full Name**: Comissão do Mercado de Valores Mobiliários (Portuguese Securities Market Commission)
- **Website**: https://www.cmvm.pt/
- **Jira**: https://ma-datasolutions.atlassian.net/browse/PPD-14134

## Notebook

- **Current Version**: `PT_CMVM_v3.ipynb`

## List Types

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| PT | CMVM | 1 | Issuers | https://www.cmvm.pt/PInstitucional/Content?Input=EC2CC0691CC518A5DD27F600C912A72B95813803AA700D079B482F06F6A9D4D3 | Multi-tab page; iterate each tab, then paginate through every page within the tab. |
| PT | CMVM | 2 | Financial intermediaries registered with the CMVM | https://www.cmvm.pt/PInstitucional/Content?Input=5DFE7211A0E7ECF9447CFDDEB7DF36130830865865A4241BD33893ED167B3991 | Side-menu accordion with sub-sections (e.g. "Top five trading platforms and order execution quality", "Qualifying holdings in financial intermediaries"); paginate within each. |
| PT | CMVM | 3 | Management Companies | https://www.cmvm.pt/PInstitucional/Content?Input=DE69D31DE34B669FF11251BE9053B7BF8AF19CC5ECBEB434FC4E4A857452C478 | Standard paginated table. |
| PT | CMVM | 4 | Investment funds | https://www.cmvm.pt/PInstitucional/Content?Input=E53C246B2452F00BEB3AEEF67C47C69CA0E3BB26DACB718CAD315564B7A421B4 | Standard paginated table. |
| PT | CMVM | 5 | Registered crowdfunding platform managers | https://www.cmvm.pt/PInstitucional/Content?Input=185E6B62730853323BB4F2C2D727ACBA64584CC7E65E1DCDC5BDE00DA2BC7486 | Standard paginated table. |
| PT | CMVM | 6 | Financial intermediaries registered for providing investment advice | https://www.cmvm.pt/PInstitucional/Content?Input=A569E0E41AC02102EA1881F785AF55733C331047139FDB06C96372769F55084F | Standard paginated table. |
| PT | CMVM | 7 | Financial intermediaries that provide the services of investment research and financial analysis or other forms of general recommendation relating to transactions in financial instruments | https://www.cmvm.pt/PInstitucional/Content?Input=6A7A54D1B9464E33BE3EBFA4FAA15FA2F45BE9F585803D7F3EFE1995C9FAD072 | Standard paginated table. |

## Notes

- The site is built on OutSystems; element IDs are partial-match only (use `contains(@id, ...)` / `[id*=...]`).
- Pagination uses `<button class="pagination-button" aria-label="go to next page">`. The button is rendered with `disabled=""` once the last page is reached, so the script must check the disabled state or guard the click before iterating to the next page.
- Tab content lives under `[data-block="Navigation.TabsContentItem"]`; the active tab's table is the one to read.
