# MD NBMO Regulatory Lists

National Bank of Moldova (NBM / BNM). Jira: **DECD-3761**.

List 1 is a dedicated HTML page. Lists 2–5 all come from the same "supervised entities" hub page,
which links downloadable registers (`.xlsx`, `.docx`, and one legacy `.doc`).

| RegCtry | RegCode | ListNr | ListLabel | ListName | URL | Comments |
|---------|---------|--------|-----------|----------|-----|----------|
| MD | NBMO | 1 | 1 | List of authorized banks of the Republic of Moldova | https://www.bnm.md/en/content/authorized-banks-republic-moldova | Static HTML; one `div.bank-content` block per bank. |
| MD | NBMO | 2 | 2 | List of authorized insurances of the Republic of Moldova | https://www.bnm.md/en/content/supervised-entities-insurance-and-non-bank-lending#art1 | **First table only** of *Register of professional participants in the insurance market*, plus all of *List of insurance and/or reinsurance brokers* and *Register of insurance and bancassurance agents*. First worksheet of each file. |
| MD | NBMO | 3 | 4 | List of Non-bank credit organizations of the Republic of Moldova | (same hub) | *Register of authorized non-bank credit organizations*. Drop orange rows / names containing **(Radiată / Excluded / Исключена)**. |
| MD | NBMO | 4 | 4 | List of Savings and Lending Associations of the Republic of Moldova | (same hub) | *SLAs holding category A licences* + *SLAs holding category B licences and the Central National Association*. From the **category B list only**, drop names containing **filiala** / **sucursala**. |
| MD | NBMO | 5 | 4 | List of Credit history bureaus of the Republic of Moldova | (same hub) | *List of Credit history bureaus* + *List of entities (information sources)…*. From the second file, drop names containing **radiata / radiată**. |

## Current version

`MD_NBMO_v2.ipynb` / `MD_NBMO_v2.py` — supersedes `MD NBMO_v_1.ipynb`.

**Row counts, run 2026-08-20 — 672 rows total**

| ListCode | Rows | Breakdown |
|---|---|---|
| 1 | 10 | 10 banks |
| 2 | 152 | 9 insurers + 59 brokers + 84 agents |
| 3 | 109 | active non-bank credit organizations |
| 4 | 184 | 127 category A + 57 category B (110 − 53 branches) |
| 5 | 217 | 4 bureaus + 213 information sources (268 − 55 radiate) |

## Why v2 exists

v1 ran only on a Windows workstation with Microsoft Word installed, and had silently drifted
out of sync with the site.

1. **`win32com` / Microsoft Word removed.** v1 converted `.doc` → `.docx` through Word
   automation, which is why the control server could not run it (no Office licence — see the
   Jira thread) and the output had to be attached to the ticket by hand. Both SLA registers are
   `.docx` today and are read with `python-docx`; the one remaining legacy `.doc` (credit history
   bureaus) is parsed by a **self-contained OLE2/Word-binary reader** in the Function cell
   (`_cfb_streams` + `doc_text`). No Word, no `pywin32`, no extra pip packages.
2. **Selenium / ChromeDriver removed.** Every page and file is reachable with plain `requests`;
   there is no JavaScript rendering and no Cloudflare on `bnm.md`.
3. **Links resolved by label, not by file name.** BNM re-uploads these registers under new
   suffixes (`_28`, `_14`, `(2)_2`, …) every few weeks, so v1's `contains(@href,'bancassurance')`
   style XPaths rot. v2 matches the English anchor text on the hub page.

## Site quirks worth knowing

- **The English page links the wrong agents file.** *Register of insurance and bancassurance
  agents* currently points at `Registrul brokerilor de asigurare (reasigurare) (1)_1.xlsx` — a
  stale copy of the **brokers** register (same three sheets, older date). Left uncorrected, list 2
  silently ships the brokers twice and no agents at all. v2 validates the workbook (the real file
  has a `Registrul` sheet) and falls back to the Romanian hub page, which links the correct
  `Registrul agenților de asigurare și agenților bancassurance_15.xlsx`. **Re-check this on each
  run** — if BNM fixes the English link the fallback simply stops firing.
- **The insurers workbook holds two tables on one sheet.** Rows 2–10 are the 9 active insurers;
  after a blank gap, row 16 starts *Lista Societăţilor de asigurare cu licenţa retrasă*
  (licence withdrawn). The ticket asks for the first table only, so v2 stops at the first blank
  `Nr.` cell. v1 took both and marked the withdrawn companies `Regulated`.
- **ROCNA:** `Starea persoanei juridice` (col 11) is the authoritative status. v2 keeps only
  `Activă/ Active / Действующая` (109). This also excludes `În lichidare` (6) and `Suspendată` (2),
  matching the behaviour that was validated and loaded in April 2026 — the ticket text only
  mentions the radiate rows, so raise it with the requester if in-liquidation entities are wanted.
- **SLA `.docx` header rows repeat.** `python-docx` returns the vertically-merged header twice;
  rows are filtered with `is_header_row()` rather than by position.
- **Category B branches share the parent IDNO.** v1 de-duplicated on IDNO, which happened to drop
  the branches but would also drop legitimate entities. v2 applies the ticket rule literally
  (name contains `filiala` / `sucursala`).

## Bugs fixed from v1

- List 3 never called `pad()`, so every column after `Name` drifted out of alignment for the
  109 non-bank credit organizations. v2 replaces `pad()` with `add_row()`, which writes every
  column on every record, so drift is impossible.
- List 5's `.doc` branch read `row.iloc[3]` as the address — in the file BNM publishes today that
  is the **Administrator** column — and then did `.split(';')[4]` on it. Replayed against the
  current `Lista Birourilor istoriilor de credit_2.doc` (same 4 × 6 table v1 logged) this raises
  `IndexError: list index out of range` on the first bureau, which aborts the list 5 loop before
  the information-sources file is reached. It did not raise during the April 2026 run, so the
  column layout of that `.doc` changed afterwards. The branch also appended `phone_`, a variable
  that only exists inside the list 4 loop, so the value leaked from the last savings-and-loan
  association. v2 maps the columns by position against the current file and takes the phone from
  the bureaus row itself.
- `sqldict` carried an extra `Check` key, breaking the fixed 43-column schema.
- `ListLabel`, `ListLanguage`, `ListValidityDate` and `Cntry` were never populated.
- `scriptfolder` was hard-coded to `C:\Users\wuj1\...`; it is now derived from `__file__` / `cwd`.

## Output

`MD NBMO SQL Ready <timestamp>.xlsx` is written to this folder (not `tempfolder/`).
The last notebook cell also writes one PDF per list into `tempfolder/`, using a Unicode TTF so the
Romanian diacritics (ă î ș ț) survive — Helvetica would mangle them.
