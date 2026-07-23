"""
IT CONSOB - Tier 0 scraper (plain requests, NO browser, NO captcha solving).

Why this works
--------------
consob.it sits behind **Radware Bot Manager** (blocked requests 302-redirect to
validate.perfdrive.com / "Radware Captcha Page"). The captcha is therefore a
*bot-detection trigger*, not an always-on wall.

The "Listed companies" register (CONSOB list 7) is **server-rendered** at
    /listed-companies/list-old?startsWith=<A-Z>
and is reachable with a plain, browser-like requests session. Each company is:
    <div class="boxQuotata">
        <span class="boxQuotataTitle">A2A SPA</span>
        <a class="boxQuotataLink" title="Ownership" href="...?...codConsob=NNNN"> ...
So we just GET each letter page and read the titles -- no Selenium, no captcha.

Other CONSOB lists (1-6, 8) may intermittently redirect to the Radware captcha on
plain requests; those are handled by Tier 1 (undetected-chromedriver). See README.

Run with the project venv:
    .venv/bin/python "IT CONSOB/IT CONSOB_tier_0/consob_tier0.py"
"""

import datetime
import json
import os
import random
import re
import string
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

HERE = os.path.dirname(os.path.abspath(__file__))
# Optional: a cookies.json produced by the Tier 1 browser step (Radware clearance
# cookies like reese84 / _uzma...). If present, we reuse it so plain requests can
# fetch all 26 letters without being re-challenged. See README.
COOKIE_FILE = os.path.join(HERE, "clearance_cookies.json")

LIST7_URL = (
    "https://www.consob.it/web/consob-and-its-activities/"
    "listed-companies/list-old?startsWith={}"
)

# Browser-like headers keep Radware happy for the server-rendered list pages.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-GB,en;q=0.9,it;q=0.8",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

# NOTE: a non-blocked CONSOB page still references "perfdrive.com" in a Radware
# script tag, so the bare string is NOT a block signal. A real block either
# redirects to validate.perfdrive.com or serves the "Radware Captcha Page".
BLOCK_MARKERS = (
    "radware captcha page",
    "we apologize for the inconvenience",
)


def is_blocked(resp: requests.Response) -> bool:
    """True if Radware intercepted this response."""
    if "validate.perfdrive.com" in resp.url.lower():
        return True
    low = resp.text.lower()
    return any(m in low for m in BLOCK_MARKERS)


def parse_listed_companies(html: str) -> list[dict]:
    """Extract one row per company from a list-old letter page."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for box in soup.select("div.boxQuotata"):
        title = box.select_one("span.boxQuotataTitle")
        if not title:
            continue
        name = title.get_text(strip=True)
        if not name:
            continue
        # codConsob is CONSOB's internal id; grab it from any action link if present.
        code = ""
        for a in box.find_all("a", href=True):
            m = re.search(r"codConsob=(\d+)", a["href"])
            if m:
                code = m.group(1)
                break
        rows.append({"Name": name, "codConsob": code})
    return rows


def scrape_list7(session: requests.Session, polite=(1.0, 2.5), max_consec_blocks=3):
    """Scrape the full A-Z listed-companies register. Returns (rows, blocked_letters).

    Stops early after `max_consec_blocks` consecutive Radware blocks: once it
    flags the client, every later request is redirected too, so hammering is
    pointless (and noisy). Re-run with clearance cookies to get past it.
    """
    rows, blocked, consec = [], [], 0
    for letter in string.ascii_uppercase:
        url = LIST7_URL.format(letter)
        try:
            r = session.get(url, timeout=30, allow_redirects=True)
            blocked_now = is_blocked(r)
        except requests.RequestException as e:
            # Radware redirects to validate.perfdrive.com, whose cert fails
            # verification -> surfaces as an SSLError. Treat as a block, quietly.
            blocked_now = "perfdrive" in str(e).lower() or isinstance(e, requests.exceptions.SSLError)
            if not blocked_now:
                print(f"  [{letter}] request error: {type(e).__name__}")
                blocked.append(letter)
                continue

        if blocked_now:
            print(f"  [{letter}] BLOCKED by Radware")
            blocked.append(letter)
            consec += 1
            if consec >= max_consec_blocks:
                remaining = string.ascii_uppercase[string.ascii_uppercase.index(letter) + 1:]
                if remaining:
                    print(f"  -> {consec} consecutive blocks; stopping. Not tried: {remaining}")
                    blocked.extend(remaining)
                break
            continue

        consec = 0
        found = parse_listed_companies(r.text)
        print(f"  [{letter}] {len(found)} companies")
        rows.extend(found)
        time.sleep(random.uniform(*polite))
    return rows, blocked


def load_clearance_cookies(session: requests.Session) -> bool:
    """Inject Radware clearance cookies exported by the Tier 1 browser step."""
    if not os.path.exists(COOKIE_FILE):
        return False
    with open(COOKIE_FILE) as f:
        cookies = json.load(f)
    for c in cookies:
        session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".consob.it"))
    print(f"Loaded {len(cookies)} clearance cookies from {os.path.basename(COOKIE_FILE)}")
    return True


def to_sqldict(rows: list[dict]) -> dict:
    """Map parsed rows into the project's fixed SQL-Ready structure."""
    # Canonical column set (DO NOT change keys -- see project CLAUDE.md).
    sqldict = {k: [] for k in (
        'bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
        'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
        'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type', 'Address_1',
        'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax', 'Website', 'Email',
        'RegulationType', 'RegulationTypeCode', 'RegulationDate', 'CancellationDate',
        'RegCtry', 'RegCode', 'ListCode', 'ListLanguage', 'ListValidityDate',
        'ListName', 'ListProcessDate', 'LEI Code', 'BIC SWIFT Code',
        'Name - Mother Company', 'Address_1 - Mother company',
        'Address_2 -  Mother company', 'City - Mother company',
        'Zip - Mother company', 'Cntry - Mother company', 'Phone - Mother company',
    )}
    processdate = datetime.datetime.now().strftime('%Y-%m-%d')
    for row in rows:
        for k in sqldict:
            sqldict[k].append("")
        sqldict['Name'][-1] = row['Name']
        sqldict['InternalID_1'][-1] = row['codConsob']
        sqldict['InternalID_1_type'][-1] = 'codConsob' if row['codConsob'] else ''
        sqldict['Cntry'][-1] = 'Italy'
        sqldict['RegCtry'][-1] = 'Italy'
        sqldict['RegCode'][-1] = 'CONSOB'
        sqldict['RegulationType'][-1] = 'Regulated'
        sqldict['ListName'][-1] = 'Listed Companies'
        sqldict['ListCode'][-1] = 'IT CONSOB 7'
        sqldict['ListLanguage'][-1] = 'English'
        sqldict['ListProcessDate'][-1] = processdate
    return sqldict


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    load_clearance_cookies(session)  # no-op if Tier 1 hasn't produced them
    # Warm up on the landing page so the session looks like a real visit.
    try:
        session.get(
            "https://www.consob.it/web/consob-and-its-activities/listed-companies",
            timeout=30,
        )
    except requests.RequestException:
        pass

    print("Scraping IT CONSOB 7 (Listed companies) A-Z ...")
    rows, blocked = scrape_list7(session)
    print(f"\nTotal companies: {len(rows)} | letters blocked: {blocked or 'none'}")
    if not rows:
        print("No rows scraped -- Radware blocked the session. See README (Tier 1).")
        return

    df = pd.DataFrame(to_sqldict(rows))
    now = datetime.datetime.now()
    out = os.path.join(
        HERE, "IT CONSOB 7 SQL Ready {}.xlsx".format(str(now).replace(":", ".")[:-7])
    )
    df.to_excel(out, index=False)
    print(f"Saved -> {out}  ({len(df)} rows)")


if __name__ == "__main__":
    main()
