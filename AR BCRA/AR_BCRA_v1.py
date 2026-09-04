#---- Begin_Librairie ----
# AR BCRA - Banco Central de la Republica Argentina
# DECD-6965  (8 lists)
#
# Source shapes, all MEASURED on 2026-09-02 (not guessed):
#   1 Financial Institutions   -> site-internal JSON API, list + 1 detail call per entity (73)
#   2 Exchange Houses          -> site-internal JSON API                                   (7)
#   3 Interoperable e-wallets  -> site-internal JSON API                                   (91)
#   4 Public guarantee funds   -> static HTML table                                        (17 ES / 16 EN)
#   5 MSME financing platforms -> JSON embedded inline in the HTML (div#registro[hidden])  (7)
#   6 Payment service providers-> site-internal JSON API, tipoPSP=1 per the ticket URL     (227)
#   7 Representatives of foreign financial institutions -> static HTML table               (8 ES / 4 EN)
#   8 Electronic clearing houses / EFT scheme managers  -> hand-written <ul><li>           (6)
#
# NOTE on api.bcra.gob.ar: the *documented* public API does NOT expose an entity register
# (/entidades/... 404, /estadisticas/... 410 Gone). The real source is the website's own
# https://www.bcra.gob.ar/api/endpoints/*.php, which is what the page's own JS calls.
# Only four such endpoints exist; lists 4, 5, 7 and 8 have none and are parsed from HTML.
#
# NOTE on /en/ vs /es/ for the two static tables: the English pages are STALE.
#   list 4: ES 17 rows, EN 16  -> EN is missing 51017 Fondo de Garantia Santa Fe Produce
#   list 7: ES  8 rows, EN  4  -> EN is missing 4 entities, and corrupts one code cell
#                                 into the literal text "Item No. 30013"
# Dropping real regulated entities because a translation lagged is not acceptable, so
# lists 4 and 7 are scraped from the Spanish pages. Every other list is taken from the
# ticket's own /en/ URL. See README_AR_BCRA.md.

import os
import re
import ssl
import json
import time
import html
import datetime
import unicodedata

import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup

# Corporate TLS proxy on the Mac dev box: the chain does not validate.
ssl._create_default_https_context = ssl._create_unverified_context
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


#---- Begin_fileName ----
regulatorName = 'AR BCRA'

print('Running {} Web Scraping Tool v.1.0'.format(regulatorName))

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
BASE = 'https://www.bcra.gob.ar'
API = BASE + '/api/endpoints/'

# ---- Template fields. Fixed values with a fixed shape - the three tokens of
# ---- '<CC> <AGENCY> <listnr>':
# ----     RegCtry  = 2-letter country code, NOT the country name
# ----     RegCode  = the agency code alone, 'BCRA', NOT 'AR BCRA'
# ----     ListCode = the bare ticket ListNr, '1', NOT 'AR BCRA 1'
# ---- Hard-coded on purpose; deriving them at runtime is how sibling notebooks
# ---- ended up emitting another regulator's code.
REGCTRY = 'AR'
REGCODE = 'BCRA'

# One entry per ticket ListNr, in the ticket's own order.
#   'url'      - the page/endpoint actually scraped (see the /en/ vs /es/ note above)
#   'ticket'   - the URL as written in the Jira description, kept for traceability
#   'label'    - ListLabel: 1 bank, 2 insurance, 3 both, 4 everything else
#   'lang'     - ListLanguage, i.e. the language of the page actually scraped
#   'expected' - row count MEASURED on 2026-09-02. Drift is warned about, never asserted:
#                a regulator adding or removing an entity is legitimate.
LISTS = {
    1: dict(listname='Financial Institutions', label=1, lang='EN', expected=73,
            ticket=BASE + '/en/financial-institutions-2/',
            url=API + 'entidades-financieras.php?action=list&lang=en'),
    2: dict(listname='Exchange Houses', label=4, lang='EN', expected=7,
            ticket=BASE + '/en/exchange-houses/',
            url=API + 'casas-de-cambio.php?lang=en'),
    3: dict(listname='Interoperable e-wallets', label=4, lang='EN', expected=91,
            ticket=BASE + '/en/interoperable-e-wallets/',
            url=API + 'billeteras.php?action=list&lang=en'),
    4: dict(listname='Public guarantee funds', label=4, lang='ES', expected=17,
            ticket=BASE + '/en/public-guarantee-funds/',
            url=BASE + '/fondos-de-garantia-de-caracter-publico/'),
    5: dict(listname='Platforms for MSME Financing', label=4, lang='EN', expected=7,
            ticket=BASE + '/en/registration-of-platforms-for-msme-financing/',
            url=BASE + '/en/registration-of-platforms-for-msme-financing/'),
    6: dict(listname='Payment service providers', label=4, lang='EN', expected=227,
            ticket=BASE + '/en/payment-service-provider-registration-results-by-type/?tipoPSP=1',
            url=API + 'proveedores-psp.php?tipoPSP=1&lang=en'),
    7: dict(listname='Representatives of foreign financial institutions', label=1, lang='ES', expected=8,
            ticket=BASE + '/en/representatives-of-foreign-financial-institutions/',
            url=BASE + '/representantes-de-entidades-financieras-del-exterior/'),
    8: dict(listname='Electronic clearing houses and electronic funds transfer managers',
            label=4, lang='EN', expected=6,
            ticket=BASE + '/en/electronic-clearing-houses-and-electronic-funds-transfer-managers/',
            url=BASE + '/en/electronic-clearing-houses-and-electronic-funds-transfer-managers/'),
}

# List 4's Spanish table ships NO header row (its first <tr> is empty), so its columns can
# only be taken positionally. The English page carries the labels for the same column
# order, so the labels are read from there each run and asserted before ES is parsed --
# if BCRA ever reorders the columns this fires instead of silently mis-mapping.
L4_HEADERS = ['code', 'denomination', 'tax id number', 'domicile', 'city', 'province',
              'zip code', 'telephone']

# List 7's Spanish table DOES carry labels (2nd header row), so it is mapped by label.
L7_LABELS = {'pais': 'country', 'codigo entidad': 'code', 'entidad representada': 'name',
             'domicilio': 'address', 'localidad': 'city', 'telefono': 'phone'}

# Spanish country names -> ISO-3166 alpha-2. Only list 7 needs this; every value seen on
# 2026-09-02 is covered and an unmapped one is reported loudly rather than guessed.
CNTRY_ES = {
    'alemania': 'DE', 'brasil': 'BR', 'estados unidos de america': 'US',
    'estados unidos': 'US', 'francia': 'FR', 'gran bretana': 'GB',
    'reino unido': 'GB', 'paises bajos': 'NL', 'holanda': 'NL', 'panama': 'PA',
    'espana': 'ES', 'italia': 'IT', 'japon': 'JP', 'china': 'CN', 'suiza': 'CH',
    'canada': 'CA', 'chile': 'CL', 'uruguay': 'UY', 'argentina': 'AR',
}

# List 8 has no table and no codes - only two Spanish group headings above two <ul>s.
# Matched on a normalised keyword so an accent or a wording tweak does not break it.
L8_GROUPS = [
    ('camaras electronicas', 'Electronic clearing house (CEC)'),
    ('administradores de esquemas', 'Electronic funds transfer payment scheme manager'),
]

# Columns that hold identifiers, not quantities. Excel silently turns an all-digit string
# into a float (30715084291 -> 3.07151e+10) and eats leading zeros - and BCRA phone
# numbers really do look like '000043294201'. Pinned to text before writing, then the
# workbook is read back and asserted.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company', 'ListCode']

CUIT_RE = re.compile(r'^\d{2}-?\d{8}-?\d$')

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

SQL_KEYS = list(sqldict.keys())
assert len(SQL_KEYS) == 43, 'schema must be exactly 43 keys, got {}'.format(len(SQL_KEYS))

session = requests.Session()
session.headers.update({
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'),
    'Accept-Language': 'en-US,en;q=0.9',
})

summary = []          # (listnr, listname, rows, expected)
warnings_seen = []    # non-fatal anomalies, reprinted in the run summary


#---- Begin_Function ----
def add_row(**kw):
    """Single writer for sqldict. Appends to EVERY one of the 43 keys on every record
    and raises on an unknown key, so column drift is impossible."""
    unknown = set(kw) - set(SQL_KEYS)
    if unknown:
        raise KeyError('add_row got unknown column(s): {}'.format(sorted(unknown)))
    for k in SQL_KEYS:
        v = kw.get(k, '')
        sqldict[k].append('' if v is None else str(v))
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(lens))


def warn(msg):
    warnings_seen.append(msg)
    print('   ** {}'.format(msg))


def ascii_slug(s, limit=70):
    """cp1252 console safety: the Windows control server raises UnicodeEncodeError on
    any non-cp1252 byte, so nothing scraped is ever printed raw."""
    return re.sub(r'[^\x20-\x7e]', '?', str(s or ''))[:limit]


def clean(v):
    """NBSP -> space, collapse runs of whitespace, strip. Also normalises the ints and
    bools the JSON endpoints hand back into text, so nothing reaches Excel as a number."""
    if v is None or v is False:
        return ''
    if v is True:
        return 'True'
    s = str(v).replace('\xa0', ' ').replace('​', '')
    s = html.unescape(s)
    return re.sub(r'\s+', ' ', s).strip()


def norm(s):
    """NFKD + drop combining marks + collapse + lowercase. Spanish labels and country
    names mix accented and unaccented spellings; never compare them with ==."""
    s = unicodedata.normalize('NFKD', clean(s))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s).strip().lower()


def get(url, as_json=False, tries=3, pause=0.8):
    last = None
    for i in range(tries):
        try:
            r = session.get(url, timeout=120, verify=False)
            r.raise_for_status()
            if as_json:
                return r.json()
            r.encoding = r.encoding or 'utf-8'
            return r.text
        except Exception as e:
            last = e
            time.sleep(pause * (i + 1))
    raise last


def soup_of(url):
    return BeautifulSoup(get(url), 'lxml')


def split_br(s):
    """The billeteras and PSP payloads embed a literal <br> separating the street from a
    repeat of city/CP/province. Only the street belongs in Address_1."""
    parts = re.split(r'<\s*br\s*/?\s*>', str(s or ''), flags=re.I)
    return [clean(p) for p in parts]


def strip_cp(s):
    """Drop a trailing '(CP: X1234ABC)' - the postcode has its own column."""
    return clean(re.sub(r'\(\s*CP\s*:?[^)]*\)\s*$', '', clean(s)))


def street_only(domicilio, localidad='', provincia=''):
    """Exchange-house / PSP style composite address:
       'Calle y N: Mitre 868, P.B., Santa Fe, ROSARIO (CP: S2000COR)'
    The tail repeats province + city + postcode, all of which have their own columns.
    Peel the tail off using the row's own values, then fall back to just dropping the
    '(CP: ...)' if the tail is not shaped as expected."""
    s = split_br(domicilio)[0]
    s = re.sub(r'^\s*calle\s*y\s*n[º°o.]*\s*:?\s*', '', s, flags=re.I)
    s = strip_cp(s)
    for tail in (u'{}, {}'.format(clean(provincia), clean(localidad)),
                 u'{}, {}'.format(clean(localidad), clean(provincia))):
        if tail.strip(', ') and norm(s).endswith(norm(tail)):
            s = clean(s[:len(s) - len(tail)]).rstrip(',').strip()
            break
    return clean(s).rstrip(',').strip()


ZONA_RE = re.compile(r'^(.*?)\s+ZONA\s+(NORTE|SUR|ESTE|OESTE)\s*$', re.I)


def strip_zona(locality):
    """BCRA writes its own *supervision zone* into the locality field for Buenos Aires
    entities: 'CABA ZONA NORTE' / 'CABA ZONA SUR'. The zone is an internal supervisory
    division, not part of the entity's address, so it is trimmed back to the city it
    qualifies ('CABA'). Anything without the suffix is left untouched.

    This is NOT a list-1 quirk. It leaks from at least two independent sources -- list 1's
    'direccion' middle segment (42/73 rows) and list 3's 'domicilio.localidad' (20/91) --
    so the normalisation is applied centrally in emit() to every list's City rather than
    at one call site. v1 originally patched list 1 only and shipped list 3 dirty."""
    m = ZONA_RE.match(clean(locality))
    return clean(m.group(1)) if m else clean(locality)


def es_month_to_iso(mes, anio):
    """List 1 stamps itself 'mayo de 2026' - month granularity only. Rendered as the
    first of that month so it is a real date; the day is synthetic, see README."""
    months = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
              'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
              'noviembre': 11, 'diciembre': 12}
    m = months.get(norm(mes))
    if not m or not str(anio).strip().isdigit():
        return ''
    return '{}-{:02d}-01'.format(int(anio), m)


def iso_country(name):
    n = norm(name)
    if not n:
        return ''
    if n in CNTRY_ES:
        return CNTRY_ES[n]
    warn('unmapped country name {!r} -> left blank'.format(ascii_slug(name, 40)))
    return ''


def table_rows(sp, min_cells=6):
    """All <tr> of the page's single data table that actually carry cells."""
    t = sp.select_one('table#tabla-rowcolspan-int')
    if t is None:
        return []
    out = []
    for tr in t.find_all('tr'):
        cells = tr.find_all('td')
        if len(cells) >= min_cells:
            out.append([clean(c.get_text(' ', strip=True)) for c in cells])
    return out


def emit(nr, **kw):
    """Every row of every list funnels through here so the template fields cannot be
    forgotten or spelled differently on one list than on another."""
    spec = LISTS[nr]
    kw.setdefault('RegulationType', 'Regulated')
    # BCRA leaks its supervision zone into the locality on more than one list, so strip it
    # here -- once, for every list -- instead of at each call site. See strip_zona().
    if kw.get('City'):
        kw['City'] = strip_zona(kw['City'])
    add_row(Typology=spec['listname'],
            ListLabel=spec['label'],
            RegCtry=REGCTRY,
            RegCode=REGCODE,
            ListCode=str(nr),
            ListLanguage=spec['lang'],
            ListName=spec['listname'],
            ListProcessDate=processdate,
            **kw)


def finish(nr, count):
    spec = LISTS[nr]
    exp = spec['expected']
    if exp is not None and count != exp:
        warn('list {} row-count drift: {} now vs {} measured 2026-09-02'.format(nr, count, exp))
    print('   -> {} rows'.format(count))
    summary.append((nr, spec['listname'], count, exp))


#---- Begin_MainLoop ----
# ============================ 1  Financial Institutions ============================
# The ticket says "select each company provided on the list, click on search and extract
# the information of each" - that click is an XHR to action=detail, so it is called
# directly. The rendered page carries no <select> and no data at all.
nr = 1
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
payload = get(LISTS[nr]['url'], as_json=True)
entities = payload.get('entidades') or []
fa = payload.get('fecha_actualizacion') or {}
validity = es_month_to_iso(fa.get('mes'), fa.get('anio'))
print('   list endpoint returned {} entities, stamped {}'.format(len(entities), validity or 'n/a'))

TIPO_ENTRY = {'casa central': 'Head Office', 'casa matriz': 'Head Office',
              'casa central no operativa': 'Head Office'}

count = 0
for e in entities:
    codigo = clean(e.get('codigo'))
    d = get(API + 'entidades-financieras.php?action=detail&bco={}&lang=en'.format(codigo),
            as_json=True)
    ent = d.get('entidad') or {}
    if not clean(ent.get('nombre')):
        warn('list 1: empty detail for entity code {}'.format(ascii_slug(codigo, 12)))
        continue

    # 'STREET - LOCALITY - PROVINCE'; every one of the 73 split into exactly 3 segments
    # on 2026-09-02. A row that does not is kept whole in Address_1 rather than guessed at.
    seg = [clean(p) for p in str(ent.get('direccion') or '').split(' - ')]
    if len(seg) == 3:
        street, locality, province = seg
    else:
        street, locality, province = clean(ent.get('direccion')), '', ''
        warn('list 1: address for {} has {} segments, kept whole'.format(
            ascii_slug(codigo, 12), len(seg)))

    tipo = clean(ent.get('tipo'))
    emit(nr,
         Name=clean(ent.get('nombre')),
         EntryType=TIPO_ENTRY.get(norm(tipo), ''),
         InternalID_1=codigo,
         InternalID_1_type='BCRA entity code',
         InternalID_2=clean(ent.get('cuit')),
         InternalID_2_type='CUIT' if clean(ent.get('cuit')) else '',
         CoType=clean(ent.get('grupo_institucional')),
         License_Type=tipo,
         Address_1=street,
         Address_2=province,
         City=locality,          # emit() strips the 'ZONA NORTE/SUR' supervision suffix
         Cntry='AR',
         Phone=clean(ent.get('telefono')),
         Fax=clean(ent.get('fax')),
         Website=clean(ent.get('sitio_web')),
         Email=clean(ent.get('email')),
         ListValidityDate=validity)
    count += 1
finish(nr, count)

# ============================ 2  Exchange Houses ============================
nr = 2
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
d = get(LISTS[nr]['url'], as_json=True)
data = d.get('data') or []
if d.get('total') is not None and int(d['total']) != len(data):
    warn('list 2: endpoint says total={} but returned {} rows'.format(d['total'], len(data)))
count = 0
for r in data:
    if not clean(r.get('denominacion')):
        continue
    # 'suspension' was empty for all 7 rows on 2026-09-02; if BCRA ever fills it the
    # entity is not plainly Regulated any more, so surface it instead of mislabelling.
    susp = clean(r.get('suspension'))
    emit(nr,
         Name=clean(r.get('denominacion')),
         EntryType='Head Office' if norm(r.get('sede')) == 'legal' else '',
         InternalID_1=clean(r.get('codigo_externo')),
         InternalID_1_type='BCRA registration number',
         CoType='Exchange House',
         License_Type=susp and 'Suspended: {}'.format(susp) or '',
         Address_1=street_only(r.get('domicilio'), r.get('localidad'), r.get('provincia')),
         Address_2=clean(r.get('provincia')),
         City=clean(r.get('localidad')),
         Zip=clean(r.get('codigo_postal')),
         Cntry='AR',
         Phone=clean(r.get('telefono')),
         RegulationType='Suspended' if susp else 'Regulated')
    count += 1
finish(nr, count)

# ============================ 3  Interoperable e-wallets ============================
# Ticket: "use the 'Name of legal person' as Name" -> denominacion_pj, not marca_comercial.
nr = 3
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
d = get(LISTS[nr]['url'], as_json=True)
data = d.get('billeteras') or []
if d.get('total') is not None and int(d['total']) != len(data):
    warn('list 3: endpoint says total={} but returned {} rows'.format(d['total'], len(data)))
count = 0
for r in data:
    if not clean(r.get('denominacion_pj')):
        continue
    dom = r.get('domicilio') or {}
    emit(nr,
         Name=clean(r.get('denominacion_pj')),
         InternalID_1=clean(r.get('codigo_billetera')),
         InternalID_1_type='E-wallet code',
         InternalID_2=clean(r.get('cuit')),
         InternalID_2_type='CUIT' if clean(r.get('cuit')) else '',
         CoType='Interoperable e-wallet',
         License_Type='Enabled for interoperable QR (VQR)' if r.get('habilitacion_vqr')
                      else 'Not enabled for interoperable QR (VQR)',
         Address_1=split_br(dom.get('calle_numero'))[0],
         Address_2=clean(dom.get('provincia')),
         City=clean(dom.get('localidad')),
         Zip=clean(dom.get('codigo_postal')),
         Cntry='AR',
         Phone=clean(dom.get('telefono')),
         Website=clean(r.get('url_sitio_web')))
    count += 1
finish(nr, count)

# ============================ 4  Public guarantee funds ============================
# Scraped from the SPANISH page: the English one is a row short (see header note).
nr = 4
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
# Cross-check the column order against the English page's labels before trusting the
# Spanish table's positions - the Spanish table has no header row of its own.
try:
    en_rows = table_rows(soup_of(LISTS[nr]['ticket']))
    hdr = [norm(c) for c in en_rows[0]] if en_rows else []
    if hdr[:len(L4_HEADERS)] != L4_HEADERS:
        warn('list 4: English header changed {} - column order no longer confirmed'
             .format([ascii_slug(h, 18) for h in hdr]))
    else:
        print('   column order confirmed against the English page header')
    en_codes = set(r[0] for r in en_rows[1:] if r)
except Exception as ex:
    en_codes = set()
    warn('list 4: English cross-check failed ({})'.format(ascii_slug(str(ex), 50)))

rows = table_rows(soup_of(LISTS[nr]['url']))
count = 0
for r in rows:
    if norm(r[0]) in ('code', 'codigo'):      # defensive: ES page has no header today
        continue
    if len(r) < 8 or not clean(r[1]):
        continue
    if r[2] and not CUIT_RE.match(clean(r[2]).replace(' ', '')):
        warn('list 4: column 3 of code {} is not a CUIT ({}) - check column order'
             .format(ascii_slug(r[0], 10), ascii_slug(r[2], 20)))
    emit(nr,
         Name=clean(r[1]),
         InternalID_1=clean(r[0]),
         InternalID_1_type='BCRA entity code',
         InternalID_2=clean(r[2]),
         InternalID_2_type='CUIT' if clean(r[2]) else '',
         CoType='Public guarantee fund',
         Address_1=clean(r[3]),
         Address_2=clean(r[5]),
         City=clean(r[4]),
         Zip=clean(r[6]),
         Cntry='AR',
         Phone=clean(r[7]))
    count += 1
if en_codes:
    extra = sorted(set(clean(r[0]) for r in rows) - en_codes - {''})
    print('   ES-only entity codes absent from the English page: {}'.format(extra or 'none'))
finish(nr, count)

# ============================ 5  Platforms for MSME Financing ============================
# The visible <table> is an empty shell filled by JS; the data is server-rendered as JSON
# inside a hidden div on the same response.
nr = 5
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
node = soup_of(LISTS[nr]['url']).select_one('div#registro')
if node is None:
    raise RuntimeError('list 5: div#registro not found - the page layout changed')
res = json.loads(html.unescape(node.get_text())).get('result') or []
count = 0
for r in res:
    if not clean(r.get('TX_DENOMINACION_PJ')):
        continue
    dom = r.get('domicilioDto') or {}
    street = ' '.join(x for x in (clean(dom.get('TX_DIRECCION')),
                                  clean(dom.get('TX_PISO_OFICINA'))) if x)
    pais = clean(dom.get('TX_PAIS'))
    emit(nr,
         Name=clean(r.get('TX_DENOMINACION_PJ')),
         InternalID_1=clean(r.get('CD_CODIGO_ENTIDAD')),
         InternalID_1_type='Platform code',
         InternalID_2=clean(r.get('CD_CUIT')),
         InternalID_2_type='CUIT' if clean(r.get('CD_CUIT')) else '',
         CoType='Platform for MSME financing',
         Address_1=street,
         Address_2=clean(dom.get('TX_PROVINCIA')),
         City=clean(dom.get('TX_LOCALIDAD')),
         Zip=clean(dom.get('TX_CODIGO_POSTAL')),
         Cntry=iso_country(pais) or 'AR',
         Phone=clean(dom.get('TX_TELEFONO')))
    count += 1
finish(nr, count)

# ============================ 6  Payment service providers ============================
# The ticket URL pins tipoPSP=1 ("PSP offering Payment Account"), so only type 1 is taken.
# Types 2-9 exist on the same endpoint and hold a further ~210 entities - see README.
nr = 6
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
d = get(LISTS[nr]['url'], as_json=True)
data = d.get('proveedores') or []
psp_type = clean(d.get('tipo_psp_nombre'))
if d.get('total') is not None and int(d['total']) != len(data):
    warn('list 6: endpoint says total={} but returned {} rows'.format(d['total'], len(data)))
count = 0
for r in data:
    name = clean(r.get('denominacion_pj')) or clean(r.get('denominacion'))
    if not name:
        continue
    emit(nr,
         Name=name,
         InternalID_1=clean(r.get('codigo')),
         InternalID_1_type='Provider code',
         InternalID_2=clean(r.get('cuit')),
         InternalID_2_type='CUIT' if clean(r.get('cuit')) else '',
         CoType='Payment service provider',
         License_Type=psp_type,
         Address_1=street_only(r.get('domicilio'), r.get('localidad'), r.get('provincia')),
         Address_2=clean(r.get('provincia')),
         City=clean(r.get('localidad')),
         Zip=clean(r.get('codigo_postal')),
         Cntry='AR',
         Phone=clean(r.get('telefono')))
    count += 1
finish(nr, count)

# ============================ 7  Representatives of foreign FIs ============================
# Scraped from the SPANISH page: the English one carries 4 of the 8 rows and corrupts one
# code cell into the literal text 'Item No. 30013'.
#
# Shape of a row: the named entity is a FOREIGN bank, but the address/phone belong to its
# representative office in Argentina. So Cntry follows the address ('AR') and the home
# jurisdiction is carried in 'Cntry - Mother company', with the same name repeated in
# 'Name - Mother Company'. The two representative *people* have no field in the fixed
# 43-key schema and are deliberately not emitted - see README.
nr = 7
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
sp = soup_of(LISTS[nr]['url'])
tbl = sp.select_one('table#tabla-rowcolspan-int')
if tbl is None:
    raise RuntimeError('list 7: table#tabla-rowcolspan-int not found')

idx = {}
for tr in tbl.find_all('tr'):
    cells = [norm(c.get_text(' ', strip=True)) for c in tr.find_all(['th', 'td'])]
    hits = {L7_LABELS[c]: i for i, c in enumerate(cells) if c in L7_LABELS}
    if len(hits) >= 5:
        idx = hits
        break
if len(idx) < 5:
    raise RuntimeError('list 7: could not map columns by label, got {}'.format(sorted(idx)))
print('   columns mapped by label: {}'.format(sorted(idx)))

count = 0
for r in table_rows(sp):
    if norm(r[idx['name']]) in ('entidad representada', 'entity represented'):
        continue
    name = clean(r[idx['name']])
    if not name:
        continue
    code = clean(r[idx['code']])
    # the English page has been seen writing 'Item No. 30013' into this cell
    m = re.search(r'\d{3,}', code)
    if m and m.group(0) != code:
        warn('list 7: entity code cell {!r} cleaned to {}'.format(ascii_slug(code, 20), m.group(0)))
        code = m.group(0)
    emit(nr,
         Name=name,
         EntryType='Representative Office',
         InternalID_1=code,
         InternalID_1_type='BCRA entity code',
         CoType='Representative office of a foreign financial institution',
         Address_1=clean(r[idx['address']]),
         City=clean(r[idx['city']]),
         Cntry='AR',
         Phone=clean(r[idx['phone']]),
         **{'Name - Mother Company': name,
            'Cntry - Mother company': iso_country(r[idx['country']])})
    count += 1
finish(nr, count)

# ============================ 8  Electronic clearing houses / EFT managers ============================
# No table: two hand-written <ul>s under two Spanish headings. The two
# table#tabla-rowcolspan-int elements on this page are empty shells - ignore them.
# Names repeat across the two groups; that is the site's own content and is NOT deduped,
# because the group is the only thing distinguishing the two entries.
nr = 8
print('\n[{}] {}'.format(nr, LISTS[nr]['listname']))
inner = soup_of(LISTS[nr]['url']).select_one('div.et_pb_text_3 .et_pb_text_inner')
if inner is None:
    raise RuntimeError('list 8: div.et_pb_text_3 .et_pb_text_inner not found')

count = 0
group = ''
for el in inner.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'ul']):
    if el.name != 'ul':
        n = norm(el.get_text(' ', strip=True))
        for key, label in L8_GROUPS:
            if key in n:
                group = label
                break
        continue
    if not group:
        warn('list 8: a <ul> appeared before any recognised heading')
    for li in el.find_all('li'):
        # every <li> starts with an en dash + space
        name = clean(re.sub(r'^[–—‒-]+\s*', '', clean(li.get_text(' ', strip=True))))
        if not name:
            continue
        emit(nr, Name=name, CoType=group or 'Electronic clearing house / EFT scheme manager',
             Cntry='AR')
        count += 1
finish(nr, count)


#---- Begin_writer and save df to excel ----
print('\n================ RUN SUMMARY ================')
total = 0
drift = 0
for n, name, cnt, exp in summary:
    flag = ''
    if exp is not None and cnt != exp:
        flag = '   <-- was {} on 2026-09-02'.format(exp)
        drift += 1
    print('ListCode {:<3} label {}  {:<52} {:>5}{}'.format(
        n, LISTS[n]['label'], ascii_slug(name, 52), cnt, flag))
    total += cnt
print('{:<62} {:>5}'.format('TOTAL', total))
print('lists at their measured row count: {}/{}'.format(len(summary) - drift, len(summary)))
if warnings_seen:
    print('\n{} warning(s) raised during the run:'.format(len(warnings_seen)))
    for w in warnings_seen:
        print('  - {}'.format(w))

os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

assert list(df.columns) == SQL_KEYS, 'schema drift: columns do not match the fixed 43-key sqldict'
print('\nSchema check OK: {} columns'.format(len(df.columns)))

# Template fields have a fixed shape. ListCode is the bare ticket ListNr - NOT
# '<CC> <AGENCY> <nr>' - and RegCode is the agency alone. Asserted so it cannot regress.
assert set(df['RegCtry']) == {REGCTRY}, 'RegCtry must be {!r}, got {}'.format(REGCTRY, set(df['RegCtry']))
assert set(df['RegCode']) == {REGCODE}, 'RegCode must be {!r}, got {}'.format(REGCODE, set(df['RegCode']))
_badlc = sorted(c for c in set(df['ListCode']) if not str(c).isdigit())
assert not _badlc, 'ListCode must be a bare number per list, got {}'.format(_badlc)
assert set(df['ListLabel']) <= {'1', '2', '3', '4'}, 'ListLabel out of range: {}'.format(set(df['ListLabel']))
assert (df['ListProcessDate'] == processdate).all(), 'ListProcessDate not stamped on every row'
assert (df['RegulationType'] != '').all(), 'RegulationType missing on some rows'
print('Template fields OK: RegCtry={} RegCode={} ListCode={}'.format(
    REGCTRY, REGCODE, ','.join(sorted(set(df['ListCode']), key=int))))

# A row count alone does not prove the Name column holds names - a sibling regulator once
# shipped 997 reconciled rows with 'Yes'/'No' in Name. Assert the content separately.
_bad = df[df['Name'].str.strip().isin(['', 'Yes', 'No', 'Si', 'N/A', '-', 'Name', 'Denominacion'])]
assert _bad.empty, 'Name column holds non-name values in {} rows'.format(len(_bad))
print('Name content check OK: {} distinct names over {} rows'.format(df['Name'].nunique(), len(df)))

# City must hold a city, never a BCRA supervision zone. Asserted across EVERY list, not
# just the one the quirk was first noticed on: v1 patched list 1 alone and shipped list 3
# with 20 rows reading 'CABA ZONA NORTE'/'CABA ZONA SUR'.
_zona = df[df['City'].str.contains(r'\bZONA\b', case=False, regex=True, na=False)]
assert _zona.empty, 'supervision zone left in City on {} rows, lists {}'.format(
    len(_zona), sorted(set(_zona['ListCode'])))
print('City check OK: no supervision zone in City on any of the {} lists'.format(
    df['ListCode'].nunique()))

# Identifiers are text, not quantities: Excel turns 30715084291 into 3.07151e+10 and eats
# the leading zeros off a phone number like '000043294201'.
for _c in TEXT_COLS:
    df[_c] = df[_c].apply(lambda v: '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip())

outpath = os.path.join(scriptfolder, filename)
df.to_excel(outpath, sheet_name='SQL Ready', index=False)

# Read the workbook back and prove Excel did not mangle anything on the way out.
_chk = pd.read_excel(outpath, sheet_name='SQL Ready', dtype=str, keep_default_na=False)
assert len(_chk) == len(df), 'round-trip row count changed: {} -> {}'.format(len(df), len(_chk))
for _c in TEXT_COLS:
    _bad = _chk[_c].astype(str).str.contains(r'[eE]\+\d|\.0$', regex=True, na=False)
    assert not _bad.any(), 'Excel coerced {} to float in {} rows'.format(_c, int(_bad.sum()))
_lead = df[df['Phone'].str.startswith('0')]
_lead_back = _chk[_chk['Phone'].str.startswith('0')]
assert len(_lead) == len(_lead_back), 'leading zeros lost on Phone: {} -> {}'.format(
    len(_lead), len(_lead_back))
print('Round-trip check OK: {} rows re-read, IDs text-safe, {} leading-zero phones intact'
      .format(len(_chk), len(_lead_back)))

print('Saved {} rows to {}'.format(len(df), outpath))
