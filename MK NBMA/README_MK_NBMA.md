# MK NBMA — National Bank of the Republic of North Macedonia

Scraper for North Macedonia's central bank, **NBRM** (nbrm.mk), English pages.

- **Jira:** DECD-6134 (parent epic DECD-3438 — Regulators 2026 Crawlers)
- **RegCtry:** `MK`
- **RegCode:** `NBMA` (confirmed on the regulators maintenance site)
- **RegulationType:** `Regulated`
- **Script:** `MK NBMA_v_1.ipynb`
- **Output:** `MK NBMA SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`), saved in this folder
- **Run:** **DrissionPage (real Chrome)** — nbrm.mk sits behind a Cloudflare JS challenge; plain
  `requests` gets 403. The challenge auto-passes in a few seconds; the scraper waits for the
  `inner-content-box` content marker, not just the page title. The two xlsx registers are then
  downloaded with `requests` reusing the browser's cookies **and its exact User-Agent**
  (`cf_clearance` is UA-bound).

## Lists (ticket ListNr → source; ticket skips ListNr 2)

| ListNr | `ListName` (ticket) | `ListLabel` | Source | Count (2026-07-13) |
|---|---|---|---|--:|
| 1 | Banks | 1 | `banki-en.nspx` — anchors inside `div.inner-content-box > p` | 13 |
| 3 | Saving Houses | 1 | `stedilnici-en.nspx` — 3-column table | 2 |
| 4 | Other financial institutions | 4 | `ostanati_finansiski_institutcii-en.nspx` | 3 |
| 5 | NBRM participants (MIPS) | 4 | operators xlsx, sheet `MIPS Participants` | 19 |
| 6 | KIBS participants | 4 | operators xlsx, sheet `KIBS Participants` | 14 |
| 7 | Register of payment institutions | 4 | payment-institutions xlsx | 5 |

The ticket's "tabs" for lists 5/6 are **xlsx sheet tabs**, not HTML tabs. Both workbooks are
linked from `registri-pups-en.nspx`; the operators filename is **version-stamped**
(`..._12026.xlsx`), so the links are resolved each run by anchor text — never hardcoded.

## Parsing decisions

- **List 1:** name = anchor text only (one `<p>` carries trailing text "- available in Macedonian
  only" outside the link); `Website` = anchor href. No address/phone published.
- **List 3:** name/address/phone/fax/email parsed from `<br>`-separated lines; the site spells
  one row's fax label "Faks:" (Macedonian) — treated as Fax. The Manager column has no sqldict
  field and is not captured. `", 1000 Skopje"` tails are split into `Zip`/`City`.
- **List 4:** the excluded "Government (non-financial) institutions" section starts at a
  `<strong>` marker inside the same `<p>` — collection stops there (its 2 entries are plain text,
  not links, so they'd be skipped anyway). 3 entities kept, 2 excluded.
- **Lists 5/6:** xlsx sheets, header row 3, columns Ref.no / Name / UCIN / Address.
  UCIN → `InternalID_1` (type `UCIN`); the literal placeholder `X` (MasterCard) is blanked.
  **`Cntry` is set to `MK` for all rows** even though MasterCard International is US-addressed
  (2000 Purchase Street, NY) — it's a participant register of the Macedonian systems; review if
  QA prefers `US` there. One MIPS name contains a **Cyrillic 'А'** in "АD"
  (Development Bank row) — kept as-is.
- **List 7:** single-sheet xlsx (sheet literally named "Sample Sheet"), header row 3, 14 columns.
  Title → `Name`, Single tax number → `InternalID_1` (`Tax number`), UCIN → `InternalID_2`
  (`UCIN`), "Main offfice" (sic) → `Address_1`, Phone/E-mail/Website, licensing decision date
  (`DD.MM.YYYY / D No. …`) → `RegulationDate`, services text → `License_Type`. All 5 rows show
  status `active`; the scraper warns if any other status ever appears.
- All cell values are `.strip()`-ed (both workbooks have trailing-space noise).

## Last run

- 2026-07-13 (v1): **56** entities. `MK NBMA SQL Ready 2026-07-13 10.17.56.xlsx`.
