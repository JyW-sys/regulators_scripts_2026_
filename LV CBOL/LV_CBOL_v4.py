#---- Begin_Librairie ----
# LV CBOL - Latvijas Banka (Bank of Latvia) - Financial Market Participant Register
# DECD-6826
#
# v4: the ticket description was rewritten on 2026-08-31. Every one of the 13 lists now
# reads "Extract all entities from the link or select the listName in the Segment field
# and extract all entities", and the requester confirmed "please use the links in the
# Jira description". So the whole sub-segment include/exclude machinery that v3 carried
# is gone - each list is now its parent segment taken whole.
#
# Two consequences that matter:
#   1. Volume goes from 460 rows to ~4400. Lists 3 (1522) and 11 (1110) are now larger
#      than the register's page cap, so v4 paginates. v3 did not need to and could not.
#   2. limit=5000 does NOT return everything - the register silently caps a page at 1000
#      and still reports the true total. v3's single-shot fetch would have returned 1000
#      rows for list 3 while the site declared 1522. See PAGE_SIZE below.

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

print('Running {} Web Scraping Tool v.4.0'.format(regulatorName))

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

# ---- ticket-level constants. These are TEMPLATE fields with fixed values, not
# ---- anything derived from the page. The house format is
# ----     RegCtry = the 2-letter country code   (NOT the country name)
# ----     RegCode = the agency code alone       ('CBOL', not 'LV CBOL')
# ----     ListCode = the bare ticket ListNr     ('1', not 'LV CBOL 1')
# ---- i.e. the three tokens of '<CC> <AGENCY> <listnr>'. Hard-coded on purpose -
# ---- deriving them by splitting a name at runtime is how sibling notebooks ended
# ---- up emitting a different regulator's code entirely.
REGCTRY = 'LV'
REGCODE = 'CBOL'

# MEASURED, not guessed: ?limit=5000 returns HTTP 200 with exactly 1000 rendered rows
# while resultCount still says 1522. The register caps a page at 1000 and says nothing.
# So request 1000 and page through. ?page=N is honoured (page 2 of limit=1000 returned
# the remaining 522 with no overlap; a page past the end returns 0 rows, which is the
# loop's stop condition). Do not raise this above 1000 expecting more rows back.
PAGE_SIZE = 1000
MAX_PAGES = 50  # safety stop: 50k rows is far beyond any segment on this register

# Detail pages carry Legal address + licence dates but weigh ~1.1 MB each. At v3's 460
# rows that was ~500 MB; at v4's ~4400 rows it is ~4.8 GB. Still implemented, still off.
FETCH_DETAIL = False

# ---------------------------------------------------------------------------
# One entry per ticket ListNr, in the ticket's own order.
#
# 'alias' is the segment id taken verbatim from the Jira description URL, because the
# requester asked for exactly those links. 'segment' is the human title, used only to
# cross-check the alias against what the landing page advertises this run - if the
# register renames or renumbers a segment the run prints a loud ALIAS DRIFT warning
# instead of silently scraping the wrong thing.
#
# Every list is whole-segment now; there is no include/exclude selection left to make.
# ---------------------------------------------------------------------------
LISTS = [
    dict(nr='1',  alias='3-alternative-investment-fund-managers',
         segment='Alternative investment fund managers',
         listname='Alternative investment fund managers', label=4),

    dict(nr='2',  alias='51-insurance-companies',
         segment='Insurance companies',
         listname='Insurance companies', label=2),

    dict(nr='3',  alias='137-insurance-intermediaries',
         segment='Insurance Intermediaries',
         listname='Insurance Intermediaries', label=2),

    dict(nr='4',  alias='107-financial-instruments-market',
         segment='Financial instruments market',
         listname='Financial instruments market', label=4),

    dict(nr='5',  alias='471-financial-holdings',
         segment='Financial holdings',
         listname='Financial holdings', label=4),

    dict(nr='6',  alias='111-investment-service-providers',
         segment='Investment service providers',
         listname='Investment service providers', label=4),

    dict(nr='7',  alias='1-investment-management-companies',
         segment='Investment management companies',
         listname='Investment management companies', label=4),

    dict(nr='8',  alias='466-crowdfunding-service-providers',
         segment='Crowdfunding service providers',
         listname='Crowdfunding service providers', label=4),

    dict(nr='9',  alias='94-co-operative-credit-unions',
         segment='Co-operative Credit Unions',
         listname='Co-operative Credit Unions', label=1),

    dict(nr='10', alias='41-credit-institutions',
         segment='Credit institutions',
         listname='Credit institutions', label=1),

    dict(nr='11', alias='236-payment-service-providers',
         segment='Payment service providers',
         listname='Payment service providers', label=1),

    dict(nr='12', alias='135-pension-funds',
         segment='Pension Funds',
         listname='Pension Funds', label=4),

    dict(nr='13', alias='469-foreign-exchange-trading-companies',
         segment='Foreign exchange trading companies',
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
            r = session.get(url, timeout=120, verify=False)
            r.raise_for_status()
            if as_json:
                return r.json()
            return r.text
        except Exception as e:
            last = e
            time.sleep(pause * (i + 1))
    raise last


def fetch_page(alias, page=1, limit=PAGE_SIZE):
    """One page of the register's JSON endpoint for a segment alias."""
    url = '{}?format=json&limit={}&segments={}&page={}'.format(
        LISTING, limit, quote(alias, safe=',-'), page)
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


def discover_segments():
    """Resolve top-level segment title -> alias from the landing page, each run.
    Used only to cross-check the ticket's hard-coded aliases, never to replace them."""
    try:
        soup = BeautifulSoup(get(LANDING), 'lxml')
    except Exception as e:
        print('Landing-page discovery failed ({}); alias cross-check skipped'.format(str(e)[:60]))
        return {}
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
    One dict per rendered row - no dedupe, the site's row count is the truth.
    (List 3 genuinely renders the same personal name more than once; those are
    distinct registrations and both must survive.)"""
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


def fetch_all_rows(alias):
    """Page through a segment until the register stops handing back rows.

    Returns (rows, declared). Stops on an empty page, never on 'we have enough' -
    the reconciliation against `declared` is what proves the page loop was right,
    so the loop must not be allowed to satisfy its own success condition.
    """
    rows, declared, page = [], None, 1
    while page <= MAX_PAGES:
        payload = fetch_page(alias, page=page)
        if declared is None:
            declared = declared_count(payload)
        batch = parse_items(payload)
        if not batch:
            break
        rows.extend(batch)
        print('     page {:>2}: +{:>4} rows (running {})'.format(page, len(batch), len(rows)))
        if len(batch) < PAGE_SIZE:
            break
        page += 1
        time.sleep(0.3)
    else:
        print('     *** hit MAX_PAGES={} - segment may be truncated ***'.format(MAX_PAGES))
    return rows, declared


#---- Begin_MainLoop ----
segments = discover_segments()
print('Discovered {} top-level segments on the landing page (cross-check only)'
      .format(len(segments)))

summary = []

for spec in LISTS:
    # display label for the run log ONLY - the ListCode COLUMN is the bare nr, see add_row
    runlabel = '{} {}'.format(regulatorName, spec['nr'])
    print('\n------ Working with {} : {} ------'.format(runlabel, spec['segment']))

    alias = spec['alias']
    live = segments.get(norm(spec['segment']))
    if live and live != alias:
        print('     *** ALIAS DRIFT: ticket says {} but the landing page now links {} ***'
              .format(alias, live))
    elif not live:
        print('     note: landing page has no link titled {!r}; using the ticket alias'
              .format(spec['segment']))

    print('     segment alias = {} (whole segment, per ticket)'.format(alias))

    items, declared = fetch_all_rows(alias)

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
            RegCtry=REGCTRY,
            RegCode=REGCODE,
            ListCode=spec['nr'],
            ListLanguage='EN',
            ListName=spec['listname'],
            ListProcessDate=processdate,
        )

    print('     -> {} rows added'.format(len(items)))
    summary.append((runlabel, spec['segment'], len(items), declared))


#---- Begin_writer and save df to excel ----
print('\n================ RUN SUMMARY ================')
total = 0
mismatches = 0
for code, seg, n, declared in summary:
    flag = ''
    if declared is None or declared != n:
        flag = '   <-- MISMATCH vs {}'.format(declared)
        mismatches += 1
    print('{:<12} {:<42} {:>6}{}'.format(code, seg[:42], n, flag))
    total += n
print('{:<12} {:<42} {:>6}'.format('TOTAL', '', total))
print('lists reconciled: {}/{}'.format(len(summary) - mismatches, len(summary)))

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

assert list(df.columns) == SQL_KEYS, 'schema drift: columns do not match the fixed 43-key sqldict'
print('\nSchema check OK: {} columns'.format(len(df.columns)))

# Template fields are fixed values with a fixed shape. ListCode is the bare ticket
# ListNr - NOT '<CC> <AGENCY> <nr>' - and RegCode is the agency alone. Both were got
# wrong once; assert the shape so it cannot regress silently.
assert set(df['RegCtry']) == {REGCTRY}, 'RegCtry must be {!r}, got {}'.format(REGCTRY, set(df['RegCtry']))
assert set(df['RegCode']) == {REGCODE}, 'RegCode must be {!r}, got {}'.format(REGCODE, set(df['RegCode']))
_badlc = sorted(c for c in set(df['ListCode']) if not str(c).isdigit())
assert not _badlc, 'ListCode must be a bare number per list, got {}'.format(_badlc)
print('Template fields OK: RegCtry={} RegCode={} ListCode={}'
      .format(REGCTRY, REGCODE, ','.join(sorted(set(df['ListCode']), key=int))))

# Name must hold entity names, not a stray status/flag column. A row count alone does
# not prove that, so assert the content separately before writing.
_bad = df[df['Name'].str.strip().isin(['', 'Yes', 'No', 'N/A', '-'])]
assert _bad.empty, 'Name column holds non-name values in {} rows'.format(len(_bad))
print('Name content check OK: {} distinct names over {} rows'
      .format(df['Name'].nunique(), len(df)))

# Registration numbers are identifiers, not quantities. Excel silently turns an
# all-digit string into a float (40003761234 -> 4.000376e+10) and drops leading
# zeros, so pin the ID columns to text before writing.
for _c in ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax']:
    df[_c] = df[_c].apply(lambda v: '' if v == '' or pd.isna(v) else str(v).strip())

outpath = os.path.join(scriptfolder, filename)
df.to_excel(outpath, sheet_name='SQL Ready', index=False)

# Read the workbook back and prove Excel did not mangle the identifiers on the way out.
_check = pd.read_excel(outpath, sheet_name='SQL Ready', dtype=str)
_float_ids = _check['InternalID_1'].dropna().astype(str).str.contains(r'[eE]\+|\.0$', regex=True)
assert not _float_ids.any(), 'Excel coerced InternalID_1 to float in {} rows'.format(int(_float_ids.sum()))
print('Round-trip check OK: {} rows re-read, InternalID_1 intact'.format(len(_check)))

print('Saved {} rows to {}'.format(len(df), outpath))
