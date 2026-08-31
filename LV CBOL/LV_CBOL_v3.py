#---- Begin_Librairie ----
# LV CBOL - Latvijas Banka (Bank of Latvia) - Financial Market Participant Register
# DECD-6826
#
# v3: full rebuild. The old uzraudziba.bank.lv/en/market/* site was retired; every
# one of the 13 ticket URLs now 301-redirects to a single landing page on www.bank.lv.
# v1/v2 selectors (div.categories-list, div.posts-block) no longer exist anywhere.
# v3 targets the new register and uses its JSON endpoint. No Selenium, no ChromeDriver.

import os
import re
import time
import json
import datetime
import unicodedata
from urllib.parse import urljoin, quote

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


#---- Begin_fileName ----
regulatorName = 'LV CBOL'

print('Running {} Web Scraping Tool v.3.0'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)


#---- Begin_Variable ----
BASE = 'https://www.bank.lv'
LANDING = BASE + '/en/financial-market-participant-register'
LISTING = BASE + '/en/financial-market-participant-register/market-participants'

# The register renders 10 rows/page in HTML, but ?format=json&limit=N returns the whole
# result set in a single request. PAGE_LIMIT is a safety ceiling, not a hard-coded count.
PAGE_LIMIT = 5000

# Detail pages carry Legal address + licence dates but weigh ~1.1 MB each.
# Implemented and working, but OFF by default - see README for the measured cost.
FETCH_DETAIL = False

# Sub-segments that represent entities that are NOT currently in good standing.
# The ticket does not ask for them and v2 excluded them, so they are dropped -
# but the run log prints exactly how many rows each one removed.
EXCLUDE_ALWAYS = ['liquidation', 'insolvent', 'suspended']

# ---------------------------------------------------------------------------
# One entry per ticket ListNr. 'segment' is matched against the segment TITLE
# discovered on the landing page each run (never a hard-coded id).
# 'include' / 'exclude' are matched against sub-segment TITLES discovered from
# the JSON childSegments fragment each run.
#   mode 'all'     -> take the parent segment whole
#   mode 'include' -> only sub-segments whose title contains one of the keywords
#   mode 'exclude' -> every sub-segment except those matching the keywords
# ---------------------------------------------------------------------------
LISTS = [
    dict(nr='1',  segment='Alternative investment fund managers',
         mode='include', keys=['licensed managers', 'registered managers'],
         listname='Investment service providers', label=4),

    dict(nr='2',  segment='Insurance companies',
         mode='include', keys=['non-life-insurance companies', 'life insurance companies'],
         listname='Insurance companies', label=2),

    dict(nr='3',  segment='Insurance Intermediaries',
         mode='exclude', keys=['freedom of establishment', 'freedom to provide services'],
         listname='Insurance Intermediaries', label=2),

    dict(nr='4',  segment='Financial instruments market',
         mode='include', keys=['depositary', 'issuers', 'regulated market organizers'],
         listname='Financial instruments market', label=4),

    dict(nr='5',  segment='Financial holdings',
         mode='all', keys=[],
         listname='Financial holdings', label=4),

    dict(nr='6',  segment='Investment service providers',
         mode='include', keys=['credit institutions', 'investment firms',
                               'investment management companies'],
         listname='Investment service providers', label=4),

    dict(nr='7',  segment='Investment management companies',
         mode='all', keys=[],
         listname='Investment management companies', label=4),

    dict(nr='8',  segment='Crowdfunding service providers',
         mode='all', keys=[],
         listname='Crowdfunding service providers', label=4),

    dict(nr='9',  segment='Co-operative Credit Unions',
         mode='all', keys=[],
         listname='Co-operative Credit Unions', label=1),

    dict(nr='10', segment='Credit institutions',
         mode='include', keys=['banks', 'representative offices'],
         listname='Credit institutions', label=1),

    dict(nr='11', segment='Payment service providers',
         mode='include', keys=['banks', 'authorized electronic money institutions',
                               'registered electronic money institutions', 'exceptions',
                               'authorized payment institutions', 'third party service providers'],
         listname='Payment service providers', label=1),

    dict(nr='12', segment='Pension Funds',
         mode='all', keys=[],
         listname='Pension Funds', label=4),

    dict(nr='13', segment='Foreign exchange trading companies',
         mode='all', keys=[],
         listname='Foreign exchange trading companies', label=4),
]

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SQL_KEYS = list(sqldict.keys())

session = requests.Session()
session.headers.update({
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
})


#---- Begin_Function ----
def add_row(**kw):
    """Single writer for sqldict. Appends to EVERY one of the 43 keys on every
    record and raises on an unknown key, so column drift is impossible."""
    unknown = set(kw) - set(SQL_KEYS)
    if unknown:
        raise KeyError('add_row got unknown column(s): {}'.format(sorted(unknown)))
    for k in SQL_KEYS:
        sqldict[k].append(kw.get(k, ''))


def norm(s):
    """NFKC + strip accents + collapse whitespace + lowercase.
    Latvian has a c e g i k l n s u z with diacritics and the register mixes
    them with ASCII homoglyphs, so never compare titles with ==."""
    s = unicodedata.normalize('NFKD', (s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'\s+', ' ', s).strip().lower()


def get(url, tries=3, pause=0.6, as_json=False):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=60, verify=False)
            r.raise_for_status()
            if as_json:
                return r.json()
            return r.text
        except Exception as e:
            last = e
            time.sleep(pause * (i + 1))
    raise last


def fetch_segment(alias, limit=PAGE_LIMIT):
    """Query the register's JSON endpoint for one or more segment aliases."""
    url = '{}?format=json&limit={}&segments={}'.format(LISTING, limit, quote(alias, safe=',-'))
    return get(url, as_json=True)


def declared_count(payload):
    """The register prints its own total; parse it for reconciliation."""
    txt = BeautifulSoup(payload.get('resultCount', '') or '', 'lxml').get_text(' ', strip=True)
    m = re.search(r'([\d\s]+?)\s*results?', txt)
    if not m:
        return None
    try:
        return int(re.sub(r'\D', '', m.group(1)))
    except ValueError:
        return None


def child_segments(payload):
    """Discover sub-segment (alias, title) pairs from the JSON fragment.
    Never hard-code this enumeration - the register adds and renames segments."""
    frag = payload.get('childSegments', '') or ''
    out = []
    for inp in BeautifulSoup(frag, 'lxml').select('input[data-alias]'):
        alias = (inp.get('data-alias') or '').strip()
        title = (inp.get('data-title') or '').strip()
        if alias and title:
            out.append((alias, title))
    return out


def discover_segments():
    """Resolve top-level segment title -> alias from the landing page, each run."""
    soup = BeautifulSoup(get(LANDING), 'lxml')
    segs = {}
    for a in soup.select('a[href]'):
        href = urljoin(BASE + '/', a.get('href') or '')
        m = re.search(r'segments=([^&]+)', href)
        if not m:
            continue
        title = a.get_text(' ', strip=True)
        if title:
            segs.setdefault(norm(title), m.group(1))
    return segs


def parse_items(payload):
    """Parse the results HTML fragment into raw dicts.
    One dict per rendered row - no dedupe, the site's row count is the truth."""
    frag = payload.get('results', '') or ''
    soup = BeautifulSoup(frag, 'lxml')
    rows = []
    for rc in soup.select('.result-content'):
        h2 = rc.select_one('h2')
        name = h2.get_text(' ', strip=True) if h2 else ''
        if not name:
            continue
        infos = [i.get_text(' ', strip=True) for i in rc.select('.info-item')]
        infos = [re.sub(r'\s+', ' ', x).strip() for x in infos if x and x.strip()]

        regnr, country, tags = '', '', []
        for it in infos:
            m = re.match(r'^Reg\.?\s*N[ro]\.?\s*(.+)$', it, re.I)
            if m:
                regnr = m.group(1).strip()
            else:
                tags.append(it)
        # the register prints the country of origin as the final info-item
        if tags:
            country = tags[-1]
            tags = tags[:-1]

        par = rc.find_parent('a')
        detail = urljoin(BASE + '/', par.get('href')) if par and par.get('href') else ''

        rows.append(dict(name=name, regnr=regnr, country=country,
                         tags='; '.join(tags), detail=detail))
    return rows


def parse_detail(url):
    """Optional enrichment: legal address from the entity page.
    OFF by default (FETCH_DETAIL) - these pages are ~1.1 MB each."""
    out = {'address': '', 'city': '', 'zip': ''}
    try:
        soup = BeautifulSoup(get(url), 'lxml')
    except Exception as e:
        print('     detail fetch failed for {}: {}'.format(url, str(e)[:80]))
        return out
    txt = soup.get_text('\n', strip=True)
    m = re.search(r'Legal address\s*\n\s*(.+)', txt)
    if m:
        addr = m.group(1).strip()
        out['address'] = addr
        z = re.search(r'(LV-\d{4})', addr)
        if z:
            out['zip'] = z.group(1)
        parts = [p.strip() for p in addr.split(',')]
        if len(parts) >= 2:
            out['city'] = parts[-2].strip() if z else parts[-1].strip()
    return out


def select_aliases(spec, subs):
    """Turn a list spec + the discovered sub-segments into the aliases to query.
    Returns (aliases_to_fetch, chosen_titles, dropped_for_status)."""
    if spec['mode'] == 'all' or not subs:
        return None, [], []

    chosen = []
    for alias, title in subs:
        n = norm(title)
        hit = any(norm(k) in n for k in spec['keys'])
        if spec['mode'] == 'include' and hit:
            chosen.append((alias, title))
        elif spec['mode'] == 'exclude' and not hit:
            chosen.append((alias, title))

    # report any keyword that matched nothing, loudly
    if spec['mode'] == 'include':
        for k in spec['keys']:
            if not any(norm(k) in norm(t) for _, t in subs):
                print("     SKIPPED - no sub-segment whose title contains '{}'".format(k))

    dropped = [(a, t) for a, t in chosen if any(x in norm(t) for x in EXCLUDE_ALWAYS)]
    chosen = [(a, t) for a, t in chosen if not any(x in norm(t) for x in EXCLUDE_ALWAYS)]
    return chosen, [t for _, t in chosen], dropped


#---- Begin_MainLoop ----
segments = discover_segments()
print('Discovered {} top-level segments on the landing page'.format(len(segments)))

summary = []
excluded_report = []

for spec in LISTS:
    listcode = '{} {}'.format(regulatorName, spec['nr'])
    print('\n------ Working with {} : {} ------'.format(listcode, spec['segment']))

    seg_alias = segments.get(norm(spec['segment']))
    if not seg_alias:
        print("     SKIPPED - no segment whose label contains '{}'".format(spec['segment']))
        summary.append((listcode, spec['segment'], 0, None))
        continue

    parent = fetch_segment(seg_alias, limit=1)
    parent_total = declared_count(parent)
    subs = child_segments(parent)
    print('     segment alias = {} | site declares {} in the whole segment | {} sub-segments'
          .format(seg_alias, parent_total, len(subs)))

    chosen, titles, dropped = select_aliases(spec, subs)

    if chosen is None:
        alias_q = seg_alias
        print('     mode=all -> taking the whole segment')
    else:
        if not chosen:
            print('     SKIPPED - selection matched no sub-segment')
            summary.append((listcode, spec['segment'], 0, parent_total))
            continue
        alias_q = ','.join(a for a, _ in chosen)
        print('     selected {} sub-segment(s): {}'.format(len(chosen), '; '.join(titles)))

    for a, t in (dropped or []):
        d = fetch_segment(a, limit=1)
        n = declared_count(d)
        print('     EXCLUDED (not in good standing): {} -> {} entities'.format(t, n))
        excluded_report.append((listcode, t, n))

    payload = fetch_segment(alias_q)
    declared = declared_count(payload)
    items = parse_items(payload)

    if declared is not None and declared != len(items):
        print('     *** MISMATCH: site declares {} but {} rows parsed ***'
              .format(declared, len(items)))
    else:
        print('     reconciled: site declares {} / parsed {}'.format(declared, len(items)))

    for it in items:
        extra = {'address': '', 'city': '', 'zip': ''}
        if FETCH_DETAIL and it['detail']:
            extra = parse_detail(it['detail'])

        add_row(
            ListLabel=spec['label'],
            Typology=spec['listname'],
            Name=it['name'],
            InternalID_1=it['regnr'],
            InternalID_1_type='Registration number' if it['regnr'] else '',
            CoType=it['tags'],
            Address_1=extra['address'],
            City=extra['city'],
            Zip=extra['zip'],
            Cntry=it['country'],
            RegulationType='Regulated',
            RegCtry='Latvia',
            ListCode=listcode,
            ListLanguage='EN',
            ListName=spec['listname'],
            ListProcessDate=processdate,
        )

    print('     -> {} rows added'.format(len(items)))
    summary.append((listcode, spec['segment'], len(items), declared))


#---- Begin_writer and save df to excel ----
print('\n================ RUN SUMMARY ================')
total = 0
for code, seg, n, declared in summary:
    flag = '' if (declared is None or declared == n) else '   <-- MISMATCH vs {}'.format(declared)
    print('{:<12} {:<42} {:>6}{}'.format(code, seg[:42], n, flag))
    total += n
print('{:<12} {:<42} {:>6}'.format('TOTAL', '', total))

if excluded_report:
    print('\n--- Excluded sub-segments (not-in-good-standing, for requester review) ---')
    for code, title, n in excluded_report:
        print('{:<12} {:<60} {}'.format(code, title[:60], n))

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

assert list(df.columns) == SQL_KEYS, 'schema drift: columns do not match the fixed 43-key sqldict'
print('\nSchema check OK: {} columns'.format(len(df.columns)))

# Registration numbers are identifiers, not quantities. Excel silently turns an
# all-digit string into a float (40003761234 -> 4.000376e+10) and drops leading
# zeros, so pin the ID columns to text before writing.
for _c in ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax']:
    df[_c] = df[_c].apply(lambda v: '' if v == '' or pd.isna(v) else str(v).strip())

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
