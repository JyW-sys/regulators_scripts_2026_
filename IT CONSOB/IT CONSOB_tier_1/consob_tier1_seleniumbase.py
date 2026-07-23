"""
IT CONSOB - Tier 1 (PRIMARY): SeleniumBase UC mode vs Radware Bot Manager.

Strategy
--------
Radware validates the TLS/JS fingerprint on every request, so plain `requests`
(Tier 0) gets locked out after ~1 page. A real, anti-detect browser executes
Radware's JS challenge, earns the clearance cookie, and -- with a PERSISTENT
profile -- keeps it across the A-Z loop. If the Radware/captcha interstitial
shows, `uc_gui_click_captcha()` clicks it.

Once a page is cleared, we reuse the proven Tier 0 parser on its HTML.

macOS note
----------
`uc_gui_click_captcha()` drives the real mouse via PyAutoGUI, which needs
**Accessibility permission** for the app you launch this from (VS Code / Terminal):
System Settings -> Privacy & Security -> Accessibility. Without it the click
silently does nothing. Run NON-headless.

Run (project venv):
    .venv/bin/python "IT CONSOB/IT CONSOB_tier_1/consob_tier1_seleniumbase.py"
"""

import datetime
import json
import os
import random
import string

import pandas as pd
from seleniumbase import SB

from consob_common import LIST7_URL, is_blocked, parse_listed_companies, to_sqldict

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "uc_profile")          # persists Radware clearance
COOKIE_EXPORT = os.path.join(                        # for the Tier 0 hybrid
    HERE, "..", "IT CONSOB_tier_0", "clearance_cookies.json"
)

# uc_gui_click_captcha() drives the real mouse via PyAutoGUI, which needs macOS
# Accessibility permission. On a locked-down Mac that's unavailable, so we default
# to MANUAL solve (you click the captcha yourself in the visible window -- your own
# mouse needs no permission). Set True only if you've granted Accessibility.
USE_GUI_CLICK = False


def page_blocked(sb) -> bool:
    try:
        return is_blocked(sb.get_current_url(), sb.get_page_source())
    except Exception:
        return True


def ensure_cleared(sb, url, attempts=3) -> bool:
    """Open `url`; if Radware blocks, pass the challenge.

    UC mode's reconnect trick often clears Radware with no captcha at all. If a
    challenge does appear, we either auto-click it (USE_GUI_CLICK, needs macOS
    Accessibility) or pause for you to solve it by hand in the visible window.
    The persistent profile then keeps the clearance for the rest of the run.
    """
    sb.uc_open_with_reconnect(url, reconnect_time=6)
    for i in range(attempts):
        if not page_blocked(sb):
            return True
        if USE_GUI_CLICK:
            print(f"    Radware challenge (try {i + 1}/{attempts}) -> uc_gui_click_captcha()")
            try:
                sb.uc_gui_click_captcha()
            except Exception as e:
                print(f"    uc_gui_click_captcha error: {type(e).__name__}: {e}")
            sb.sleep(random.uniform(3, 5))
        else:
            print(f"    Radware challenge on {url}")
            print("    -> Solve it BY HAND in the Chrome window (your own mouse), wait for")
            print("       the company list to load, then come back here.")
            input("    Press Enter once you're past the captcha: ")
        if not page_blocked(sb):
            return True
    return not page_blocked(sb)


def export_cookies(sb):
    """Best-effort: save cookies for the Tier 0 hybrid. NOTE: Radware binds
    clearance to the TLS fingerprint, so plain `requests` reuse may still fail;
    curl_cffi (impersonate='chrome') is the client most likely to honor it."""
    try:
        cookies = sb.get_cookies()
        os.makedirs(os.path.dirname(COOKIE_EXPORT), exist_ok=True)
        with open(COOKIE_EXPORT, "w") as f:
            json.dump(cookies, f, indent=2)
        print(f"Exported {len(cookies)} cookies -> {os.path.relpath(COOKIE_EXPORT, HERE)}")
    except Exception as e:
        print(f"cookie export skipped: {type(e).__name__}: {e}")


def main():
    rows, blocked = [], []
    with SB(uc=True, headless=False, user_data_dir=PROFILE) as sb:
        print("Handshake with Radware on letter A ...")
        if not ensure_cleared(sb, LIST7_URL.format("A")):
            print("Could not pass Radware on the first page. Re-run (the profile keeps\n"
                  "progress), check Accessibility permission, or try a cleaner IP.")
            return

        for letter in string.ascii_uppercase:
            if not ensure_cleared(sb, LIST7_URL.format(letter)):
                print(f"  [{letter}] still blocked")
                blocked.append(letter)
                continue
            found = parse_listed_companies(sb.get_page_source())
            print(f"  [{letter}] {len(found)} companies")
            rows.extend(found)
            sb.sleep(random.uniform(2, 5))

        export_cookies(sb)

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
