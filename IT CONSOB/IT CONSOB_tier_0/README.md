# IT CONSOB — Tier 0 (plain `requests`, no browser, no captcha)

Goal: get the CONSOB lists **without** a browser or captcha solving, by hitting the
server-rendered pages directly with `requests` + BeautifulSoup.

## What we found (recon, 2026-06-18)

1. **CONSOB is behind Radware Bot Manager.** Blocked requests 302-redirect to
   `https://validate.perfdrive.com/...` ("Radware Captcha Page", `botmanager_support@radware.com`).
   The image-tile captcha the user saw is served by Radware, not Google directly.
2. **The "Listed companies" register (CONSOB list 7) is server-rendered** at
   `/listed-companies/list-old?startsWith=<A-Z>`. Each company is:
   ```html
   <div class="boxQuotata">
     <span class="boxQuotataTitle">A2A SPA</span>
     <a class="boxQuotataLink" title="Ownership" href="...codConsob=NNNN">...
   ```
   So no JS/datatable AJAX is needed — the names are in the HTML. `consob_tier0.py`
   parses them straight into the project's SQL-Ready structure.
3. **Radware lets the *first* request through, then locks on.** In testing, letter
   **A returned 52 companies**, then letters **B–Z were all redirected** to the
   captcha. Radware expects its JS challenge to be solved (to mint a `reese84` /
   `_uzma*` clearance cookie); plain `requests` can't execute JS, so after the first
   hit it flags the client.

## Verdict

- ✅ The **parser works** and the data is fully server-rendered — no JS rendering needed.
- ❌ **Plain `requests` alone can't sustain access** — Radware blocks after ~1 page.
- ⚠️ A one-off run may still grab one letter (or a few) before the block kicks in.

## How to actually make Tier 0 work — the hybrid

Let a real browser (Tier 1, `undetected-chromedriver`) solve Radware **once**, then
export its clearance cookies and hand them to this fast parser:

1. Tier 1 opens CONSOB in a real browser, passes Radware, and writes the cookies to
   `IT CONSOB_tier_0/clearance_cookies.json` (list of `{name, value, domain}`).
2. Run `consob_tier0.py` again — it auto-loads that file via `load_clearance_cookies()`
   and fetches all 26 letters with plain `requests` (fast, no per-letter browser).

This keeps the heavy browser work to a single Radware handshake and reuses the
lightweight parser for the bulk scrape.

## Run

```bash
# from the repo root, with the project venv
.venv/bin/python "IT CONSOB/IT CONSOB_tier_0/consob_tier0.py"
```

Output: `IT CONSOB 7 SQL Ready <timestamp>.xlsx` written **inside this folder**
(gitignored — scraped output is never committed).

## Scope / notes

- Covers **CONSOB list 7 (Listed companies)** only — that's the one confirmed
  server-rendered. Lists 1–6 and 8 redirect to the Radware captcha on plain requests
  and need the Tier 1 browser (or the hybrid cookie reuse).
- Does **not** modify the original `IT_CONSOB_Palmela.ipynb`.
