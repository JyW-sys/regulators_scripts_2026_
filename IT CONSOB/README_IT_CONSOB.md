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

### Captcha: solve it by hand

The most reliable way past Radware is to **click the captcha yourself** — no bypass needed. Run the
script from a real terminal and it auto-enables manual mode: when Radware appears it maximises and
focuses the Chrome window, prints instructions, and **waits for you to press Enter**. Solve the tiles,
wait for the CONSOB page, press Enter, and the run continues from where it paused.

Because the clearance cookie is stored in `dp_profile_v2/`, this is normally a **one-time step for the
whole run** — often for several days, since the profile survives between runs.

At the prompt you can type `s` to stop being asked; the run then falls back to timed backoff.

Mode is auto-detected from the terminal (`sys.stdin.isatty()`), so the same file still works
unattended in the Control Room — there it uses timed backoff instead of hanging on a prompt nobody
can answer. Override either way:

```bash
CONSOB_INTERACTIVE=1 python "IT CONSOB/IT_CONSOB_v2.py"   # always ask me
CONSOB_INTERACTIVE=0 python "IT CONSOB/IT_CONSOB_v2.py"   # never ask (unattended)
```

The startup banner prints which mode is active.

Operational notes:
- **Do not run headless and do not use incognito.** Headless is far more detectable to Radware, and
  incognito discards the clearance cookie every run. The persistent profile `dp_profile_v2/` keeps
  clearance between runs so the handshake happens once.
- A datacenter/VPN IP gets flagged quickly; a normal office/home IP is best. Once flagged, the IP
  needs tens of minutes to cool down.
- Expect roughly 8 s per rendered page, plus 2–5 s pacing between list 7's 26 letters.

## Status — not yet run end to end

**No output file has been produced.** The scraper is code-complete and its parsers are unit-tested,
but every live run attempt on 2026-07-29 was stopped by the Radware wall described above. What is
verified: compiles clean, 43-column schema with equal-length columns, address mapping correct on
both real label shapes, block detection working against a live block page, and the page-load
timeout fix. What is **not** verified: the actual row counts for lists 1–7.

To finish it, on a machine whose network is not flagged:

```bash
python "IT CONSOB/IT_CONSOB_v2.py"
```

Run it from a real terminal so `INTERACTIVE` auto-detects on. Solve the one hCaptcha by hand when it
appears; clearance lands in `dp_profile_v2/` and the rest of the run should sail past. Two things to
check in that first run: **list 1** previously rendered only 1 entity (plausible, but confirm against
the Italian site), and **list 8** will be skipped with a warning until a replacement URL arrives.

## History

- `IT_CONSOB_v2.py` — current. Browser-rendered, Radware-aware, correct address mapping, 404 guard.
- `IT_CONSOB_v1.ipynb` (2026-05-26) — superseded. Broke on the Liferay redesign; also hardcoded a
  Windows path, injected stale 2025 `__uzm*` cookies (which can *provoke* Radware), used a blind
  `sleep(10)` instead of waiting for content, and added a `'Check'` key outside the frozen schema.
- `IT_CONSOB_Palmela.ipynb` (2025-11-18) — original, superseded.
- `IT CONSOB_tier_0/`, `IT CONSOB_tier_1/` — a June 2026 anti-bot spike (requests parser + cookie
  reuse; SeleniumBase UC / DrissionPage browser stage). Covered **list 7 only**. Kept for reference;
  v2 supersedes both.
