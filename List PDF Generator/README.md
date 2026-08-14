# List PDF Generator

Standalone utility that turns a **SQL Ready** `.xlsx` into one PDF per list.

## Setup (one time)

```
pip install -r requirements.txt
```

## Usage

1. Copy one **or more** `... SQL Ready ....xlsx` workbook(s) into this folder —
   the script processes **every** `.xlsx` it finds in one run.
2. Run:

   ```
   python list_pdf_generator.py
   ```

3. PDFs are written to `pdf_output/`, one file per unique **(RegCtry, RegCode,
   ListCode)** combination, named
   `<RegCtry> <RegCode> SQL Ready <date-time from the workbook's own filename>- <ListCode>.pdf`.

   E.g. uploading `XX BCEAO SQL Ready 2026-07-10 12.32.59.xlsx` produces
   `NE BCEAONE SQL Ready 2026-07-10 12.32.59- 1.pdf`,
   `SN BCEAOSN SQL Ready 2026-07-10 12.32.59- 1.pdf`, ... one per
   (RegCtry, RegCode, ListCode) row group found in the workbook. The date-time
   is whatever comes after `"SQL Ready "` in the *uploaded* filename — the
   workbook must be named `... SQL Ready <date-time>.xlsx` for this to work.

Each PDF is a single-column list of the workbook's **Name** values under a
`Name` header, 32 names per page.

## Notes

- Dependencies are pinned in `requirements.txt` (`pandas`, `openpyxl`, `reportlab`).
- Needs the columns **Name**, **RegCtry**, **RegCode**, **ListCode**; a workbook
  missing any of them is skipped with a message. A workbook whose filename doesn't
  contain `"SQL Ready <date-time>"` is skipped too (nothing to build the PDF name from).
- Temporary Excel lock files (`~$...xlsx`, created while a workbook is open) are
  ignored.
- Font: uses Arial (`C:\Windows\Fonts\arial.ttf` on the Windows box,
  `/System/Library/Fonts/Supplemental/Arial.ttf` on macOS) for Unicode, else
  falls back to Helvetica.
- The `Name`-only layout / helpers (`draw_header`, `export_list_to_pdf`,
  `safe_filename`) are extracted from `CW CBCSCW_v2.py`.
