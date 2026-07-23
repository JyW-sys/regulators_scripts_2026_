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

3. PDFs are written to `pdf_output/`, one file per unique **(RegCtry, ListCode)**
   pair, named `<workbook base name> - <RegCtry>-<ListCode>.pdf`
   (e.g. `SR CBSU SQL Ready ... - SR-1.pdf`, `... - SR-2.pdf`). Because each PDF
   name starts with its source workbook's name, multiple workbooks never collide.

Each PDF is a single-column list of the workbook's **Name** values under a
`Name` header, 32 names per page.

## Notes

- Dependencies are pinned in `requirements.txt` (`pandas`, `openpyxl`, `reportlab`).
- Needs the columns **Name**, **RegCtry**, **ListCode**; a workbook missing any
  of them is skipped with a message.
- Temporary Excel lock files (`~$...xlsx`, created while a workbook is open) are
  ignored.
- Font: uses Arial (`C:\Windows\Fonts\arial.ttf` on the Windows box,
  `/System/Library/Fonts/Supplemental/Arial.ttf` on macOS) for Unicode, else
  falls back to Helvetica.
- The `Name`-only layout / helpers (`draw_header`, `export_list_to_pdf`,
  `safe_filename`) are extracted from `CW CBCSCW_v2.py`.
