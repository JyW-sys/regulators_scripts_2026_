# -*- coding: utf-8 -*-
#---- Begin_Librairie ----
# AL BA v2 -- Bank of Albania / Banka e Shqiperise (DECD-6828)
#
# Rewrite of Al_BA_v1.py. What changed and why:
#   * v1 used Selenium (webdriver.Chrome) + tabula. Both are gone: the production box
#     has no JVM for tabula and the repo convention is requests-first. Everything here
#     is plain requests + pandas.read_excel + pdfplumber. No browser is started.
#   * v1's sqldict carried an ILLEGAL 44th key 'Check'. Removed -- the schema is
#     exactly the 43 project keys and add_row() raises if anything else is passed.
#   * v1 read list 1 (Banks) from the static HTML (h4 -> parent div -> p / tbody).
#     That markup no longer exists: each bank is a collapsed accordion whose body is
#     fetched from https://www.bankofalbania.org/ajxDt.php?...&cis=<id>&apprcss=getciwrp
#     on expand. v2 reads the data-url off each accordion and calls that endpoint
#     directly with requests -- no browser needed.
#   * v1 clicked only the FIRST download link of each page (XPath li[1]), so revoked
#     lists were never actually emitted even though it had a 'Revoked' code path.
#     v2 discovers every link in ul.block-list and classifies it by its link TEXT.
#   * v1 hard-coded positional table indices (tr_s[1] = NUIS, tr_s[2] = Phone ...).
#     v2 maps every field by its LABEL, with Albanian diacritics folded first
#     ("Licence" is really "Licence" with e-diaeresis, so ASCII regexes silently miss it).
#   * v1's PDF reader followed the entry numbering 1,2,3... strictly. The Savings &
#     Loan PDF has TWO sections that each restart at 1, so one entity was dropped
#     silently. v2 detects the section restart (15 -> 16 records on that file).
#
# No filename or document id is hard-coded anywhere: every download URL is resolved
# from the landing page at run time.
import os
import re
import sys
import time
import datetime
import warnings
import unicodedata

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

try:
    from urllib.parse import urljoin
except ImportError:                     # pragma: no cover - py2 never used here
    from urlparse import urljoin

requests.packages.urllib3.disable_warnings()
warnings.filterwarnings('ignore')

#---- Begin_fileName ----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.isdir(tempfolder):
    os.makedirs(tempfolder)

regulatorName = 'AL BA'
now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, now.strftime('%Y-%m-%d %H.%M.%S'))

print('Running {} Web Scraping Tool v.2.0'.format(regulatorName))

#---- Begin_Variable ----
# THE 43-KEY SCHEMA -- DO NOT ADD, REMOVE OR RENAME A SINGLE KEY
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

SCHEMA_KEYS = list(sqldict.keys())
assert len(SCHEMA_KEYS) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SCHEMA_KEYS))

BASE = 'https://www.bankofalbania.org'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-GB,en;q=0.9,sq;q=0.8',
}

# The Bank of Albania publishes the same six registers under an English path and an
# Albanian path. All six English pages exist and were verified live, so the English
# landing page is the primary for every list -- its link TEXT is what tells
# "licensed" from "revoked" from "agents". The Albanian page is kept purely as a
# fallback in case the English one stops resolving; it is NOT used otherwise.
#
# ListCode | ListName                                     | ListLabel | CoType | Typology (regulator's own term) | ListLanguage
LISTS = [
    ('1', 'List of Licensed Banks',
     '/Supervision/Licensed_institutions/Banks/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Banka/',
     '1', 'Bank', 'Banka', 'EN'),
    ('2', 'List of Licensed Foreign Exchange Bureaus',
     '/Supervision/Licensed_institutions/Foreign_Exchange_Bureaus/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Zyra_te_kembimit_valutor/',
     '4', 'Foreign Exchange Bureau', 'Zyra e Kembimit Valutor', 'SQ'),
    ('3', 'List of Licensed Non-bank Financial Institutions',
     '/Supervision/Licensed_institutions/Non-bank_financial_institutions/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Subjekte_Financiare_jobanka/',
     '4', 'Non-bank Financial Institution', 'Subjekt Financiar Jobanke', 'EN'),
    ('4', 'List of Licensed Savings and Loan Associations and their Unions',
     '/Supervision/Licensed_institutions/Savings_and_Loan_Associations_and_their_Unions/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Shoqeri_te_kursim_kreditit_dhe_SHKK/',
     '4', 'Savings and Loan Association', 'Shoqeri e Kursim-Kreditit', 'SQ'),
    ('5', 'List of Licensed Payment Institutions',
     '/Supervision/Licensed_institutions/Payment_Institutions/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Institucionet_e_Pagesave/',
     '4', 'Payment Institution', 'Institucion i Pagesave', 'EN'),
    ('6', 'List of Licensed Electronic Money Institutions',
     '/Supervision/Licensed_institutions/Electronic_Money_Institutions/',
     '/Mbikeqyrja/Subjekte_te_licencuara/Institucionet_e_Parase_Elektronike/',
     '4', 'Electronic Money Institution', 'Institucion i Parase Elektronike', 'EN'),
]

# Agent registers (payment-institution agents, e-money agents) are separate entities
# from the licensed institutions. v1 never collected them. Kept OUT of scope here and
# reported at the end so the ticket owner can decide -- flip to True to include the
# count in the report only (parsing agents would need its own record shape).
INCLUDE_AGENTS = False

# Emit revoked entities with RegulationType 'Revoked'. v1 could not actually reach the
# revoked files. Set to False to ship licensed entities only.
INCLUDE_REVOKED = True

TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'ListCode', 'ListLabel', 'Zip - Mother company', 'Phone - Mother company']

# One consistent value. The sources spell it three ways -- "NUIS/NIPT" (banks accordion),
# "Unique registration number (NUIS/NIPT)" (English workbooks) and "NUIS" (PDFs and
# Albanian workbooks). NUIS and NIPT are the same Albanian taxpayer number, so every
# row is stamped 'NUIS'.
ID_TYPE = 'NUIS'

CITIES = ['TIRANE', 'TIRANA', 'DURRES', 'VLORE', 'SHKODER', 'ELBASAN', 'KORCE', 'FIER',
          'BERAT', 'LUSHNJE', 'KAVAJE', 'POGRADEC', 'GJIROKASTER', 'SARANDE', 'LEZHE',
          'KUKES', 'PESHKOPI', 'BURREL', 'KRUJE', 'LAC', 'LIBRAZHD', 'PERMET',
          'TEPELENE', 'BULQIZE', 'DELVINE', 'GRAMSH', 'KUCOVE', 'MALLAKASTER', 'MAT',
          'MIRDITE', 'PEQIN', 'PUKE', 'SKRAPAR', 'TROPOJE', 'KURBIN', 'RRESHEN',
          'PATOS', 'ROSKOVEC', 'DIVJAKE', 'CERRIK', 'SHIJAK', 'VORE', 'KAMEZ',
          'MEMALIAJ', 'BALLSH', 'ERSEKE', 'LESKOVIK', 'COROVODE', 'BILISHT', 'MALIQ',
          'RROGOZHINE', 'SELENICE', 'HIMARE', 'KONISPOL', 'FINIQ', 'KRUME', 'KLOS',
          'BAJRAM CURRI', 'FUSHE-ARREZ', 'FUSHE ARREZ', 'KOPLIK', 'VAU I DEJES',
          'URA VAJGURORE', 'POLICAN', 'PRRENJAS', 'PERRENJAS', 'FUSHE-KRUJE',
          'FUSHE KRUJE', 'BALLSH', 'ORIKUM', 'HAS', 'DIBER', 'KELCYRE', 'LIBOHOVE']

CNTRY_MAP = {
    'albania': 'AL', 'shqiperi': 'AL', 'shqiperia': 'AL', 'al': 'AL',
    'estonia': 'EE', 'estoni': 'EE', 'italy': 'IT', 'itali': 'IT',
    'turkey': 'TR', 'turqi': 'TR', 'turqia': 'TR', 'austria': 'AT', 'austri': 'AT',
    'greece': 'GR', 'greqi': 'GR', 'kosovo': 'XK', 'kosove': 'XK',
    'macedonia': 'MK', 'maqedoni': 'MK', 'switzerland': 'CH', 'zvicer': 'CH',
    'bulgaria': 'BG', 'bullgari': 'BG', 'hungary': 'HU', 'hungari': 'HU',
    'usa': 'US', 'shba': 'US', 'united states': 'US', 'germany': 'DE', 'gjermani': 'DE',
    'france': 'FR', 'franca': 'FR', 'netherlands': 'NL', 'holande': 'NL',
    'cyprus': 'CY', 'qipro': 'CY', 'malta': 'MT', 'luxembourg': 'LU', 'luksemburg': 'LU',
    'canada': 'CA', 'kanada': 'CA', 'lithuania': 'LT', 'lituani': 'LT',
    'latvia': 'LV', 'letoni': 'LV', 'poland': 'PL', 'poloni': 'PL',
    'romania': 'RO', 'rumani': 'RO', 'serbia': 'RS', 'serbi': 'RS',
    'croatia': 'HR', 'kroaci': 'HR', 'slovenia': 'SI', 'slloveni': 'SI',
    'united kingdom': 'GB', 'britani': 'GB', 'england': 'GB',
    'spain': 'ES', 'spanje': 'ES', 'portugal': 'PT', 'portugali': 'PT',
    'belgium': 'BE', 'belgjike': 'BE', 'ireland': 'IE', 'irlande': 'IE',
    'israel': 'IL', 'izrael': 'IL', 'china': 'CN', 'kine': 'CN',
    'japan': 'JP', 'japoni': 'JP', 'russia': 'RU', 'rusi': 'RU',
    'ukraine': 'UA', 'ukraina': 'UA', 'sweden': 'SE', 'suedi': 'SE',
    'norway': 'NO', 'norvegji': 'NO', 'denmark': 'DK', 'danimarke': 'DK',
    'finland': 'FI', 'finlande': 'FI',
}

#---- Begin_Function ----
def add_row(**kw):
    """Single funnel into sqldict. Appends to EVERY one of the 43 keys and raises on an
    unknown key, so the schema physically cannot drift (this is where v1's 'Check' died)."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        v = kw.get(k, '')
        sqldict[k].append('' if v is None else str(v))
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(sorted(lens)))


def fold(s):
    """Albanian labels carry e-diaeresis and c-cedilla ("Licence", "date", "Adresa e
    selise"). Fold them plus curly quotes/dashes so ONE ASCII regex matches the
    Albanian and the English spelling. Only ever used for MATCHING -- values keep
    their original characters so the .xlsx stays faithful."""
    if s is None:
        return ''
    s = u'{}'.format(s)
    s = s.replace(u'ë', 'e').replace(u'Ë', 'E')
    s = s.replace(u'ç', 'c').replace(u'Ç', 'C')
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in ((u'“', '"'), (u'”', '"'), (u'‘', "'"), (u'’', "'"),
                 (u'–', '-'), (u'—', '-'), (u' ', ' ')):
        s = s.replace(a, b)
    return s


def clean(s):
    """Collapse whitespace, keep the original letters."""
    if s is None:
        return ''
    return re.sub(r'\s+', ' ', u'{}'.format(s)).strip()


def ascii_only(s):
    """Safe to print on the cp1252 Windows console."""
    return re.sub(r'[^\x20-\x7e]', '?', fold(u'{}'.format(s)))


NUM_RE = re.compile(r'^([0-9]{1,4})\s*\.\s*(.*)$')
FAX_RE = re.compile(r'^(?:Tel\s*\.?\s*/\s*fax|Tel\s*/\s*fax|Fax)\s*[:.]?\s*(.*)$', re.I)
TEL_RE = re.compile(r'^(?:Telefon|Tel|Mobile|Cel)\s*[:.]?\s*(.*)$', re.I)
ADDR_RE = re.compile(r'^(?:Adresa|Address)\b\s*[:]?\s*(.*)$', re.I)
NUIS_RE = re.compile(r'^NUIS\s*[:]?\s*(.*)$', re.I)
MAIL_RE = re.compile(r'^(?:E\s*[-]?\s*mail|Email)\s*[:]?\s*(.*)$', re.I)
WEB_RE = re.compile(r'^(?:www|Web)\s*[:]?\s*(.*)$', re.I)
LIC_RE = re.compile(r'^(?:Licenc[ae]|Licence|License|Leje)\b\s*(.*)$', re.I)
SKIP_RE = re.compile(r'^(?:Administrator|Kryetar i Bordit|Drejtori|Pezulluar|Veprimtari|'
                     r'Zyra\b|Aksioner|Ortak|Objekti|Numri|Vendim)', re.I)
REV_RE = re.compile(r'(Revokuar|Revokohet|Shfuqizuar|Hequr licenca|has been revoked|revoked by)', re.I)
HDR_RE = re.compile(r'^[^a-z0-9]{12,}$')
DATE_RE = re.compile(r'(\d{1,2})\s*[./]\s*(\d{1,2})\s*[./]\s*(\d{4})')
LICNO_RE = re.compile(r'\b(?:nr|no)\s*\.?\s*([0-9][0-9A-Za-z/\-]*)', re.I)
PDF_LABELS = [FAX_RE, TEL_RE, ADDR_RE, NUIS_RE, MAIL_RE, WEB_RE, LIC_RE, SKIP_RE]


def is_label(folded):
    for p in PDF_LABELS:
        if p.match(folded):
            return True
    return bool(REV_RE.search(folded))


def norm_date(text, last=False):
    """dd.mm.yyyy -> yyyy-mm-dd. `last=True` takes the final date in the string, which
    is what the revocation sentences need ('... decision no. 5543, date / date\\n08.07.2009.')."""
    hits = DATE_RE.findall(fold(text or ''))
    if not hits:
        return ''
    d, m, y = hits[-1] if last else hits[0]
    try:
        return datetime.date(int(y), int(m), int(d)).strftime('%Y-%m-%d')
    except ValueError:
        return ''


def split_city(name):
    """The PDF registers append the district to the entity name
    ('... SH.P.K., DURRES'). Return the district only when it matches a known Albanian
    city, so City never fills up with fragments of a company name. Name is left intact."""
    f = fold(name).upper().rstrip(' .')
    for sep in (',', ' '):
        if sep in f:
            tail = f.rsplit(sep, 1)[-1].strip(' ."\'')
            if tail in CITIES:
                return tail.title()
    for c in CITIES:
        if f.endswith(' ' + c) or f.endswith(', ' + c):
            return c.title()
    return ''


def split_addr(addr):
    """Address_1 caps at 250 chars; the overflow goes to Address_2 on a word boundary."""
    addr = clean(addr)
    if len(addr) <= 250:
        return addr, ''
    cut = addr.rfind(' ', 0, 250)
    if cut < 100:
        cut = 250
    return addr[:cut].strip(), addr[cut:].strip()[:250]


def split_mother(text):
    """'TRANZIT SH.P.K., Albania' -> ('TRANZIT SH.P.K.', 'AL'). Country only when the
    trailing token is a country we recognise, otherwise the whole string is the name."""
    t = clean(text)
    t = re.sub(r'\s*[\d.,]+\s*%\s*$', '', t).strip(' ,')
    if not t:
        return '', ''
    if ',' in t:
        head, tail = t.rsplit(',', 1)
        code = CNTRY_MAP.get(fold(tail).strip().lower().rstrip('.'), '')
        if code:
            return clean(head), code
    return t, ''


SESSION = requests.Session()
SESSION.verify = False
SESSION.headers.update(HEADERS)


def http_get(url, tries=4, referer=None):
    """The corporate TLS proxy drops connections intermittently; verify=False is the
    proxy, not the site. Retry with backoff."""
    last = None
    hdr = {'Referer': referer} if referer else None
    for i in range(tries):
        try:
            r = SESSION.get(url, timeout=120, headers=hdr)
            r.raise_for_status()
            return r
        except Exception as exc:
            last = exc
            print('      retry {}/{} after {}'.format(i + 1, tries, type(exc).__name__))
            time.sleep(3 * (i + 1))
    raise last


def get_soup(url):
    """The site declares and serves utf-8; decode the bytes explicitly rather than
    trusting r.encoding, so e-diaeresis survives."""
    return BeautifulSoup(http_get(url).content.decode('utf-8', 'replace'), 'html.parser')


def classify(link_text):
    """The only thing that tells the three files apart is the link text."""
    f = fold(link_text).lower()
    if 'revok' in f or 'shfuqizuar' in f or 'revoked' in f or 'revocation' in f:
        return 'revoked'
    if 'agjent' in f or 'agent' in f:
        return 'agents'
    return 'licensed'


def discover(url):
    """Resolve every downloadable register from the landing page at run time.
    Nothing about the filename or its numeric document id is assumed."""
    soup = get_soup(url)
    out = []
    seen = set()
    block = soup.find('ul', {'class': 'block-list'})
    anchors = block.find_all('a', href=True) if block else soup.find_all('a', href=True)
    for a in anchors:
        href = a['href']
        if not re.search(r'\.(pdf|xlsx|xls)(\?|$)', href, re.I):
            continue
        full = urljoin(url, href)
        if full in seen:
            continue
        seen.add(full)
        text = clean(a.get_text(' '))
        out.append({'url': full, 'text': text, 'kind': classify(text),
                    'ext': full.rsplit('.', 1)[-1].split('?')[0].lower()})
    return soup, out


def download(url):
    name = re.sub(r'[^A-Za-z0-9._-]', '_', url.rsplit('/', 1)[-1].split('?')[0])[-120:]
    path = os.path.join(tempfolder, name)
    r = http_get(url)
    with open(path, 'wb') as fh:
        fh.write(r.content)
    return path


#---- Begin_ParserHTML ----
def parse_banks_html(soup, landing_url):
    """List 1 only. Each bank is a collapsed accordion; its body is served by
    ajxDt.php and is referenced by data-url on the inner anchor. v1 relied on Selenium
    firing that request -- we just call it."""
    recs = []
    fq = soup.find('div', {'class': 'fq-list'})
    if fq is None:
        raise AssertionError('list 1: div.fq-list is gone -- the Banks page markup changed')
    blocks = fq.find_all('div', recursive=False)
    for blk in blocks:
        h4 = blk.find('h4')
        anchor = blk.find('a', attrs={'data-url': True})
        if h4 is None or anchor is None:
            continue
        name = clean(h4.get_text(' ')) or clean(anchor.get('title'))
        detail = BeautifulSoup(
            http_get(anchor['data-url'], referer=landing_url).content.decode('utf-8', 'replace'),
            'html.parser')
        rec = {'name': name}
        for p in detail.find_all('p'):
            t = clean(p.get_text(' '))
            if ':' not in t:
                continue
            # One card really does say "Addres s:" -- squeeze the spaces out of the
            # label before testing it, or that bank silently loses its address.
            head = fold(t.split(':', 1)[0]).replace(' ', '').lower()
            if head.startswith('address') or head.startswith('adresa'):
                rec['address'] = t.split(':', 1)[-1].strip()
                break
        shareholder_next = False
        for tr in detail.find_all('tr'):
            cells = [clean(td.get_text(' ')) for td in tr.find_all(['td', 'th'])]
            if len(cells) < 2:
                shareholder_next = False
                continue
            label, value = fold(cells[0]).strip(), cells[1]
            low = label.lower()
            if shareholder_next and 'mother' not in rec:
                mname, mcode = split_mother(cells[0])
                if mname:
                    rec['mother'], rec['mother_cntry'] = mname, mcode
                shareholder_next = False
            if 'shareholders' in low or 'aksioner' in low:
                shareholder_next = True
            elif low.startswith('nuis') or 'nipt' in low:
                rec['nuis'] = value
            elif low.startswith('tel'):
                rec['phone'] = value
            elif low.startswith('fax'):
                rec['fax'] = value
            elif low.startswith('web') or low.startswith('www'):
                rec['website'] = value
            elif low.startswith('e-mail') or low.startswith('email') or low.startswith('e mail'):
                rec['email'] = value
            elif 'licen' in low:
                rec['licence'] = value
        recs.append(rec)
    return recs


#---- Begin_ParserXLSX ----
XL_ADDR = re.compile(r'^(?:Registered address|Adresa e selise|Adresa e seli)', re.I)
XL_BRANCH = re.compile(r'^(?:Address of the branches|Adresa[t]? e deg|Post offices|Zyra)', re.I)
XL_NUIS = re.compile(r'^(?:NUIS|NIPT|Unique registration number)', re.I)
XL_LIC = re.compile(r'^(?:Number and date of (?:the )?(?:actual )?licen|Numri dhe data e licenc)', re.I)
XL_SUSP = re.compile(r'suspen|pezullim', re.I)
XL_SHARE = re.compile(r'^(?:Shareholders|Ortak|Aksioner)', re.I)


def parse_xlsx(path):
    """Lists 3, 5 and 6. Sheet 0 is the register index (No. | Name); sheets 1..N are one
    detail card per institution, in the same order. Names come from the INDEX (that is
    what the site row count is), details from the matching card."""
    book = pd.ExcelFile(path)
    sheets = book.sheet_names
    index = pd.read_excel(path, sheet_name=sheets[0], header=None).fillna('')
    names = []
    for i in range(len(index)):
        row = [clean(c) for c in index.iloc[i].tolist()]
        row = [c for c in row if c]
        if len(row) < 2:
            continue
        if not re.match(r'^\d+(\.\d+)?$', fold(row[0])):
            continue
        names.append(clean(row[1]))
    if len(names) != len(sheets) - 1:
        print('      NOTE index rows={} but detail sheets={} -- pairing by position'.format(
            len(names), len(sheets) - 1))
    recs = []
    matched = 0
    for i, name in enumerate(names):
        rec = {'name': name}
        if i + 1 < len(sheets):
            df = pd.read_excel(path, sheet_name=sheets[i + 1], header=None).fillna('')
            share_next = False
            title = ''
            for r in range(len(df)):
                cells = [clean(c) for c in df.iloc[r].tolist()]
                cells = [c for c in cells if c]
                if not cells:
                    continue
                first = cells[0]
                rest = cells[1] if len(cells) > 1 else ''
                f = fold(first)
                if not title:
                    title = first
                if XL_BRANCH.match(f):
                    share_next = False
                    continue
                if share_next and 'mother' not in rec:
                    mname, mcode = split_mother(first)
                    if mname and not XL_SHARE.match(f):
                        rec['mother'], rec['mother_cntry'] = mname, mcode
                    share_next = False
                if XL_SHARE.match(f):
                    share_next = True
                    if rest and 'mother' not in rec:
                        mname, mcode = split_mother(rest)
                        if mname and '%' not in rest:
                            rec['mother'], rec['mother_cntry'] = mname, mcode
                            share_next = False
                elif XL_ADDR.match(f):
                    val = first.split(':', 1)[-1].strip() if ':' in first else ''
                    rec['address'] = val or rest
                elif XL_NUIS.match(f):
                    rec['nuis'] = rest or (first.split(':', 1)[-1].strip() if ':' in first else '')
                elif XL_LIC.match(f) and not XL_SUSP.search(f):
                    if rest and 'licence' not in rec:
                        rec['licence'] = rest
                elif FAX_RE.match(f):
                    rec['fax'] = rest
                elif TEL_RE.match(f):
                    rec['phone'] = rest
                elif WEB_RE.match(f):
                    rec['website'] = rest
                elif MAIL_RE.match(f):
                    rec['email'] = rest
            # Proof the card really belongs to the index row it was paired with --
            # a row count reconciles just as happily when the cards are off by one.
            key = lambda x: re.sub(r'[^a-z0-9]', '', fold(x).lower())[:8]
            if title and key(title) == key(name):
                matched += 1
        recs.append(rec)
    print('      detail cards provably paired with their index name: {}/{}'.format(matched, len(recs)))
    return recs


#---- Begin_ParserPDF ----
def parse_pdf(path):
    """Every PDF register is a numbered list. Records are followed by sequence
    (1,2,3...) rather than by a loose regex, and a restart at 1 after an ALL-CAPS
    section header is accepted as a NEW section -- the Savings & Loan register has two
    such sections and a strict sequence walker silently drops one entity."""
    lines = []
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        for page in pdf.pages:
            for ln in (page.extract_text() or '').splitlines():
                if ln.strip():
                    lines.append(ln.strip())

    blocks = []
    expect = 1
    cur = None
    prev = ''
    for s in lines:
        f = fold(s)
        m = NUM_RE.match(f)
        start = False
        if m and len(m.group(2)) > 3:
            n = int(m.group(1))
            if n == expect:
                start = True
                expect += 1
            elif n == 1 and blocks and HDR_RE.match(prev):
                start = True
                expect = 2
        if start:
            cur = {'name': [NUM_RE.match(s).group(2)], 'lines': []}
            blocks.append(cur)
        elif cur is not None:
            # A name that wrapped onto a second line is itself ALL CAPS, so it must NOT
            # be tested against HDR_RE here -- doing that truncated the Savings & Loan
            # union at 'UNIONI I SHOQERIVE TE KURSIM KREDITIT "UNIONI SHQIPTAR'.
            # Only lines before the record's first LABEL can extend the name, and every
            # record carries a label before the next section header, so this is safe.
            if not cur['lines'] and not is_label(f):
                cur['name'].append(s)
            else:
                cur['lines'].append(s)
        prev = f

    recs = []
    for blk in blocks:
        rec = {'name': clean(' '.join(blk['name']))}
        body = blk['lines']
        i = 0
        rev_text = []
        while i < len(body):
            s = body[i]
            f = fold(s)
            if REV_RE.search(f):
                rev_text.append(s)
                j = i + 1
                while j < len(body) and not is_label(fold(body[j])):
                    rev_text.append(body[j])
                    j += 1
                i = j
                continue
            m = FAX_RE.match(f)
            if m:
                rec['fax'] = clean(s[len(s) - len(m.group(1)):]) if m.group(1) else ''
                i += 1
                continue
            m = ADDR_RE.match(f)
            if m:
                parts = [s.split(':', 1)[-1] if ':' in s else m.group(1)]
                j = i + 1
                while j < len(body) and not is_label(fold(body[j])) and not NUM_RE.match(fold(body[j])):
                    parts.append(body[j])
                    j += 1
                addr = clean(' '.join(parts))
                # FX bureaus list every branch as "Zyra 1: ... Zyra 2: ...".
                # Keep the head office only.
                addr = re.sub(r'^Zyra\s*1\s*:\s*', '', addr, flags=re.I)
                cut = re.search(r'\bZyra\s*[2-9]\b', fold(addr))
                if cut:
                    addr = addr[:cut.start()].strip(' ,;')
                rec['address'] = addr
                i = j
                continue
            m = TEL_RE.match(f)
            if m:
                val = clean(m.group(1)).strip(':. ')
                if val:
                    rec['phone'] = (rec.get('phone', '') + ', ' + val).strip(', ') if rec.get('phone') else val
                i += 1
                continue
            m = NUIS_RE.match(f)
            if m:
                rec['nuis'] = clean(m.group(1))
                i += 1
                continue
            m = MAIL_RE.match(f)
            if m:
                rec['email'] = clean(s.split(':', 1)[-1]) if ':' in s else clean(m.group(1))
                i += 1
                continue
            m = WEB_RE.match(f)
            if m:
                rec['website'] = clean(s if f.lower().startswith('www') else s.split(':', 1)[-1])
                i += 1
                continue
            m = LIC_RE.match(f)
            if m and 'licence' not in rec:
                rec['licence'] = clean(m.group(1))
                i += 1
                continue
            i += 1
        if rev_text:
            rec['revoked_text'] = clean(' '.join(rev_text))
        recs.append(rec)
    return recs, pages


def is_mojibake(s):
    s = u'{}'.format(s)
    return (u'�' in s) or bool(re.search(u'Ã[ -¿]|â€', s))


#---- Begin_MainLoop ----
summary = []
agent_files = []
unparsed = []

for listcode, listname, en_path, sq_path, listlabel, cotype, typology, listlang in LISTS:
    landing = BASE + en_path
    print('[INFO] list {} : {}'.format(listcode, ascii_only(listname)))
    soup, files = discover(landing)
    if not files and listcode != '1':
        landing = BASE + sq_path
        print('      English page had no downloads -- falling back to the Albanian page')
        soup, files = discover(landing)
    for f in files:
        print('      link [{}] {} -> .{}'.format(f['kind'], ascii_only(f['text'])[:64], f['ext']))

    got = {'licensed': 0, 'revoked': 0}

    # ---- licensed ----
    if listcode == '1':
        recs = parse_banks_html(soup, landing)
        src = 'inline HTML + ajxDt.php'
    else:
        lic = [f for f in files if f['kind'] == 'licensed']
        assert len(lic) == 1, 'list {}: expected 1 licensed file, found {}'.format(listcode, len(lic))
        path = download(lic[0]['url'])
        if lic[0]['ext'].startswith('xls'):
            recs = parse_xlsx(path)
            src = 'xlsx'
        else:
            recs, npages = parse_pdf(path)
            src = 'pdf({}p)'.format(npages)
        os.remove(path)

    for rec in recs:
        name = clean(rec.get('name'))
        if not name:
            continue
        a1, a2 = split_addr(rec.get('address', ''))
        ctype = cotype
        if listcode == '4' and fold(name).upper().startswith('UNION'):
            ctype = 'Union of Savings and Loan Associations'
        add_row(
            Name=name,
            EntryType='Head Office',
            Typology=typology,
            CoType=ctype,
            ListLabel=listlabel,
            InternalID_1=clean(rec.get('nuis', '')),
            InternalID_1_type=ID_TYPE if clean(rec.get('nuis', '')) else '',
            License_Type=(LICNO_RE.search(fold(rec.get('licence', ''))).group(1)
                          if LICNO_RE.search(fold(rec.get('licence', ''))) else ''),
            RegulationDate=norm_date(rec.get('licence', '')),
            Address_1=a1,
            Address_2=a2,
            City=split_city(name) or split_city(a1),
            Cntry='AL',
            Phone=clean(rec.get('phone', '')),
            Fax=clean(rec.get('fax', '')),
            Website=clean(rec.get('website', '')),
            Email=clean(rec.get('email', '')),
            RegulationType='Regulated',
            RegCtry='AL',
            RegCode='BA',
            ListCode=listcode,
            ListName=listname,
            ListLanguage=listlang,
            ListValidityDate=processdate,
            ListProcessDate=processdate,
            **{'Name - Mother Company': clean(rec.get('mother', '')),
               'Cntry - Mother company': rec.get('mother_cntry', '')}
        )
        got['licensed'] += 1

    # ---- revoked ----
    if INCLUDE_REVOKED:
        for f in [f for f in files if f['kind'] == 'revoked']:
            path = download(f['url'])
            if f['ext'].startswith('xls'):
                rrecs = parse_xlsx(path)
            else:
                rrecs, _ = parse_pdf(path)
            os.remove(path)
            for rec in rrecs:
                name = clean(rec.get('name'))
                if not name:
                    continue
                a1, a2 = split_addr(rec.get('address', ''))
                cancel = norm_date(rec.get('revoked_text', ''), last=True)
                if not cancel:
                    unparsed.append((listcode, name))
                add_row(
                    Name=name,
                    EntryType='Head Office',
                    Typology=typology,
                    CoType=cotype,
                    ListLabel=listlabel,
                    InternalID_1=clean(rec.get('nuis', '')),
                    InternalID_1_type=ID_TYPE if clean(rec.get('nuis', '')) else '',
                    License_Type=(LICNO_RE.search(fold(rec.get('licence', ''))).group(1)
                                  if LICNO_RE.search(fold(rec.get('licence', ''))) else ''),
                    RegulationDate=norm_date(rec.get('licence', '')),
                    CancellationDate=cancel,
                    Address_1=a1,
                    Address_2=a2,
                    City=split_city(name) or split_city(a1),
                    Cntry='AL',
                    Phone=clean(rec.get('phone', '')),
                    Fax=clean(rec.get('fax', '')),
                    Website=clean(rec.get('website', '')),
                    Email=clean(rec.get('email', '')),
                    RegulationType='Revoked',
                    RegCtry='AL',
                    RegCode='BA',
                    ListCode=listcode,
                    ListName=listname,
                    ListLanguage=listlang,
                    ListValidityDate=processdate,
                    ListProcessDate=processdate,
                )
                got['revoked'] += 1

    for f in [f for f in files if f['kind'] == 'agents']:
        agent_files.append((listcode, f['text']))

    summary.append((listcode, listname, src, got['licensed'], got['revoked']))
    print('      licensed={} revoked={}'.format(got['licensed'], got['revoked']))

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

assert list(df.columns) == SCHEMA_KEYS, 'column order drifted from the 43-key schema'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))
assert 'Check' not in df.columns, "v1's illegal 'Check' column is back"

# --- content validation: a row count can reconcile perfectly while Name holds the
# --- wrong column. Validate what is IN Name, not just how many rows there are.
bad_empty = df[df['Name'].str.strip() == '']
assert len(bad_empty) == 0, '{} rows have an empty Name'.format(len(bad_empty))
bad_numeric = df[df['Name'].str.match(r'^[\d\s.,/-]+$')]
assert len(bad_numeric) == 0, 'Name holds bare numbers in {} rows, e.g. {}'.format(
    len(bad_numeric), bad_numeric['Name'].head(3).tolist())
bad_date = df[df['Name'].str.match(r'^\d{1,4}[./-]\d{1,2}[./-]\d{2,4}$')]
assert len(bad_date) == 0, 'Name holds dates in {} rows'.format(len(bad_date))
bad_short = df[df['Name'].str.len() < 3]
assert len(bad_short) == 0, 'Name shorter than 3 chars in {} rows'.format(len(bad_short))
bad_label = df[df['Name'].str.contains(r'(?i)^(?:NUIS|Tel|Fax|www|e-?mail|Adres|Licen)\b', regex=True)]
assert len(bad_label) == 0, 'Name holds a field LABEL in {} rows, e.g. {}'.format(
    len(bad_label), bad_label['Name'].head(3).tolist())
print('Name content check: {} rows, all non-empty, non-numeric, non-date, no stray labels.'.format(len(df)))

# --- mojibake gate: a garbled Name passes every row-count check
bad = df[df['Name'].map(is_mojibake)]
assert len(bad) == 0, 'mojibake detected in {} Name values, e.g. {}'.format(
    len(bad), [ascii_only(x) for x in bad['Name'].head(3).tolist()])
diacritic_rows = int(df['Name'].str.contains(u'[ëËçÇ]').sum())
print('Mojibake check: 0 of {} Names garbled; {} Names still carry Albanian e/c diacritics.'.format(
    len(df), diacritic_rows))

assert set(df['RegulationType'].unique()) <= set(['Regulated', 'Revoked']), \
    'unexpected RegulationType: {}'.format(df['RegulationType'].unique())
assert (df['RegulationType'] != '').all(), 'RegulationType is empty on some rows'
assert (df['ListProcessDate'] == processdate).all(), 'ListProcessDate not stamped on every row'
assert set(df['RegCtry'].unique()) == set(['AL']) and set(df['RegCode'].unique()) == set(['BA'])
assert set(df['Cntry'].unique()) == set(['AL'])
assert set(df['InternalID_1_type'].unique()) <= set(['', ID_TYPE]), \
    'InternalID_1_type is not one consistent value: {}'.format(df['InternalID_1_type'].unique())

# --- Excel silently coerces all-digit strings to floats and eats leading zeros
for c in TEXT_COLS:
    df[c] = df[c].astype(str).replace('nan', '')

writer = pd.ExcelWriter(os.path.join(scriptfolder, filename), engine='openpyxl')
df.to_excel(writer, sheet_name='SQL Ready', index=False)
sheet = writer.sheets['SQL Ready']
for ci, col in enumerate(SCHEMA_KEYS, start=1):
    if col in TEXT_COLS:
        for ri in range(2, len(df) + 2):
            sheet.cell(row=ri, column=ci).number_format = '@'
writer.close()
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

#---- Begin_RoundTrip ----
chk = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
chk = chk.fillna('')
assert len(chk) == len(df), 'row count changed on round-trip: {} -> {}'.format(len(df), len(chk))
assert list(chk.columns) == SCHEMA_KEYS, 'column order changed on round-trip'

ids = [v for v in chk['InternalID_1'].tolist() if v.strip()]
assert len(ids) > 0, 'no InternalID_1 survived the round-trip'
float_ids = [v for v in ids if re.match(r'^\d+\.\d+$', v) or v.endswith('.0') or 'E+' in v.upper()]
assert not float_ids, 'InternalID_1 was coerced to float by Excel: {}'.format(float_ids[:3])
src_ids = [v for v in df['InternalID_1'].tolist() if v.strip()]
assert sorted(ids) == sorted(src_ids), 'InternalID_1 values changed on round-trip'
print('Round-trip OK: {} rows x {} cols; {} NUIS values intact, sample {!r}'.format(
    len(chk), len(chk.columns), len(ids), ascii_only(ids[0])))

rt_moji = [ascii_only(v) for v in chk['Name'].tolist() if is_mojibake(v)]
assert not rt_moji, 'mojibake appeared after the Excel round-trip: {}'.format(rt_moji[:3])
rt_diac = int(chk['Name'].str.contains(u'[ëËçÇ]').sum())
assert rt_diac == diacritic_rows, 'Albanian diacritics lost in the workbook: {} -> {}'.format(
    diacritic_rows, rt_diac)
print('Encoding round-trip OK: {} Names still carry e/c diacritics after reading the .xlsx back.'.format(rt_diac))

#---- Begin_Reconciliation ----
print('')
print('--- per-list reconciliation ---')
tot_l = tot_r = 0
for code, name, src, nl, nr in summary:
    print('  list {} {:<62} {:>10}  licensed={:>4}  revoked={:>4}'.format(
        code, ascii_only(name)[:62], src, nl, nr))
    tot_l += nl
    tot_r += nr
print('  TOTAL licensed={}  revoked={}  rows={}'.format(tot_l, tot_r, len(df)))
assert tot_l + tot_r == len(df), 'per-list totals do not add up to the sheet'

print('')
print('--- field fill rates ---')
for c in ['InternalID_1', 'Address_1', 'City', 'Phone', 'Fax', 'Website', 'Email',
          'License_Type', 'RegulationDate', 'CancellationDate', 'Name - Mother Company']:
    n = int((df[c].astype(str).str.strip() != '').sum())
    print('  {:<24} {:>5}/{} ({:.0f}%)'.format(c, n, len(df), 100.0 * n / max(len(df), 1)))

print('')
print('--- rows per ListName ---')
for k, v in df['ListName'].value_counts().items():
    print('  {:<64} {}'.format(ascii_only(k)[:64], v))

if agent_files:
    print('')
    print('--- AGENT registers found and SKIPPED (INCLUDE_AGENTS=False) ---')
    for code, text in agent_files:
        print('  list {}: {}'.format(code, ascii_only(text)))
if unparsed:
    print('')
    print('--- revoked rows with no parseable CancellationDate: {} ---'.format(len(unparsed)))
    for code, name in unparsed[:10]:
        print('  list {}: {}'.format(code, ascii_only(name)[:70]))
print('')
print('DONE {}'.format(filename))
