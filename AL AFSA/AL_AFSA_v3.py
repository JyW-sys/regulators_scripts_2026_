#---- Begin_Librairie ----
# AL AFSA - Autoriteti i Mbikeqyrjes Financiare (Albanian Financial Supervisory Authority)
# Jira: DECD-6833
# Source: https://amf.gov.al  (static ASP pages, Bootstrap accordion "panel-group")
#
# TRANSPORT (v3.1) -- amf.gov.al sits behind Cloudflare.
#   Every panel body IS present in the initial HTML response, so plain requests
#   is enough *when Cloudflare lets the caller through*.  It does not always:
#   the 2026-08-25 production run died on
#       HTTPError: 403 Client Error: Forbidden for url: .../ts_shoqeri_sigurimi.asp
#   while the same call from the dev Mac returned 200 the same day.  Header
#   tuning does not fix it -- bare / Mac-UA / Windows-UA / full browser headers
#   were all measured returning 200 here, so the refusal keys on the client
#   (egress IP + TLS fingerprint), not on what we send.
#
#   So: requests first (fast, and it works on the dev box), and the moment it is
#   refused, fall back to a real Chrome for the rest of the run -- a browser
#   cannot be told apart from a browser.  v2 of this scraper used DrissionPage
#   and worked in production; v3 replaced it with plain requests, which is the
#   regression this restores.  DrissionPage is imported lazily so a box where
#   requests already succeeds never needs it installed.
#
# FAILURE CONTAINMENT (v3.3) -- the browser fallback is NOT enough on the control
#   server: the 2026-09-02 run still died on list 1 (Chrome returned ~631 KB with
#   no accordion, six times in 120s, on the correct URL).  That is unsolved, and
#   the FAILED *.html dump on that box is what will solve it.  What v3.3 does fix
#   is the blast radius: one unreadable list used to discard all seven.  Each list
#   is now attempted independently, a half-parsed list is rolled back to nothing,
#   and only an all-seven failure stops the run.

import os
import re
import ssl
import time
import datetime
import unicodedata

import requests
import pandas as pd
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()
ssl._create_default_https_context = ssl._create_unverified_context


#---- Begin_fileName ----
regulatorName = 'AL AFSA'

print("Running {} Web Scraping Tool v.3".format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)


#---- Begin_Variable ----
regdict = {
    regulatorName + ' 1': 'https://amf.gov.al/ts_shoqeri_sigurimi.asp',
    regulatorName + ' 2': 'https://amf.gov.al/ts_shoqeri_risigurimi.asp',
    regulatorName + ' 3': 'https://amf.gov.al/tt_shoqeri_komisionere.asp',
    regulatorName + ' 4': 'https://amf.gov.al/tt_rregjistrar.asp',
    regulatorName + ' 5': 'https://amf.gov.al/tt_treg.asp',
    regulatorName + ' 6': 'https://amf.gov.al/tsik_fond.asp',
    regulatorName + ' 7': 'https://amf.gov.al/tsik_depositare.asp',
}

ListNameDict = {
    regulatorName + ' 1': 'List of "Insurance Companies"',
    regulatorName + ' 2': 'List of "Reinsurance Companies"',
    regulatorName + ' 3': 'List of "Brokerage Companies"',
    regulatorName + ' 4': 'List of "Registrars"',
    regulatorName + ' 5': 'List of "Regulated Markets"',
    regulatorName + ' 6': 'List of "Investment Funds"',
    regulatorName + ' 7': 'List of "Depository for Collective Investment Undertakings"',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# AFSA supervises insurance, private pensions and securities. Banks are the Bank of
# Albania's remit, so no list here is a bank list even when banks appear as members.
ListLabelDict = {
    regulatorName + ' 1': 2,   # insurance undertakings
    regulatorName + ' 2': 2,   # reinsurance undertakings
    regulatorName + ' 3': 4,   # investment-service firms (securities), some are banks
    regulatorName + ' 4': 4,   # securities registrar / central depository
    regulatorName + ' 5': 4,   # regulated market (stock exchange)
    regulatorName + ' 6': 4,   # collective investment undertakings
    regulatorName + ' 7': 4,   # depositaries for CIUs
}

# These 43 keys are fixed by the project spec. Do not add, remove or rename any of them.
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

SQL_KEYS = list(sqldict.keys())
assert len(SQL_KEYS) == 43, 'schema must have exactly 43 keys, got {}'.format(len(SQL_KEYS))

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36'),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'sq-AL,sq;q=0.9,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
}

# How long Chrome may spend clearing a Cloudflare interstitial before we give up.
CLEARANCE_TIMEOUT = 120

# Albanian administrative centres, used only to lift a City out of the free-text address.
AL_CITIES = ['Tiranë', 'Durrës', 'Vlorë', 'Shkodër', 'Elbasan', 'Korçë', 'Fier', 'Berat',
             'Lushnjë', 'Pogradec', 'Kavajë', 'Gjirokastër', 'Sarandë', 'Lezhë', 'Kukës',
             'Peshkopi', 'Krujë', 'Burrel', 'Laç', 'Patos', 'Kuçovë', 'Librazhd']

TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company']


#---- Begin_Function ----
def norm(s):
    """Accent-stripped, whitespace-collapsed, lower-cased text for tolerant matching.

    AFSA's own editors spell the same label both 'Selise' and 'Selise' with/without the
    diacritic, so labels must never be compared with ==.
    """
    if s is None:
        return ''
    s = unicodedata.normalize('NFKD', str(s))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip().lower()


def clean(s):
    """Collapse whitespace but keep Albanian diacritics intact for stored values."""
    if s is None:
        return ''
    s = unicodedata.normalize('NFKC', str(s)).replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def decode_cfemail(enc):
    """Cloudflare obfuscates every mailto on this site as data-cfemail hex."""
    try:
        r = int(enc[:2], 16)
        return ''.join(chr(int(enc[i:i + 2], 16) ^ r) for i in range(2, len(enc), 2))
    except Exception:
        return ''


def looks_like_challenge(text):
    """True if this is Cloudflare's interstitial rather than the real page."""
    head = (text or '')[:800].lower()
    return ('just a moment' in head
            or 'cf-browser-verification' in head
            or 'challenge-platform' in head
            or 'attention required' in head)


def count_panels(html):
    """How many real accordion panels this HTML contains.

    THE single definition of "we got the page we asked for".  v3.1 had two
    different ones -- the browser wait-loop accepted any HTML containing the
    substring 'panel-default' or 'div class="panel', while get_soup() required
    the CSS selector to match -- so the loop happily returned a wrong page and
    the assert 15 lines later reported it as a site problem.  The substring test
    was far too loose anyway: 'div class="panel' also matches panel-heading,
    panel-body and panel-group (40 hits on a good page, 13 real panels).
    The 2026-08-26 production run failed exactly this way: 632133 bytes of
    something that contained the substring and zero real panels.
    """
    try:
        return len(BeautifulSoup(html or '', 'html.parser')
                   .select('div.panel.panel-default'))
    except Exception:                                    # noqa: BLE001
        return 0


def dump_failure(url, html, page_url=''):
    """Save an unusable response so the next failure is diagnosable, not guessed.

    This box is not the box that fails.  When production rejects a page we cannot
    reproduce here, the only way to learn what it actually received is to keep it.
    """
    try:
        if not os.path.isdir(tempfolder):
            os.makedirs(tempfolder)
        stamp = datetime.datetime.now().strftime('%Y-%m-%d %H.%M.%S')
        slug = re.sub(r'[^A-Za-z0-9]+', '_', url.split('/')[-1])[:40]
        path = os.path.join(tempfolder, 'FAILED {} {}.html'.format(slug, stamp))
        with open(path, 'w', encoding='utf-8', errors='replace') as fh:
            fh.write('<!-- requested: {} -->\n'.format(url))
            fh.write('<!-- browser landed on: {} -->\n'.format(page_url or 'n/a'))
            fh.write(html or '')
        print('       [DIAG] unusable response saved to {}'.format(path))
        return path
    except Exception as exc:                             # noqa: BLE001
        print('       [DIAG] could not save the failing response: {}'
              .format(type(exc).__name__))
        return ''


class Channel(object):
    """Reads amf.gov.al over requests while allowed, through Chrome once refused.

    The switch is sticky and one-way: if Cloudflare has decided this client is
    not welcome over requests, it will keep deciding that, and retrying requests
    on all seven lists would just cost seven more refusals.
    """

    def __init__(self):
        self.mode = 'requests'
        self.page = None

    # -- browser side ---------------------------------------------------------
    def _browser(self):
        """A visible Chrome, started on first need.

        headless MUST stay off: Cloudflare challenges headless Chrome and it
        never clears, which is the trap HK IAHK v1.4 fell into.
        """
        if self.page is not None:
            return self.page
        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
        except ImportError:
            raise RuntimeError(
                'requests was refused by Cloudflare and DrissionPage is not '
                'installed, so there is no way left to reach amf.gov.al.  '
                'Install it on this box:  pip install DrissionPage')
        def base_options():
            options = ChromiumOptions()
            options.headless(False)
            options.set_argument('--disable-blink-features=AutomationControlled')
            options.set_download_path(tempfolder)
            return options

        # Start OUR OWN Chrome instead of attaching to whatever is already
        # listening on the default debug port (127.0.0.1:9222).  Without this,
        # DrissionPage takes over a Chrome the operator happens to have open --
        # with their profile, their extensions and their corporate content-
        # injection agent, none of which we want in the DOM we parse.  Best
        # current explanation for the 2026-08-26 run reading 632133 bytes off a
        # page that is ~125 KB here, though it stays unconfirmed: this box
        # cannot reproduce it.
        #
        # auto_port() picks a free port AND a throwaway user-data dir by itself.
        # Do NOT also call set_user_data_path(): it sets _auto_port = False while
        # auto_port() has already blanked the address, and Chromium then dies on
        # "not enough values to unpack" before the browser ever starts.
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
            # An isolated browser is a hardening measure, not the point of the
            # run.  If this DrissionPage build cannot do it, take a shared Chrome
            # over no data at all -- but say so, because a dirty profile is the
            # prime suspect whenever the accordion then fails to show up.
            print('  [!] isolated Chrome failed to start ({}); retrying on the '
                  'default port. If the accordion is not found, close every '
                  'other Chrome window first.'.format(type(exc).__name__))
            self.page = ChromiumPage(base_options())
        return self.page

    def _browser_html(self, url):
        """Navigate to url and return its HTML once the real accordion is there.

        Acceptance is count_panels() -- the same test get_soup() applies -- so a
        page that will fail the assert can never be returned as a success here.
        """
        page = self._browser()
        deadline = time.time() + CLEARANCE_TIMEOUT
        last = 'never loaded'
        html = ''
        attempt = 0
        while time.time() < deadline:
            attempt += 1
            try:
                page.get(url)
            except Exception as exc:                     # noqa: BLE001
                last = 'navigation raised {}'.format(type(exc).__name__)
            # Poll this navigation for up to ~20s before re-navigating: waiting
            # helps a Cloudflare challenge clear, but it will never turn a wrong
            # page into the right one, so keep re-issuing the request too.
            settle = time.time() + 20
            while time.time() < settle and time.time() < deadline:
                try:
                    html = page.html
                except Exception:
                    html = ''        # mid-navigation; the DOM handle went stale
                if html and not looks_like_challenge(html):
                    if count_panels(html):
                        if attempt > 1:
                            print('       [OK] accordion appeared on browser '
                                  'attempt {}'.format(attempt))
                        return html
                    last = ('loaded {} bytes with no accordion in it'
                            .format(len(html)))
                else:
                    last = 'Cloudflare challenge still on screen'
                time.sleep(2)
        try:
            landed = page.url
        except Exception:                                # noqa: BLE001
            landed = ''
        dump_failure(url, html, landed)
        raise RuntimeError(
            'SKIPPED - Chrome never produced the accordion for {} within {}s '
            'after {} attempt(s) ({}; landed on {}).  The failing HTML was saved '
            'to tempfolder for inspection.  If this box shows an "I am not a '
            'robot" checkbox, tick it by hand once; if the saved file is not the '
            'AFSA page at all, this Chrome is not clean -- close every other '
            'Chrome window and re-run.'
            .format(url, CLEARANCE_TIMEOUT, attempt, last, landed or 'n/a'))

    def _fall_back(self, reason):
        self.mode = 'browser'
        print('  [!] requests was refused ({}). Switching to browser-side '
              'fetching for the rest of the run.'.format(reason))

    # -- public ---------------------------------------------------------------
    def html(self, url):
        if self.mode == 'requests':
            reason = ''
            try:
                resp = requests.get(url, headers=HEADERS, verify=False, timeout=60)
                if resp.status_code == 200:
                    resp.encoding = resp.apparent_encoding or 'utf-8'
                    if looks_like_challenge(resp.text):
                        reason = 'HTTP 200 carrying a Cloudflare challenge page'
                    elif count_panels(resp.text):
                        return resp.text
                    else:
                        # 200 but not the page we asked for -- a soft-404 or a
                        # proxy interstitial.  Worth one try through Chrome
                        # before declaring the list dead.
                        reason = ('HTTP 200 with no accordion ({} bytes)'
                                  .format(len(resp.text)))
                else:
                    reason = 'HTTP {}'.format(resp.status_code)
            except Exception as exc:                     # noqa: BLE001
                reason = type(exc).__name__
            self._fall_back(reason)
        return self._browser_html(url)

    def close(self):
        if self.page is not None:
            try:
                self.page.quit()
            except Exception:
                pass
            self.page = None


channel = Channel()


def get_soup(url):
    """Fetch over whichever transport is currently working, and assert we got a
    real AFSA page (a soft-404 or a proxy error page carries no accordion)."""
    html = channel.html(url)
    soup = BeautifulSoup(html, 'html.parser')
    if not soup.select('div.panel.panel-default'):
        # Both transports now apply count_panels() before handing HTML back, so
        # reaching here means something disagreed with them -- keep the evidence.
        dump_failure(url, html)
        raise RuntimeError('SKIPPED - no accordion panels found at {} (len={}, transport={}); '
                           'the failing HTML was saved to tempfolder'
                           .format(url, len(html), channel.mode))
    return soup


def field_lookup(fields, *keywords):
    """Substring match on accent-stripped labels; returns the first hit."""
    for kw in keywords:
        k = norm(kw)
        for label, value in fields.items():
            if k in norm(label):
                return value
    return ''


def parse_license(text):
    """Pull a licence/decision number and its date out of AFSA's free-text licence line.

    Examples seen live:
      'Nr. 5, datë 31.01.2022 (pa afat). Kjo Licencë zëvendëson Licencën ...'
      'Vendim Nr. 03, dt. 08.06.2000'
      'nr. 1 datë 13.12.2011 (pa afat)'
    """
    lic_no, lic_date = '', ''
    if not text:
        return lic_no, lic_date
    t = clean(text)
    m = re.search(r'(?:nr\.?|nr)\s*[:\s]*([0-9]+(?:/[0-9]+)?)', t, re.I)
    if m:
        lic_no = m.group(1).lstrip('0') or m.group(1)
    d = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{4})', t)
    if d:
        day, mon, yr = int(d.group(1)), int(d.group(2)), int(d.group(3))
        try:
            lic_date = datetime.date(yr, mon, day).strftime('%Y-%m-%d')
        except ValueError:
            lic_date = ''
    return lic_no, lic_date


def pick_city(address):
    a = norm(address)
    for c in AL_CITIES:
        if norm(c) in a:
            return c
    return ''


def split_phone(text):
    """Site merges telephone and fax into one 'Tel./Faks' cell with no separator marking
    which is which, so everything goes to Phone and Fax is left empty on purpose."""
    return clean(text), ''


def add_row(**kw):
    """Single writer for the fixed schema: appends to EVERY key, rejects unknown keys."""
    unknown = set(kw) - set(SQL_KEYS)
    if unknown:
        raise KeyError('unknown sqldict key(s): {}'.format(sorted(unknown)))
    for key in SQL_KEYS:
        sqldict[key].append(kw.get(key, ''))


def parse_panel(panel):
    """Return (name, {label: value}, body_text) for one accordion panel."""
    head = panel.find(['h4', 'h3'])
    name = clean(head.get_text(' ', strip=True)) if head else ''

    # De-obfuscate Cloudflare-protected e-mail addresses in place before reading text.
    for node in panel.select('[data-cfemail]'):
        node.replace_with(decode_cfemail(node.get('data-cfemail', '')))

    fields = {}
    for li in panel.find_all('li'):
        row = li.select_one('div.row')
        if not row:
            continue
        c3 = row.select_one('div.col-md-3')
        c9 = row.select_one('div.col-md-9')
        if c3 is None or c9 is None:
            continue
        label = clean(c3.get_text(' ', strip=True)).rstrip(':').strip()
        if label:
            fields[label] = clean(c9.get_text(' ', strip=True))

    body = panel.select_one('.panel-body')
    body_text = clean(body.get_text(' ', strip=True)) if body else ''
    return name, fields, body_text


def parse_fund_body(body_text):
    """List 6 panels carry no label/value rows, only a sentence of the shape
    'NEN ADMINISTRIMIN E <manager>. DEPOZITAR I FONDIT: <depositary>'."""
    manager, depositary = '', ''
    n = norm(body_text)
    m = re.search(r'nen administrimin e\s+(.*?)(?:\s*depozitar i fondit|$)', n)
    if m:
        # Map the normalised span back onto the original text to keep diacritics.
        start = m.start(1)
        manager = clean(body_text[start:start + len(m.group(1))]).strip(' .-–')
    d = re.search(r'depozitar i fondit\s*:?\s*(.*)$', n)
    if d:
        start = d.start(1)
        depositary = clean(body_text[start:start + len(d.group(1))]).strip(' .-–')
    return manager, depositary


#---- Begin_MainLoop ----
counts = {}
skipped = {}          # reg -> why this list produced nothing

for reg, url in regdict.items():
    listcode = reg.split(' ')[-1]
    regcode = reg.split(' ')[1]
    listname = ListNameDict[reg]
    listlabel = ListLabelDict[reg]

    print('[INFO] {} -> {}'.format(reg, url))

    n_before = len(sqldict['Name'])

    # One unreachable list must not discard the ones that worked.  The 2026-09-02
    # production run died on list 1 -- Chrome returned ~631 KB with no accordion
    # on all six attempts -- and lost all seven lists with it.  Anything raised
    # while fetching OR parsing a list is caught here: the list is rolled back to
    # nothing, named in the summary, and the run carries on with the next one.
    try:
        soup = get_soup(url)
        panels = soup.select('div.panel.panel-default')
        print('       panels rendered by source: {}'.format(len(panels)))

        for panel in panels:
            name, fields, body_text = parse_panel(panel)
            if not name:
                continue

            address = field_lookup(fields, 'Adresa e Selise')
            website = field_lookup(fields, 'Faqja e Internetit')
            email = field_lookup(fields, 'Posta Elektronike')
            cotype = field_lookup(fields, 'Lloji i Pronesise')
            activity = field_lookup(fields, 'Fusha e Aktivitetit')
            lic_raw = field_lookup(fields, 'Licenca', 'Dt. e fillimit te Aktivitetit')
            phone, fax = split_phone(field_lookup(fields, 'Tel./Faks'))
            lic_no, lic_date = parse_license(lic_raw)

            mother = ''
            if listcode == '6':
                # Investment funds are not companies: the panel names the management company.
                mother, depositary = parse_fund_body(body_text)
                if not activity:
                    activity = body_text

            if email.lower().startswith('mailto:'):
                email = email[7:]

            add_row(
                ListLabel=listlabel,
                Typology=listname,
                Name=name,
                InternalID_1=lic_no,
                InternalID_1_type='License Number' if lic_no else '',
                CoType=cotype,
                License_Type=activity,
                Address_1=address,
                City=pick_city(address),
                Cntry='AL',
                Phone=phone,
                Fax=fax,
                Website=website,
                Email=email,
                RegulationType='Regulated',
                RegulationDate=lic_date,
                RegCtry='AL',
                RegCode=regcode,
                ListCode=listcode,
                ListLanguage='SQ',
                ListName=listname,
                ListProcessDate=processdate,
                **{'Name - Mother Company': mother}
            )
    except Exception as exc:                             # noqa: BLE001
        # Discard anything this list half-wrote.  A partial list is worse than an
        # absent one: the entities it did not reach load as if they had been
        # de-listed, and the reconciliation count would agree with itself.
        for key in SQL_KEYS:
            del sqldict[key][n_before:]
        reason = '{}: {}'.format(type(exc).__name__, exc)
        skipped[reg] = reason
        counts[reg] = 0
        print('       !! {} SKIPPED - {}'.format(reg, reason))
        continue

    counts[reg] = len(sqldict['Name']) - n_before
    # Reconcile what we stored against what the page actually rendered.
    if counts[reg] != len(panels):
        print('       [WARN] scraped {} rows but source rendered {} panels'.format(counts[reg], len(panels)))
    else:
        print('       scraped {} rows (matches source)'.format(counts[reg]))

channel.close()   # release Chrome as soon as the last page is read

print('\n[RECONCILIATION] scraped vs source-rendered panels')
print('   transport used: {}'.format(channel.mode))
for reg in regdict:
    print('   {} ({}): {} rows{}'.format(
        reg, ListNameDict[reg], counts.get(reg, 0),
        '   !! SKIPPED' if reg in skipped else ''))
print('   TOTAL: {}'.format(sum(counts.values())))

if skipped:
    print('\n   !! INCOMPLETE - {} of {} lists could not be read:'
          .format(len(skipped), len(regdict)))
    for reg in regdict:
        if reg in skipped:
            print('      {} ({}): {}'.format(reg, ListNameDict[reg], skipped[reg]))
    if sum(counts.values()):
        print('   The workbook below is a PARTIAL load: those entities are '
              'MISSING from it, not de-listed.')
    print('   Check tempfolder for the saved FAILED *.html before loading it.')


#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)

# Skipping a list is survivable; skipping all of them is not.  An empty workbook
# is not a small load, it is a load that de-lists every AFSA entity, so refuse to
# write one and let the run fail loudly instead.
if not sum(counts.values()):
    raise RuntimeError(
        'SKIPPED - all {} lists failed, so nothing was scraped and no workbook '
        'is written. See the FAILED *.html dumps in {}'
        .format(len(regdict), tempfolder))

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# Excel silently turns all-digit strings into floats and eats leading zeros.
for col in TEXT_COLS:
    df[col] = df[col].apply(lambda v: '' if v == '' or pd.isna(v) else str(v))

assert list(df.columns) == SQL_KEYS, 'column order/'"'"'set drifted from the fixed schema'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# Read the workbook back and prove a known all-digit ID survived as text.
_check = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
print('Round-trip: {} rows, {} columns'.format(len(_check), len(_check.columns)))
_ids = [v for v in _check['InternalID_1'].fillna('').tolist() if v]
if _ids:
    print('Round-trip InternalID_1 sample: {!r} (type {})'.format(_ids[0], type(_ids[0]).__name__))
    assert not _ids[0].replace('.', '').endswith('0') or '.' not in _ids[0], 'ID was coerced to a float'
assert list(_check.columns) == SQL_KEYS, 'saved workbook column set drifted'
print('Schema OK: 43 columns, order verified.')

# Say it again last: the operator reads the tail of the log, and a partial file
# that looks clean at the bottom is exactly how a partial load gets shipped.
if skipped:
    print('\n!! THIS FILE IS INCOMPLETE - {} of {} lists were skipped: {}'
          .format(len(skipped), len(regdict),
                  ', '.join(reg for reg in regdict if reg in skipped)))
