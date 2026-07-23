# IT CONSOB — Tier 1 (real anti-detect browser vs Radware Bot Manager)

Tier 0 proved CONSOB's data is server-rendered and the parser works, but plain
`requests` gets locked out by **Radware Bot Manager** after ~1 page. Tier 1 uses a
real, anti-detect browser to pass Radware, then reuses the Tier 0 parser.

## Files

| File | Role |
|---|---|
| `consob_tier1_seleniumbase.py` | **PRIMARY** — SeleniumBase UC mode; uses `uc_gui_click_captcha()` on the Radware challenge |
| `consob_tier1_drissionpage.py` | **FALLBACK** — DrissionPage (CDP, no webdriver fingerprint); hand-solve once if challenged |
| `consob_common.py` | Shared parser + SQL-Ready mapping (mirrors Tier 0) |

## Order of attack

1. **Run SeleniumBase UC mode first** (the user's pick):
   ```bash
   .venv/bin/python "IT CONSOB/IT CONSOB_tier_1/consob_tier1_seleniumbase.py"
   ```
2. **If it can't pass Radware, run the DrissionPage fallback:**
   ```bash
   .venv/bin/python "IT CONSOB/IT CONSOB_tier_1/consob_tier1_drissionpage.py"
   ```

## What makes it pass (Radware-specific, matters more than the tool)

- **Persistent profile** — `uc_profile/` (SB) / `dp_profile/` (DP). Radware clearance
  (`reese84`, `__uzm*`) is stored there, so you handshake **once**, not per letter.
- **Non-headless.** Headless is far more detectable; keep the window visible.
- **Human pacing.** 2–5 s randomized delays between letters (already built in).
- **Clean IP.** Datacenter/VPN IPs get flagged fast; a normal office/home IP is best.
  (The IP used during development is currently Radware-flagged — expected.)

## ⚠️ macOS Accessibility permission (for `uc_gui_click_captcha`)

`uc_gui_click_captcha()` moves/clicks the **real mouse** via PyAutoGUI. macOS blocks
synthetic clicks unless you grant **Accessibility** permission to the launching app:
**System Settings → Privacy & Security → Accessibility** → enable VS Code / Terminal.
Without it, the captcha click silently does nothing. (Same permission discussed for
the keep-alive `pyautogui` script.)

## The Tier 0 hybrid (optional speed-up)

The SeleniumBase script exports cookies to
`../IT CONSOB_tier_0/clearance_cookies.json`. Tier 0 auto-loads them. **Caveat:**
Radware binds clearance to the TLS fingerprint, so plain `requests` reuse may still be
blocked — if you want the fast path, swap Tier 0's client for **`curl_cffi`**
(`impersonate="chrome"`), which replays a real Chrome TLS fingerprint.

## Scope

- Covers **CONSOB list 7 (Listed companies)**, A–Z. Other lists (1–6, 8) use different
  page layouts; once Radware is passed, add their parsers the same way.
- Does **not** modify the original `IT_CONSOB_Palmela.ipynb`.
