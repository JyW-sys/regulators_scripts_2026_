# CD BCCO Regulatory Lists

Banque Centrale du Congo (BCCO) - Democratic Republic of the Congo central bank. The public register lists supervised financial institutions across 7 French-language pages on `www.bcc.cd`. Each page renders a single HTML `<table>` with columns: `DÉNOMINATION` (name), `AUTORISATION DE FONCTIONNER`, `SIÈGE SOCIAL` (head office), `PROVINCES`, `POINTS D'EXPLOITATION` (branches). The Dénomination and Siège Social cells use `rowspan`, so the scraper deduplicates by name and keeps only the first Siège Social as `Address_1` (branch agencies are ignored).

| RegCtry | RegCode | ListNr | ListName | URL |
|---------|---------|--------|----------|-----|
| CD | BCCO | 1 | List of Banks | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/banques-agreees |
| CD | BCCO | 2 | List of Microfinance Institutions | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/imf |
| CD | BCCO | 3 | List of Savings and Credit Cooperatives | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/coopec |
| CD | BCCO | 4 | List of Specialized Financial Institutions | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/ifs |
| CD | BCCO | 5 | List of Savings and Credit Banks | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/cec |
| CD | BCCO | 6 | List of Electronic Money Issuing Institutions | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/societes-financieres/ee |
| CD | BCCO | 7 | List of Other Financial Companies | https://www.bcc.cd/surveillance-des-intermediaires-financiers/intermediaires-financiers-assujettis/etablissements-de-credit/societes-financieres/au |

Notes:
- Static pages loaded with `requests.get`; no Chrome driver required.
- Only `Name` (Dénomination) and `Address_1` (Siège Social) are captured from the table; multiple-address branches under "Autres points d'exploitation" are intentionally skipped.
- Language: French. RegCtry=CD, RegCode=BCCO.
