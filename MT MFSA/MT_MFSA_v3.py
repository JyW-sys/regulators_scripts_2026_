#---- Begin_Librairie ----
# =============================================================================
# MT MFSA - Malta Financial Services Authority
# DECD-6834 : List 1 "License Holders"
# Source app : https://fsr.mfsa.mt  (iframed by https://www.mfsa.mt/financial-services-register/)
# Backend    : plain JSON endpoints
#
# TRANSPORT (v3.1) -- fsr.mfsa.mt sits behind Cloudflare.
#   The JSON endpoints answer plain requests *when Cloudflare lets the caller
#   through*.  It does not always: the 2026-08-21 production run died on
#       RuntimeError: giving up on .../getParentLicenceTypes params=None : HTTP 403
#   on the very first call, while the same endpoint returned 200 from the dev
#   Mac.  Measured here: bare / Mac-UA / Windows-UA / full browser headers /
#   full+XHR headers ALL returned 200, so the refusal keys on the client
#   (egress IP + TLS fingerprint), not on the headers we send -- no amount of
#   header tuning fixes it.
#
#   So: requests first, and once refused, every later call is issued as a
#   same-origin XHR from inside a real Chrome sitting on fsr.mfsa.mt.  That is
#   the pattern proven in production by HK IAHK v1.5, which hit the identical
#   "works on the Mac, 403s on the control server" split.  DrissionPage is
#   imported lazily so a box where requests already works never needs it.
# =============================================================================
import os
import re
import time
import json
import datetime

import requests
import pandas as pd

requests.packages.urllib3.disable_warnings()  # corporate TLS proxy

#---- Begin_fileName ----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production (.py)
except NameError:
    scriptfolder = os.getcwd()                                   # notebook

os.chdir(scriptfolder)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = 'MT MFSA SQL Ready {}.xlsx'.format(now.strftime('%Y-%m-%d %H.%M.%S'))

#---- Begin_Variable ----
BASE = 'https://fsr.mfsa.mt'
EP_PARENTS = BASE + '/LicenceTypes/getParentLicenceTypes'
EP_SUBS    = BASE + '/LicenceTypes/getLicenceTypesByParentId'
EP_HOLDERS = BASE + '/Licences/getLicenceHoldersByLicenceTypeId'

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                   'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': BASE + '/',
    'X-Requested-With': 'XMLHttpRequest',
}

# The app rate-limits hard (HTTP 429) above roughly 3 req/s. Stay serial + polite.
REQ_DELAY = 0.4
MAX_RETRY = 6

# How long Chrome may spend clearing a Cloudflare interstitial before we give up.
CLEARANCE_TIMEOUT = 120
# Statuses worth asking again for; anything else is a real answer, not weather.
RETRY_STATUSES = (0, -1, 403, 408, 429, 500, 502, 503, 504)
BROWSER_ATTEMPTS = 4
RETRY_BASE_DELAY = 3          # seconds, doubled each attempt: 3, 6, 12

# Issued from inside the page, so it inherits the origin, its cookies and the
# browser's own TLS fingerprint. Synchronous on purpose: run_js returns the
# finished response rather than a promise we would have to poll.
SYNC_XHR_JSON = """
var xhr = new XMLHttpRequest();
xhr.open('GET', arguments[0], false);
xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
try { xhr.send(null); }
catch (e) { return JSON.stringify({status: -1, body: '' + e}); }
return JSON.stringify({status: xhr.status, body: xhr.responseText});
"""

# ---- ticket-level constants (hard-coded on purpose: never derive RegCode by
# ---- splitting a dict key -- that is how sibling notebooks ended up emitting a
# ---- different regulator's code entirely).
REGCTRY   = 'MT'
REGCODE   = 'MFSA'
LISTCODE  = '1'
LISTNAME  = 'License Holders'
LISTLANG  = 'EN'
# MFSA is a single authority covering banking + insurance + investment + pensions
# + trustees. List 1 is ONE combined register spanning banks and insurers, so 3.
LISTLABEL = '3'

# Observed licence statuses -> RegulationType.
# Anything not listed is treated as NOT regulated and logged loudly.
STATUS_REGULATED = 'Licence Authorised'

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SCHEMA = list(sqldict.keys())
assert len(SCHEMA) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SCHEMA))

#---- Begin_Function ----
def looks_like_challenge(text):
    """True if this is Cloudflare's interstitial rather than the payload."""
    head = (text or '')[:800].lower()
    return ('just a moment' in head
            or 'cf-browser-verification' in head
            or 'challenge-platform' in head
            or 'attention required' in head)


def build_url(url, params):
    """Absolute URL with the query baked in -- the browser XHR takes one string."""
    if not params:
        return url
    try:
        from urllib.parse import urlencode
    except ImportError:                               # pragma: no cover (py2)
        from urllib import urlencode
    return '{}?{}'.format(url, urlencode(params))


class Channel(object):
    """Reads fsr.mfsa.mt over requests while allowed, through Chrome once refused.

    The switch is sticky and one-way. With ~12.5k holders spread over hundreds
    of authorisation types, re-testing requests on every call would cost one
    refusal per call for the whole run.
    """

    def __init__(self):
        self.mode = 'requests'
        self.page = None
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.session.verify = False
        # The app sets an 'MFSA' cookie plus an antiforgery cookie on the home
        # page; the JSON endpoints answer 400 without them.
        try:
            self.session.get(BASE + '/', timeout=90)
        except Exception:
            pass                                       # the fallback still has a chance

    # -- browser side ---------------------------------------------------------
    def _browser(self):
        """A visible Chrome parked on fsr.mfsa.mt, started on first need.

        headless MUST stay off: Cloudflare challenges headless Chrome and it
        never clears.
        """
        if self.page is not None:
            return self.page
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            raise RuntimeError(
                'requests was refused by Cloudflare and DrissionPage is not '
                'installed, so there is no way left to reach fsr.mfsa.mt.  '
                'Install it on this box:  pip install DrissionPage')
        def base_options():
            options = ChromiumOptions()
            options.headless(False)
            options.set_argument('--disable-blink-features=AutomationControlled')
            return options

        # Start OUR OWN Chrome rather than attaching to whatever already listens
        # on the default debug port (127.0.0.1:9222).  A shared Chrome brings the
        # operator's profile and extensions with it, and every XHR here fires
        # from that document -- AL AFSA hit exactly that on 2026-08-26.
        #
        # auto_port() allocates a free port AND a throwaway user-data dir itself.
        # Do NOT also call set_user_data_path(): it flips _auto_port back to False
        # after auto_port() has already blanked the address, and Chromium then
        # dies on "not enough values to unpack" before the browser starts.
        options = base_options()
        try:
            options.auto_port(True)
            options.set_argument('--disable-extensions')
            options.set_argument('--no-first-run')
        except Exception:                                # noqa: BLE001
            options = base_options()     # older DrissionPage: option absent
        try:
            self.page = ChromiumPage(options)
        except Exception as exc:                         # noqa: BLE001
            print('  [!] isolated Chrome failed to start ({}); retrying on the '
                  'default port. If Cloudflare will not clear, close every other '
                  'Chrome window first.'.format(type(exc).__name__))
            self.page = ChromiumPage(base_options())
        self._anchor()
        return self.page

    def _anchor(self):
        """Park the browser on the app origin and wait out any challenge.

        Every later XHR fires from this document, so it must be settled on
        fsr.mfsa.mt before anything else runs.
        """
        self.page.get(BASE + '/')
        deadline = time.time() + CLEARANCE_TIMEOUT
        while time.time() < deadline:
            try:
                html = self.page.html
            except Exception:
                html = ''                              # mid-navigation
            if html and not looks_like_challenge(html):
                return
            time.sleep(2)
        raise RuntimeError(
            'SKIPPED - Chrome could not clear Cloudflare on {} within {}s. If '
            'this box shows an "I am not a robot" checkbox it needs ticking by '
            'hand once, or CLEARANCE_TIMEOUT raising.'.format(BASE, CLEARANCE_TIMEOUT))

    def _run(self, url):
        """One browser-side XHR, re-anchoring once if the page context is lost."""
        page = self._browser()
        try:
            return json.loads(page.run_js(SYNC_XHR_JSON, url, timeout=180))
        except Exception as err:
            print('   [!] browser context lost on {} ({}); re-anchoring and '
                  'retrying once'.format(url, type(err).__name__))
            self._anchor()
            return json.loads(page.run_js(SYNC_XHR_JSON, url, timeout=180))

    def _browser_json(self, url):
        """Fetch url in the browser, retried through transient refusals."""
        delay = RETRY_BASE_DELAY
        detail = ''
        for attempt in range(1, BROWSER_ATTEMPTS + 1):
            payload = self._run(url)
            status = payload.get('status')
            body = payload.get('body') or ''
            if status == 200:
                if looks_like_challenge(body):
                    detail = 'HTTP 200 carrying a Cloudflare challenge page'
                else:
                    try:
                        return json.loads(body)
                    except ValueError:
                        # soft-404 guard: the app answers errors as HTML
                        detail = 'HTTP 200 but body is not JSON -- first 120 bytes: {!r}'.format(body[:120])
            else:
                detail = 'HTTP {}'.format(status)
                if looks_like_challenge(body):
                    detail += ' carrying a Cloudflare challenge page'
                elif body:
                    detail += ' -- first 120 bytes: {!r}'.format(body[:120])

            if status not in RETRY_STATUSES or attempt == BROWSER_ATTEMPTS:
                break
            print('   attempt {} of {} got {}; retrying in {}s'.format(
                attempt, BROWSER_ATTEMPTS, detail, delay))
            time.sleep(delay)
            delay *= 2
            if attempt >= 2:
                self._anchor()      # the refusal may be a re-armed challenge
        raise RuntimeError('the browser itself got {} for {}'.format(detail, url))

    def _fall_back(self, reason):
        self.mode = 'browser'
        print('  [!] requests was refused ({}). Switching to browser-side '
              'fetching for the rest of the run.'.format(reason))

    # -- public ---------------------------------------------------------------
    def json(self, url, params=None):
        """Parsed JSON from whichever transport is currently working."""
        full = build_url(url, params)
        if self.mode == 'requests':
            last = None
            for attempt in range(MAX_RETRY):
                try:
                    r = self.session.get(url, params=params, timeout=90)
                    if r.status_code == 200:
                        ctype = r.headers.get('content-type', '')
                        if 'json' not in ctype.lower():
                            raise ValueError('non-JSON content-type {!r} from {}'.format(ctype, r.url))
                        return r.json()
                    last = 'HTTP {}'.format(r.status_code)
                    # 403 is Cloudflare refusing this client outright. Retrying
                    # requests cannot help -- go to the browser now rather than
                    # burning MAX_RETRY * 5s first.
                    if r.status_code == 403:
                        break
                except Exception as exc:              # noqa: BLE001
                    last = repr(exc)
                if attempt < MAX_RETRY - 1:
                    time.sleep(5 * (attempt + 1))     # 429 needs real cooldown
            self._fall_back(last)
        return self._browser_json(full)

    def close(self):
        if self.page is not None:
            try:
                self.page.quit()
            except Exception:
                pass
            self.page = None


channel = Channel()


def get_json(session, url, params=None):
    """Kept for call-site compatibility; `session` is now owned by the channel."""
    return channel.json(url, params)


def clean(value):
    """Collapse whitespace / NBSP, strip. None -> ''."""
    if value is None:
        return ''
    text = str(value).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def regulation_type(status):
    """Positive register -> 'Regulated'. Everything else is a non-positive
    status (surrendered / withdrawn / suspended / in liquidation ...)."""
    return 'Regulated' if clean(status) == STATUS_REGULATED else clean(status)


def add_row(**kw):
    """Single entry point. Appends to EVERY key; raises on an unknown key."""
    unknown = set(kw) - set(SCHEMA)
    if unknown:
        raise KeyError('unknown column(s): {}'.format(sorted(unknown)))
    for key in SCHEMA:
        sqldict[key].append(clean(kw.get(key, '')))


def licence_label(lic):
    """Reproduce the label the site renders in the Authorisation column."""
    name = clean(lic.get('licenceTypeName'))
    if lic.get('checkForParentLicence') and not lic.get('moreThanOneParent'):
        parent = clean(lic.get('parentLicenceHolderName'))
        if parent:
            desc = clean(lic.get('parentTypeDescription'))
            return '{} - {} {}'.format(name, desc, parent).strip()
    return name

#---- Begin_MainLoop ----
session = channel.session      # kept so existing call sites read unchanged

# --- 1. discover the Sector list (never hard-code an enumeration) -------------
parents = get_json(session, EP_PARENTS)
if not parents:
    raise RuntimeError('SKIPPED - getParentLicenceTypes returned no sectors')
print('Sectors discovered: {}'.format(len(parents)))

# --- 2. discover the Authorisation list under each Sector --------------------
jobs = []
for parent in parents:
    subs = get_json(session, EP_SUBS,
                    {'parentLicenceTypeId': parent['parentLicenceTypeId']})
    time.sleep(REQ_DELAY)
    if not subs:
        print('   NOTE: sector {!r} has no authorisations'.format(parent['parentLicenceTypeName']))
    for sub in subs:
        jobs.append((clean(parent['parentLicenceTypeName']),
                     sub['licenceTypeId'],
                     clean(sub['licenceTypeName'])))
print('Authorisation types discovered: {}'.format(len(jobs)))

# --- 3. pull the holders of every Authorisation ------------------------------
per_type = {}
per_sector = {}
status_counts = {}
failed_types = []
declared_holder_entries = 0

for idx, (sector, ltid, ltname) in enumerate(jobs, 1):
    try:
        holders = get_json(session, EP_HOLDERS, {'licenceTypeId': ltid})
    except Exception as exc:                          # noqa: BLE001
        failed_types.append((sector, ltid, ltname, repr(exc)))
        print('   FAILED {} / {} (id={}): {}'.format(sector, ltname, ltid, exc))
        time.sleep(REQ_DELAY)
        continue

    declared_holder_entries += len(holders)
    rows_here = 0

    for holder in holders:
        name = clean(holder.get('licenceHolderName'))
        if not name:
            continue
        company_id = clean(holder.get('companyId'))
        person_id  = clean(holder.get('identification'))

        # One row per licence, exactly as the site renders it. NO de-duplication:
        # a holder legitimately shows N lines when it holds N authorisations.
        for lic in holder.get('licences', []) or []:
            status = clean(lic.get('licenceStatus'))
            status_counts[status] = status_counts.get(status, 0) + 1
            add_row(
                ListLabel=LISTLABEL,
                Name=name,
                InternalID_1=company_id,
                InternalID_1_type='MBR Registration Code' if company_id else '',
                InternalID_2=person_id,
                InternalID_2_type='MFSA Authorised Person ID' if person_id else '',
                InternalID_3=ltid,
                InternalID_3_type='MFSA Licence Type ID',
                CoType=sector,
                License_Type=licence_label(lic),
                Cntry='MT',
                RegulationType=regulation_type(status),
                RegCtry=REGCTRY,
                RegCode=REGCODE,
                ListCode=LISTCODE,
                ListLanguage=LISTLANG,
                ListName=LISTNAME,
                ListProcessDate=processdate,
            )
            rows_here += 1

    per_type[(sector, ltname)] = rows_here
    per_sector[sector] = per_sector.get(sector, 0) + rows_here
    time.sleep(REQ_DELAY)
    if idx % 25 == 0:
        print('   ... {}/{} authorisation types done'.format(idx, len(jobs)))

channel.close()   # release Chrome as soon as the last endpoint is read

# --- 4. reconciliation -------------------------------------------------------
print('\n================ RECONCILIATION ================')
print('  transport used: {}'.format(channel.mode))
for sector in sorted(per_sector):
    print('  {:<70} {:>6}'.format(sector[:70], per_sector[sector]))
print('  {:<70} {:>6}'.format('TOTAL licence rows built', sum(per_sector.values())))
print('  {:<70} {:>6}'.format('Holder entries returned by the API', declared_holder_entries))
print('  {:<70} {:>6}'.format('Authorisation types with 0 rows',
                              sum(1 for v in per_type.values() if v == 0)))

print('\nLicence status breakdown (source-declared):')
for status in sorted(status_counts, key=lambda s: -status_counts[s]):
    flag = '' if status == STATUS_REGULATED else '   <-- NOT "Regulated"'
    print('  {:<55} {:>6}{}'.format(status[:55], status_counts[status], flag))

if failed_types:
    print('\n*** {} AUTHORISATION TYPE(S) COULD NOT BE FETCHED - OUTPUT IS SHORT ***'.format(len(failed_types)))
    for sector, ltid, ltname, err in failed_types:
        print('   {} / {} (id={}) : {}'.format(sector, ltname, ltid, err))
else:
    print('\nAll {} authorisation types fetched successfully.'.format(len(jobs)))

lengths = {k: len(v) for k, v in sqldict.items()}
assert len(set(lengths.values())) == 1, 'ragged sqldict: {}'.format(lengths)
print('Every one of the {} columns holds {} values.'.format(len(SCHEMA), sum(lengths.values()) // len(SCHEMA)))

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# --- schema gate: exact 43 keys, exact order ---------------------------------
assert list(df.columns) == SCHEMA, 'column order/name drift before to_excel'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

# --- Excel would coerce all-digit strings ('C 12345' survives, but bare
# --- numbers and leading zeros do not). Force the identifier-ish columns to text.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3',
             'Zip', 'Phone', 'Fax', 'LEI Code', 'BIC SWIFT Code',
             'Zip - Mother company', 'Phone - Mother company']
for col in TEXT_COLS:
    df[col] = df[col].astype(str).replace('nan', '')

with pd.ExcelWriter(os.path.join(scriptfolder, filename), engine='xlsxwriter') as writer:
    df.to_excel(writer, sheet_name='SQL Ready', index=False)
    book = writer.book
    sheet = writer.sheets['SQL Ready']
    text_fmt = book.add_format({'num_format': '@'})
    for col in TEXT_COLS:
        pos = SCHEMA.index(col)
        sheet.set_column(pos, pos, 18, text_fmt)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# --- read back and assert the identifiers round-tripped as text --------------
check = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
assert len(check) == len(df), 'row count changed on round-trip: {} -> {}'.format(len(df), len(check))
assert list(check.columns) == SCHEMA, 'column drift on round-trip'
sample = check.loc[check['InternalID_1'].astype(str).str.strip() != '', 'InternalID_1']
if len(sample):
    val = str(sample.iloc[0]).strip()
    assert 'e+' not in val.lower() and not val.endswith('.0'), \
        'InternalID_1 was coerced to a number: {!r}'.format(val)
    print('Round-trip OK - InternalID_1 sample reads back as {!r}'.format(val))
else:
    print('Round-trip OK - no InternalID_1 values to sample')
