# DZ BAL — Bank of Algeria (Banque d'Algérie)

| Field | Value |
|---|---|
| RegCtry | DZ |
| RegCode | BAL |
| Regulator | Banque d'Algérie (Bank of Algeria) |
| Site language | French |
| Notebook | `DZ_BAL_v1.ipynb` |

## Lists

| ListNr | ListName | URL | Comments |
|---|---|---|---|
| 1 | Banques Et Etablissements Financiers | https://www.bank-of-algeria.dz/banques-et-etablissements-financiers/ | Click into each category and add all the entities to the same list. |

The parent URL above is an index of 5 sub-category pages. All entities collected across the 5 sub-pages are flattened into a **single** list (`ListName = "Banques Et Etablissements Financiers"`). Each entity's `CoType` records which sub-category it came from.

### Sub-categories walked by the notebook

| # | CoType assigned | URL |
|---|---|---|
| 1 | Commercial Bank | https://www.bank-of-algeria.dz/banques-commerciales-2/ |
| 2 | Financial Establishment - General Purpose | https://www.bank-of-algeria.dz/etablissement-financiers-a-vocation-generale/ |
| 3 | Financial Establishment - Specific Purpose | https://www.bank-of-algeria.dz/etablissements-financiers-a-vocation-specifique/ |
| 4 | Representation Office | https://www.bank-of-algeria.dz/bureaux-de-representation/ |
| 5 | Banking Association | https://www.bank-of-algeria.dz/association-des-banques-et-des-etablissements-financiers-abef/ |

## Fields captured per entity

The site renders each entity as an Elementor heading widget (entity name) followed by a text-editor `<p>` with French labels. The notebook pulls:

- **Name** — from `<h2 class="elementor-heading-title">`
- **Address_1 / Address_2 / City / Zip / Cntry** — parsed from `Siège Social :` line; `Cntry` is hard-coded `DZ`; `City` defaults to `Alger` when the address ends in `Alger`; `Zip` extracted only when a 5-digit code appears
- **Phone** — concatenated from `Téléphone :` plus continuation lines (multiple numbers separated by ` / `)
- **Fax** — same pattern as Phone
- **CoType** — sub-category label (see table above)
- **ListLabel** — director / representative name (`Directeur Général` / `Président du Directoire` / `Directeur Exécutif` / `Représentant`)
- **ListName**, **ListCode**, **RegCtry**, **RegCode**, **ListProcessDate**, **RegulationType=Regulated**, **ListLanguage=FR**

Email, website, and registration numbers are **not** published by the regulator on these pages, so the corresponding SQL columns will be empty.

## Selector logic (so future maintainers can find it)

Defined in the **Begin_Function** cell of `DZ_BAL_v1.ipynb`:

- `extract_entities_from_page(html, category_url)` walks every `h2.elementor-heading-title`, finds the sibling `.elementor-widget-text-editor` inside the same `.elementor-widget-wrap`, and keeps the pair only if the text body contains at least one of `Téléphone / Siège Social / Adresse / Fax`. This filters out page-title headings and footer headings (`Rubriques`, `Contact`, `Suivez nous`, copyright).
- `parse_detail_block(p_text)` splits the `<p>` text on the French field labels (`Siège Social :`, `Téléphone :`, `Fax :`, `Directeur Général :` and variants) and concatenates continuation lines for multi-number phone/fax fields.
- `split_address(addr)` is a best-effort split; full string is preserved in `Address_1`.

## Running

```powershell
# from the project root, activate venv then open Jupyter
cd "C:\Users\wuj1\OneDrive - Moody's\Desktop\Regulator"
.\.venv\Scripts\Activate.ps1
jupyter notebook "DZ BAL\DZ_BAL_v1.ipynb"
```

Output: `DZ BAL SQL Ready <timestamp>.xlsx` in the `DZ BAL/` folder, sheet `SQL Ready`.

## Offline parser validation

`_dryrun_parser.py` re-uses the notebook's parsing functions but fetches pages via `urllib`
instead of Selenium. Useful for verifying selectors after the site is updated, without
launching Chrome.

```powershell
cd "C:\Users\wuj1\OneDrive - Moody's\Desktop\Regulator\DZ BAL"
python _dryrun_parser.py
```

Expected last lines on a clean run:
```
GRAND TOTAL: 37
missing director : 1/37   # ABEF (association — no director field on the site)
missing phone    : 0/37
missing address  : 0/37
```

## Expected counts (baseline taken 2026-05-27)

| Category | Entities |
|---|---:|
| Commercial Banks | 21 |
| Financial Establishments — General Purpose | 8 |
| Financial Establishments — Specific Purpose | 1 |
| Representation Offices | 6 |
| Banking Association (ABEF) | 1 |
| **Total** | **37** |

If the total drops far below 37 on a future run, the Elementor template may have changed — re-inspect the heading/text-editor pair selectors first.
