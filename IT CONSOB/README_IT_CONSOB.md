# IT CONSOB — Commissione Nazionale per le Società e la Borsa

Jira: **DECD-6469** (priority High) · Country: Italy · RegCode: `CONSOB` · Site language: English (EN version of consob.it)

Authoritative scraper: **`IT_CONSOB_v2.py`**

## Lists

| ListCode | ListName | Source | ListLabel |
|---|---|---|---|
| IT CONSOB 1 | Class 1 investment firms authorised in other EU countries **with** branches in Italy | HTML, JS-rendered | 4 |
| IT CONSOB 2 | Class 1 investment firms authorised in other EU countries **without** branches in Italy | HTML, JS-rendered | 4 |
| IT CONSOB 3 | Companies of non-EU countries other than banks authorised to operate in Italy **with** branches | HTML, JS-rendered | 4 |
| IT CONSOB 4 | Companies of non-EU countries other than banks authorised **without** branches | HTML, JS-rendered | 4 |
| IT CONSOB 5 | Register of Italian Investment Firms (SIMs) | HTML, JS-rendered | 4 |
| IT CONSOB 6 | Investment Firms authorised in other EU states with branches in Italy | HTML, JS-rendered | 4 |
| IT CONSOB 7 | Listed Companies | HTML, A–Z letter pages | 4 |
| IT CONSOB 8 | Markets (MTF authorised by Consob) | **HTTP 404 upstream — see below** | 4 |

All URLs are under `https://www.consob.it/web/consob-and-its-activities/`.
`ListLabel = 4` throughout: investment firms, listed companies and MTFs are neither banks (1) nor insurance (2).

## Site behaviour (verified live 2026-07-29)

**1. Lists 1–6 are client-side rendered.** This is the reason v1 stopped working — not the captcha.
Plain `requests` returns **HTTP 200** with the correct `<title>` but **zero `<table>`** elements
(`#main-content` ≈ 1,000 chars of navigation only). The identical URL in a real browser renders
**47–77 entity tables**. Any requests-only scraper therefore reports success while producing nothing.
A browser is mandatory for lists 1–6.

**2. The blocker is Radware Bot Manager — and it serves hCaptcha as its challenge widget.**
Blocked traffic redirects to `validate.perfdrive.com`, serves a page titled *"Radware Captcha
Page"*, sets `__uzma` / `__uzmb` / `__uzmc` / `__uzmd` cookies, and embeds an **hCaptcha widget**
(`data-sitekey` present in the block page). So `hcaptcha.png` in this folder is *not* mislabeled and
Radware-vs-hCaptcha is not an either/or: Radware is the bot manager, hCaptcha is the box you tick to
get past it. *(An earlier revision of this file claimed the opposite. Verified wrong 2026-07-29 by
reading the block page directly.)*

It is **rate-triggered, not always-on**: paced loads pass, but a burst gets the network flagged.
List 7's A–Z loop is exactly that shape, which is why it needs jittered pacing and backoff.

**The flag applies to plain `requests` too, not just the browser.** Verified: with a fresh Chrome
profile *and* with no browser at all, both get the same challenge once the network is flagged.
There is no requests-only side door.

**Observed flag duration is far longer than "tens of minutes."** After a ~26-request diagnostic
burst, four probes at 10-minute intervals over 40 minutes were all still blocked — roughly 75
minutes total without clearing. Budget for that, and **do not poll to wait it out**: every probe is
another request from a flagged network and appears to refresh the timer.

**Detection must read the body, not the URL.** One observed response came back **HTTP 200 with the
real page's `<title>` and no redirect**, but zero entity tables — indistinguishable from a slow
render if you only check status or URL. `is_blocked()` checks the body text for this reason;
confirmed returning `True` on a live block page.

Note: a *clean* CONSOB page still contains the string `perfdrive.com` in a Radware `<script>` tag,
so the bare string is **not** a block signal. Only the redirect or the challenge title/body count.

**A page-load timeout is mandatory.** The Radware challenge page never fires a load event, so an
un-timed `page.get()` blocks in a socket read indefinitely — it never reaches the backoff branch
below it. An unattended run on 2026-07-29 sat frozen for **13 minutes** with zero output, parked on
`validate.perfdrive.com`, and had to be killed. Fixed by
`driver.set.timeouts(base=10, page_load=45, script=30)` plus `page.get(url, retry=0, timeout=45)`.
Verified: `get()` now returns in ~1.2 s on a challenge page and `is_blocked()` catches it.
**Do not remove these timeouts** — without them any Radware hit is a silent hang, not a retry.

**3. List 8 is dead upstream.** `mtf-authorised-consob` returns **HTTP 404** (independently
re-confirmed 2026-07-29 — a clean 404 with no challenge involved, so it is genuinely a dead URL and
not the anti-bot wall in disguise), and it is a broken link
on CONSOB's own `/markets` page — i.e. CONSOB's own regression. The nearest live siblings
(`mtf-communitarian`, `regulated-markets`) exist but carry no entity tables. v2 detects the 404,
skips the list and prints a warning rather than silently emitting zero rows.
**Action: a replacement URL is needed from the ticket owner.**

## Structure

Lists 1–6 — one `<table>` per entity inside `div.evidenzalaterale`; rows are `label:` / `value`
`th`/`td` pairs. Selector: **`div.evidenzalaterale table`**. No pagination and no lazy-load
(scroll-to-bottom adds nothing). Label wording varies per list — `Investment firm:`,
`Italian investment firm:`, `Investment firm of non-EU country other than banks:` — so `safe_get()`
matches on substring. `City:` and `Country:` appear **twice** on the "with branches" lists: first
occurrence is the registered office, second is the Italian branch.

List 7 — `https://www.consob.it/web/consob-and-its-activities/listed-companies/list?startsWith=<A-Z>`
(`list-old` is an equivalent alias). Each company is `div.boxQuotata` > `span.boxQuotataTitle`, with
`codConsob=NNNN` in the action links. Observed: A=52, B=75, L=15. The base page without `startsWith`
yields nothing.

## Mapping decisions

- **RegulationType** = `Regulated` for every entry (all lists are positive registers).
- **Address**: if the record has a `Branch:` label, the entity operates in Italy through a branch —
  `Address_1`/`City`/`Zip`/`Cntry` hold the Italian branch and the foreign registered office goes to
  the `- Mother company` columns. With no `Branch:` label there is no branch, so the registered
  office is the entity's own address and belongs in `Address_1`. *(v1 pushed the registered office
  into the mother-company columns on every list, which was wrong for lists 2, 4 and 5.)*
- `LEI code` → `LEI Code`; `Registration no` → `InternalID_1`; `Resolution` /
  `First registration resolution` → `InternalID_2` (a date is parsed out into `RegulationDate`);
  `Customer type` → `License_Type`; list 7's `codConsob` → `InternalID_1`.
- `ListProcessDate` = run date (`%Y-%m-%d`).

## Running

```bash
python "IT CONSOB/IT_CONSOB_v2.py"
```

Output `IT CONSOB SQL Ready <timestamp>.xlsx` is written to **this folder** (gitignored).

### Captcha: solve it by hand (the run resumes by itself)

The most reliable way past Radware is to **click the captcha yourself** — no bypass needed. When a
challenge appears the script maximises and focuses the Chrome window, beeps, posts a macOS
notification, and then **polls the live page until the challenge is gone**. Click the tiles and the
run picks up within ~2 seconds. **There is nothing to type.**

Detecting the solve from the browser rather than from the keyboard is deliberate. An earlier revision
blocked on `input()`, which only works when stdin is a real terminal; launched from a wrapper, an IDE
or a scheduler it raised `EOFError` immediately and the manual path was silently skipped in favour of
timed backoff. Polling has no such dependency. (Pressing Enter still works as an override when stdin
*is* a terminal, and `s` turns manual mode off for the rest of the run.)

Because the clearance cookie is stored in `dp_profile_v2/`, this is normally a **one-time step for the
whole run** — often for several days, since the profile survives between runs.

A **warm-up load** runs before list 1 so any challenge fires at the start, while someone is still
watching, instead of 20 minutes into list 7's A–Z loop.

Manual mode is **on by default**. Unattended runs degrade safely: the first challenge nobody solves
within `CONSOB_MANUAL_WAIT` flips manual mode off for the rest of the run, so the worst case is one
wasted wait window, not one per page.

```bash
CONSOB_MANUAL_WAIT=900 python "IT CONSOB/IT_CONSOB_v2.py"  # wait 15 min per challenge (default 300)
CONSOB_INTERACTIVE=0   python "IT CONSOB/IT_CONSOB_v2.py"  # never wait for a human (Control Room)
```

The startup banner prints which mode is active. stdout is line-buffered so the captcha banner shows
up immediately when the run is watched through a log file.

Operational notes:
- **Do not run headless and do not use incognito.** Headless is far more detectable to Radware, and
  incognito discards the clearance cookie every run. The persistent profile `dp_profile_v2/` keeps
  clearance between runs so the handshake happens once.
- A datacenter/VPN IP gets flagged quickly; a normal office/home IP is best. Once flagged, the IP
  needs tens of minutes to cool down.
- Expect roughly 8 s per rendered page, plus 2–5 s pacing between list 7's 26 letters.

## Status — first full end-to-end run: 2026-08-06 ✅

**737 rows**, 43 columns, written to `IT CONSOB SQL Ready 2026-08-06 14.09.46.xlsx`.

| ListCode | Rows |
|---|---|
| IT CONSOB 1 | 1 |
| IT CONSOB 2 | 5 |
| IT CONSOB 3 | 5 |
| IT CONSOB 4 | 77 |
| IT CONSOB 5 | 58 |
| IT CONSOB 6 | 46 |
| IT CONSOB 7 | 545 |
| IT CONSOB 8 | — (404 upstream, skipped with a warning) |

One captcha for the whole run, at list 7 letter `N`; solved by hand, auto-detected, run continued.
Lists 1–6 and letters A–M needed none.

List 7 by letter: A 52, B 75, C 49, D 17, E 30, F 22, G 33, H 1, I 39, J 1, K 2, L 15, M 35, N 12,
O 10, P 30, Q 0, R 22, S 48, T 27, U 10, V 7, W 3, X 0, Y 1, Z 4.

Verified after the run:

- **`Q` = 0 and `X` = 0 are genuine, not soft-blocks.** Re-loaded live: both render a full page
  (280k / 282k chars) with `blocked = False` and zero `div.boxQuotata`, against an `R` control that
  returned 22 — matching the scrape. This check matters because a Radware soft-block returns HTTP 200
  with the right `<title>` and no content, which is indistinguishable from a real empty letter.
- **List 1 really is a single entity** — confirming the count from the earlier partial run.
- **9 duplicate `Name`+`ListCode` pairs in list 7 are on the site** (e.g. `EDISON SPA` ×3,
  `TELECOM ITALIA SPA` ×2), some carrying a `codConsob` and some not. **Left in deliberately** — the
  output row count must match the site.
- Every row has `Name`, `ListLabel` (all 4), `RegulationType`, `RegCtry`, `RegCode`, `ListName`,
  `ListLanguage` and `ListProcessDate` populated; no blank `Name`.

### Open items

1. **List 8 needs a replacement URL from the ticket owner** — `mtf-authorised-consob` is still 404.
2. **`Name - Mother Company` is empty on all 737 rows** while `Address_1 / City / Zip / Cntry -
   Mother company` are filled on the 52 branch records. On these lists the Italian branch and the
   foreign parent are the same legal entity, so the parent's name is the row's own `Name`. Confirm
   with the ticket owner whether to mirror `Name` into `Name - Mother Company` on those 52 rows or
   leave it blank.

## History

- `IT_CONSOB_v2.py` — current. Browser-rendered, Radware-aware, correct address mapping, 404 guard.
- `IT_CONSOB_v1.ipynb` (2026-05-26) — superseded. Broke on the Liferay redesign; also hardcoded a
  Windows path, injected stale 2025 `__uzm*` cookies (which can *provoke* Radware), used a blind
  `sleep(10)` instead of waiting for content, and added a `'Check'` key outside the frozen schema.
- `IT_CONSOB_Palmela.ipynb` (2025-11-18) — original, superseded.
- `IT CONSOB_tier_0/`, `IT CONSOB_tier_1/` — a June 2026 anti-bot spike (requests parser + cookie
  reuse; SeleniumBase UC / DrissionPage browser stage). Covered **list 7 only**. Kept for reference;
  v2 supersedes both.
