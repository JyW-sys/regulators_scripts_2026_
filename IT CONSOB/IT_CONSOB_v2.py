"""
IT CONSOB - Web Scraping Tool v2  (Jira DECD-6469)

Why v2 exists
-------------
v1 (IT_CONSOB_v1.ipynb) broke for reasons that are NOT the captcha everyone
assumed. Diagnosis (2026-07-29, live):

1. **consob.it was rebuilt on Liferay and lists 1-6 are now client-side rendered.**
   Plain `requests` returns HTTP 200 with the correct <title> but **zero <table>**
   (#main-content = ~1,000 chars of nav only). The same URL in a real browser
   renders 47-77 entity tables. So "200 OK + empty result" was silently producing
   empty lists -- this, not the captcha, is the primary breakage.

2. **Radware Bot Manager is rate-triggered, not an always-on wall.** The
   `hcaptcha.png` in this folder is mislabeled: the challenge is Radware
   (redirects to `validate.perfdrive.com`, serves "Radware Captcha Page").
   Single paced page loads pass fine; ~26 rapid requests get the IP flagged --
   which is what list 7's A-Z loop does. Hence the jittered pacing + backoff here.

3. **List 8 (`mtf-authorised-consob`) is HTTP 404 upstream.** It is a dead link on
   CONSOB's own /markets page, i.e. CONSOB's regression, not ours. Handled as a
   soft skip with a loud warning so the run still produces lists 1-7.

4. v1 also hardcoded a Windows `scriptfolder`, injected stale 2025 `__uzm*`
   cookies (which can *provoke* Radware), used a blind `sleep(10)` instead of
   waiting for the content, and added a `'Check'` key not in the frozen schema.
   All fixed below.

Structure of the data (verified live)
-------------------------------------
Lists 1-6: one <table> per entity inside `div.evidenzalaterale`, rows are
`label:` / `value` th-td pairs, e.g.
    Investment firm: | ACME SIM SPA
    LEI code:        | 815600...
    Registered office| VIA ROMA 1
    City:            | 20121 MILANO
    Country:         | ITALY
    Branch:          | ...        <- only on the "with branches" lists
    City:            | ...        <- 2nd occurrence = branch
    Country:         | ...
List 7: `div.boxQuotata` > `span.boxQuotataTitle`, paged by letter at
    /listed-companies/list?startsWith=<A-Z>

Run:
    python "IT CONSOB/IT_CONSOB_v2.py"
"""

import datetime
import os
import random
import re
import string
import sys
import time
from collections import defaultdict

import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumOptions, ChromiumPage

# --------------------------------------------------------------------------
# Begin_fileName / workspace
# --------------------------------------------------------------------------
regulatorName = 'IT CONSOB'

print("Running {} Web Scraping Tool v.2.0".format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook

os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        try:
            os.remove(os.path.join(tempfolder, rem))
        except IsADirectoryError:
            pass
else:
    os.mkdir(tempfolder)

# Persistent Chrome profile: Radware clearance survives between runs, so we
# handshake once instead of once per page. Kept out of git (see .gitignore).
DP_PROFILE = os.path.join(scriptfolder, 'dp_profile_v2')

# ---- Manual captcha solving ----------------------------------------------
# The operator can solve the Radware tile challenge by hand, which is far more
# reliable than any automated bypass. When INTERACTIVE is on, a Radware hit
# pauses the run, brings Chrome to the front and waits for you to click through;
# the clearance cookie then lands in DP_PROFILE, so you normally solve ONCE and
# every later page (and later run) sails past.
#
# Auto-detected from the terminal so the same file still works unattended in the
# Control Room -- there it falls back to timed backoff instead of hanging on a
# prompt nobody can answer. Force it either way with:
#     CONSOB_INTERACTIVE=1   (always ask)   /   CONSOB_INTERACTIVE=0   (never ask)
_env_interactive = os.environ.get('CONSOB_INTERACTIVE')
if _env_interactive is not None:
    INTERACTIVE = _env_interactive.strip() not in ('0', 'false', 'False', '')
else:
    INTERACTIVE = sys.stdin is not None and sys.stdin.isatty()

_manual = {'enabled': INTERACTIVE}   # flipped off if the operator says "skip all"

# --------------------------------------------------------------------------
# Begin_Variable
# --------------------------------------------------------------------------
# DO NOT CHANGE this structure (project CLAUDE.md).
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

BASE = 'https://www.consob.it/web/consob-and-its-activities/'

# ListLabel: 1=bank, 2=insurance, 3=both, 4=everything else.
# Investment firms / listed companies / MTFs are none of the above -> 4.
regdict = {
    regulatorName + ' 1': {
        'url': BASE + 'class-1-investment-firms-authorised-in-other-eu-countries-with-branches-in-italy',
        'name': 'Class 1 investment firms authorised in other EU countries with branches in Italy',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 2': {
        'url': BASE + 'class-1-investment-firms-authorised-in-other-eu-countries-without-branches-in-italy',
        'name': 'Class 1 investment firms authorised in other EU countries without branches in Italy',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 3': {
        'url': BASE + 'companies-of-non-eu-authorized-to-operate-in-italy-with-branches',
        'name': 'Companies of non-EU countries other than banks authorised to operate in Italy with branches',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 4': {
        'url': BASE + 'companies-non-eu-authorized-in-italy-without-branches',
        'name': 'Companies of non-EU countries other than banks authorised to operate in Italy without branches',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 5': {
        'url': BASE + 'register-of-italian-investment-firms-sims-',
        'name': 'Register of Italian Investment Firms (SIMs)',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 6': {
        'url': BASE + 'investment-firms-with-branches',
        'name': 'Investment Firms authorised in other EU states with branches in Italy',
        'label': 4, 'kind': 'entity'},
    regulatorName + ' 7': {
        'url': BASE + 'listed-companies/list?startsWith={}',
        'name': 'Listed Companies',
        'label': 4, 'kind': 'letters'},
    regulatorName + ' 8': {
        'url': BASE + 'mtf-authorised-consob',
        'name': 'Markets (MTF authorised by Consob)',
        'label': 4, 'kind': 'entity'},
}

# Selectors confirmed live 2026-07-29.
ENTITY_SELECTOR = 'div.evidenzalaterale table'   # lists 1-6 (and 8 if restored)
LISTED_SELECTOR = 'div.boxQuotata'               # list 7
LISTED_TITLE = 'span.boxQuotataTitle'

# --------------------------------------------------------------------------
# Begin_Function
# --------------------------------------------------------------------------


def bourrage_same_length_array(sqldict):
    """Pad every column out to the length of ListProcessDate."""
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict


def clean_text(value):
    if value is None:
        return ''
    return re.sub(r'\s+', ' ', str(value).replace('\xa0', ' ')).strip()


def safe_get(record, key, idx=0, default=''):
    """Fetch the idx-th value for a label, matching on substring.

    Label wording changes per list ('Investment firm', 'Italian investment
    firm', 'Investment firm of non-EU country other than banks'), so an exact
    match is too brittle -- substring matching covers all six variants.
    """
    key = key.lower().strip()
    values = record.get(key)
    if values is None:
        for actual_key, actual_values in record.items():
            if key in actual_key:
                values = actual_values
                break
    if not values or len(values) <= idx:
        return default
    return values[idx]


def split_zip_city(value):
    """'20121 MILANO' -> ('20121', 'MILANO'); 'LONDON EC2M 1QS' -> handled too.

    Replaces v1's brittle len(parts)==2/3 branching, which crashed with
    UnboundLocalError whenever a city had 1 or 4+ tokens.
    """
    v = clean_text(value)
    if not v:
        return '', ''
    province = ''
    m = re.match(r'^(.*?)\s*\(([^)]{1,20})\)\s*$', v)   # trailing '(MI)'
    if m:
        v, province = m.group(1).strip(), m.group(2).strip()
    # UK-style two-token postcode at the end, e.g. 'LONDON EC2M 1QS'.
    m = re.search(r'\s([A-Z]{1,2}\d[A-Z\d]?\s+\d[A-Z]{2})\s*$', v, re.I)
    if m:
        return m.group(1), v[:m.start()].strip()
    parts = v.split()
    if not parts:
        return '', province
    if any(ch.isdigit() for ch in parts[0]):            # leading postcode (IT/EU)
        return parts[0], ' '.join(parts[1:]).strip() or province
    if len(parts) >= 2 and any(ch.isdigit() for ch in parts[-1]):  # single trailing token
        return parts[-1], ' '.join(parts[:-1]).strip()
    return '', v


def first_date(text):
    """Pull a date out of a resolution string, e.g. 'no. 12345 of 3.4.2019'."""
    m = re.search(r'(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})', clean_text(text))
    if not m:
        return ''
    d, mth, y = m.groups()
    if len(y) == 2:
        # CONSOB resolutions run from the early 1990s to today, so pivot at 70:
        # '99' is 1999, not 2099.
        y = ('19' if int(y) >= 70 else '20') + y
    try:
        return datetime.date(int(y), int(mth), int(d)).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def append_row(**kw):
    """Append one record, filling every frozen column exactly once."""
    for key in sqldict:
        sqldict[key].append('')
    for key, val in kw.items():
        if key in sqldict:
            # keep ints (ListLabel) as ints; only text needs normalising
            sqldict[key][-1] = val if isinstance(val, int) else clean_text(val)
    sqldict['ListProcessDate'][-1] = processdate


# ---- Radware handling -----------------------------------------------------

def is_blocked(page):
    """True if Radware intercepted this page load.

    NOTE: a *clean* CONSOB page still references perfdrive.com in a Radware
    script tag, so the bare string is NOT a block signal. Only the redirect or
    the challenge page title/body count.
    """
    url = (page.url or '').lower()
    if 'validate.perfdrive.com' in url:
        return True
    low = (page.html or '').lower()
    return ('radware captcha page' in low
            or 'we apologize for the inconvenience' in low)


def solve_by_hand(page, attempt, tries):
    """Hand the browser to the operator to click the Radware captcha.

    Returns True if we should keep prompting on later blocks, False if the
    operator asked to stop being asked (then we fall back to timed backoff).
    """
    try:                       # make sure the window can't be missed
        page.set.window.max()
        page.set.activate()
    except Exception:
        pass
    print("\n" + "=" * 70)
    print("  RADWARE CAPTCHA  -  attempt {}/{}".format(attempt, tries))
    print("  A Chrome window is open on the challenge page.")
    print("  1. Solve the captcha in that window.")
    print("  2. Wait until the real CONSOB page appears.")
    print("  3. Come back here and press Enter.")
    print("  (The clearance is saved in dp_profile_v2/, so this is normally a")
    print("   ONE-TIME step for the whole run.)")
    print("=" * 70)
    try:
        answer = input("  Press Enter when solved  [or type 's' to stop asking]: ")
    except EOFError:           # stdin vanished (piped/scheduled run)
        return False
    return answer.strip().lower() not in ('s', 'skip')


def load_page(page, url, selector=None, tries=3, settle=2.0):
    """Load a URL, wait for the JS-rendered content, survive Radware.

    Returns the page HTML, or '' if we could not get through.

    This is the core v1 fix: v1 did `driver.get(); sleep(10)` and then parsed
    whatever was there. Because lists 1-6 are client-rendered, a slow render
    silently yielded zero tables and v1 recorded an empty list as success.
    """
    for attempt in range(1, tries + 1):
        try:
            # timeout + retry=0: we do our own retry loop, and a hung load must
            # surface as a return, never as an indefinite block.
            page.get(url, retry=0, timeout=45)
        except Exception as exc:
            print("      page.get failed on attempt {}/{} ({}: {})"
                  .format(attempt, tries, type(exc).__name__, str(exc)[:120]))
            time.sleep(5)
            continue
        if is_blocked(page):
            if _manual['enabled']:
                # Let the operator click it. Far more reliable than any bypass,
                # and the clearance cookie persists for the rest of the run.
                if not solve_by_hand(page, attempt, tries):
                    _manual['enabled'] = False
                    print("      -> switching to unattended backoff for the rest of the run")
            else:
                backoff = 20 * attempt + random.uniform(0, 10)
                print("      Radware challenge on attempt {}/{}. Cooling down {:.0f}s."
                      .format(attempt, tries, backoff))
                time.sleep(backoff)
            continue           # re-request the URL with the fresh clearance
        if selector:
            try:
                page.wait.ele_displayed(f'css:{selector}', timeout=25)
            except Exception:
                pass                       # fall through to the settle + recheck
        time.sleep(settle)                 # let the last widgets paint
        if is_blocked(page):
            continue
        return page.html
    return ''


# ---- Parsers --------------------------------------------------------------

def parse_entity_tables(html):
    """Lists 1-6: one entity per <table> in div.evidenzalaterale.

    Returns a list of {label: [values...]} -- labels repeat (City/Country appear
    twice on the 'with branches' lists), so values are kept as ordered lists.
    """
    soup = BeautifulSoup(html, 'html.parser')
    records = []
    for table in soup.select(ENTITY_SELECTOR):
        data = defaultdict(list)
        for row in table.select('tr'):
            cells = row.find_all(['th', 'td'])
            if len(cells) < 2:
                continue
            label = clean_text(cells[0].get_text(' ', strip=True)).rstrip(':').lower()
            value = clean_text(cells[1].get_text(' ', strip=True))
            if label:
                data[label].append(value)
        if data:
            records.append(data)
    return records


def map_entity(rec, listcode, meta):
    """Turn one parsed entity into one SQL-Ready row.

    Address logic (v1 got this wrong for the 'without branches' lists):
      * the record has a 'Branch:' label  -> the entity operates in Italy through
        a branch: Address_1/City/Zip/Cntry = the Italian branch, and the foreign
        registered office goes to the '- Mother company' columns.
      * no 'Branch:' label -> there is no branch, so the registered office IS the
        entity's own address and belongs in Address_1/City/Zip/Cntry.
    """
    name = safe_get(rec, 'investment firm') or safe_get(rec, 'company') or safe_get(rec, 'name')
    if not name:
        return False

    lei = safe_get(rec, 'lei')
    reg_office = safe_get(rec, 'registered office')
    head_zip, head_city = split_zip_city(safe_get(rec, 'city', 0))
    head_country = safe_get(rec, 'country', 0)

    branch_addr = safe_get(rec, 'branch')
    has_branch = bool(branch_addr) or len(rec.get('city', [])) > 1

    reg_no = safe_get(rec, 'registration no')
    resolution = (safe_get(rec, 'first registration resolution')
                  or safe_get(rec, 'resolution'))
    customer_type = safe_get(rec, 'customer type')

    common = dict(
        Name=name,
        ListLabel=meta['label'],
        RegulationType='Regulated',
        RegulationDate=first_date(resolution),
        License_Type=customer_type,
        RegCtry='IT',
        RegCode='CONSOB',
        ListCode=listcode,
        ListName=meta['name'],
        ListLanguage='English',
    )
    common['LEI Code'] = lei
    if reg_no:
        common['InternalID_1'] = reg_no
        common['InternalID_1_type'] = 'Registration no'
    if resolution:
        common['InternalID_2'] = resolution
        common['InternalID_2_type'] = 'Resolution'

    if has_branch:
        branch_zip, branch_city = split_zip_city(safe_get(rec, 'city', 1))
        append_row(
            Address_1=branch_addr, City=branch_city, Zip=branch_zip,
            Cntry=safe_get(rec, 'country', 1) or 'ITALY',
            **{'Address_1 - Mother company': reg_office,
               'City - Mother company': head_city,
               'Zip - Mother company': head_zip,
               'Cntry - Mother company': head_country},
            **common)
    else:
        append_row(Address_1=reg_office, City=head_city, Zip=head_zip,
                   Cntry=head_country, **common)
    return True


def parse_listed_companies(html):
    """List 7: each company is a div.boxQuotata with a title span and a
    codConsob-bearing link."""
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for box in soup.select(LISTED_SELECTOR):
        title = box.select_one(LISTED_TITLE)
        if not title:
            continue
        name = clean_text(title.get_text(strip=True))
        if not name:
            continue
        code = ''
        for a in box.find_all('a', href=True):
            m = re.search(r'codConsob=(\d+)', a['href'])
            if m:
                code = m.group(1)
                break
        out.append({'Name': name, 'codConsob': code})
    return out


# --------------------------------------------------------------------------
# Begin_chromedriver
# --------------------------------------------------------------------------
options = ChromiumOptions()
options.set_download_path(tempfolder)
options.set_user_data_path(DP_PROFILE)   # keep Radware clearance between runs
options.set_argument('--disable-blink-features=AutomationControlled')
options.set_argument('--ignore-certificate-errors')
options.auto_port()
# Deliberately NOT headless and NOT incognito: headless is far more detectable
# to Radware, and incognito throws away the clearance cookie every run.
driver = ChromiumPage(options)

# Page-load timeout is MANDATORY here, not a nicety. The Radware challenge page never
# fires a load event, so an un-timed page.get() blocks in a socket read forever - an
# unattended run observed here sat frozen for 13 minutes with no output at all, never
# reaching the backoff path below. With a timeout, get() returns on the challenge page
# and is_blocked() can do its job.
driver.set.timeouts(base=10, page_load=45, script=30)

print("Captcha mode: {}".format(
    "MANUAL - the run will pause and ask you to click any Radware captcha"
    if INTERACTIVE else
    "UNATTENDED - timed backoff (no prompts; set CONSOB_INTERACTIVE=1 to be asked)"))

# --------------------------------------------------------------------------
# Begin_Main
# --------------------------------------------------------------------------
counts, problems = {}, []

try:
    for k, reg in enumerate(regdict):
        meta = regdict[reg]
        print("[INFO] : Working {}/{} _({})_{}".format(k + 1, len(regdict), reg, meta['name']))
        before = len(sqldict['ListProcessDate'])

        # ---- List 7: A-Z letter pages ------------------------------------
        if meta['kind'] == 'letters':
            blocked_letters = []
            for letter in string.ascii_uppercase:
                html = load_page(driver, meta['url'].format(letter),
                                 selector=LISTED_SELECTOR, tries=3)
                if not html:
                    print("    [{}] blocked".format(letter))
                    blocked_letters.append(letter)
                    continue
                found = parse_listed_companies(html)
                print("    [{}] {} companies".format(letter, len(found)))
                for row in found:
                    append_row(
                        Name=row['Name'],
                        InternalID_1=row['codConsob'],
                        InternalID_1_type='codConsob' if row['codConsob'] else '',
                        ListLabel=meta['label'],
                        Cntry='ITALY',
                        RegulationType='Regulated',
                        RegCtry='IT', RegCode='CONSOB',
                        ListCode=reg, ListName=meta['name'],
                        ListLanguage='English')
                # Human pacing -- 26 back-to-back hits is exactly what trips Radware.
                time.sleep(random.uniform(2.0, 5.0))
            if blocked_letters:
                problems.append("{}: letters still blocked by Radware: {}"
                                .format(reg, ','.join(blocked_letters)))

        # ---- Lists 1-6 (and 8): one table per entity ---------------------
        else:
            html = load_page(driver, meta['url'], selector=ENTITY_SELECTOR, tries=3)
            if not html:
                problems.append("{}: could not load {} (Radware)".format(reg, meta['url']))
                print("    !! blocked, skipped")
                continue

            # List 8 is 404 upstream: CONSOB's own /markets page links to it but
            # the target no longer exists. Detect and skip loudly rather than
            # silently emitting zero rows (which is what v1 did).
            if 'New Consob website' in (driver.title or '') or '404' in (driver.title or ''):
                problems.append("{}: HTTP 404 upstream -- {} no longer exists on "
                                "consob.it (dead link on CONSOB's own /markets page). "
                                "Needs a replacement URL from the ticket owner."
                                .format(reg, meta['url']))
                print("    !! 404 upstream, skipped -- see warnings at the end")
                continue

            records = parse_entity_tables(html)
            print("    parsed {} entity tables".format(len(records)))
            if not records:
                problems.append("{}: page loaded but 0 entity tables matched '{}' "
                                "-- selector may have changed again".format(reg, ENTITY_SELECTOR))
            for rec in records:
                map_entity(rec, reg, meta)
            time.sleep(random.uniform(2.0, 4.0))

        sqldict = bourrage_same_length_array(sqldict)
        counts[reg] = len(sqldict['ListProcessDate']) - before
        print("    -> {} rows".format(counts[reg]))

finally:
    try:
        driver.quit()
    except Exception:
        pass

# --------------------------------------------------------------------------
# Begin_writer -- save to the REGULATOR folder (not tempfolder)
# --------------------------------------------------------------------------
os.chdir(scriptfolder)
sqldict = bourrage_same_length_array(sqldict)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

outpath = os.path.join(scriptfolder, filename)
df.to_excel(outpath, sheet_name='SQL Ready', index=False)

print("\n=== Per-list row counts ===")
for reg, n in counts.items():
    print("  {:<14} {}".format(reg, n))
print("Saved {} rows to {}".format(len(df), outpath))

if problems:
    print("\n=== WARNINGS ({}) ===".format(len(problems)))
    for p in problems:
        print("  - " + p)
