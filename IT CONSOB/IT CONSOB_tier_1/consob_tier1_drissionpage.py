"""
IT CONSOB - Tier 1 (FALLBACK): DrissionPage vs Radware Bot Manager.

Use this if the SeleniumBase UC-mode script can't get past Radware. DrissionPage
drives a real Chrome over CDP with no webdriver attached, so there's no
`navigator.webdriver`/chromedriver fingerprint -- it often clears Radware with
less fiddling. A persistent user-data path keeps the clearance cookie across runs.

DrissionPage has no built-in captcha clicker. If Radware shows the image-tile
challenge, solve it once by hand in the visible window, then press Enter; the
persistent profile means later runs usually won't be challenged again.

Run (project venv):
    .venv/bin/python "IT CONSOB/IT CONSOB_tier_1/consob_tier1_drissionpage.py"
"""

import datetime
import os
import random
import string
import time

import pandas as pd
from DrissionPage import ChromiumOptions, ChromiumPage

from consob_common import LIST7_URL, is_blocked, parse_listed_companies, to_sqldict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "dp_profile")  # persists Radware clearance


def ensure_cleared(page, url, attempts=3) -> bool:
    page.get(url)
    for i in range(attempts):
        if not is_blocked(page.url, page.html):
            return True
        print(f"    Radware challenge (try {i + 1}/{attempts}). "
              "Solve it by hand in the browser window if image tiles appear.")
        input("    ...then press Enter to retry: ")
        page.get(url)
    return not is_blocked(page.url, page.html)


def main():
    co = ChromiumOptions()
    co.set_user_data_path(PROFILE)
    co.set_argument("--disable-blink-features=AutomationControlled")
    # co.headless(False)  # keep visible so you can hand-solve if needed
    page = ChromiumPage(co)

    rows, blocked = [], []
    try:
        print("Handshake with Radware on letter A ...")
        if not ensure_cleared(page, LIST7_URL.format("A")):
            print("Could not pass Radware on the first page. Re-run or try a cleaner IP.")
            return

        for letter in string.ascii_uppercase:
            if not ensure_cleared(page, LIST7_URL.format(letter)):
                print(f"  [{letter}] still blocked")
                blocked.append(letter)
                continue
            found = parse_listed_companies(page.html)
            print(f"  [{letter}] {len(found)} companies")
            rows.extend(found)
            time.sleep(random.uniform(2, 5))
    finally:
        page.quit()

    print(f"\nTotal companies: {len(rows)} | letters blocked: {blocked or 'none'}")
    if not rows:
        print("No rows scraped.")
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
