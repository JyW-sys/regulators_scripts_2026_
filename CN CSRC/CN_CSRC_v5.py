#---- Begin_Librairie ----
# CN CSRC v5 -- China Securities Regulatory Commission (DECD-6835)
# Source: CSRC English site. Each list is a channel whose latest article links a PDF
# extracted from the CSRC Annual Report. Discovered at runtime via the site's own
# JSON endpoint /searchList/<channelid>?_isJson=true (no Selenium, no browser driver).
import os
import re
import io
import datetime
import time
import warnings
from urllib.parse import urljoin, quote

import requests
import pandas as pd
import pdfplumber

requests.packages.urllib3.disable_warnings()
warnings.filterwarnings('ignore')

#---- Begin_fileName ----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)

regulatorName = 'CN CSRC'
now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, now.strftime('%Y-%m-%d %H.%M.%S'))

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

BASE = 'https://www.csrc.gov.cn'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36',
           'Referer': BASE + '/csrc_en/'}

# ListNr -> (ListName, landing page path, channelid, CoType, ListLabel)
# Channel ids are the site's own; the landing page is re-read each run and the
# article + PDF beneath it are discovered, never hard-coded.
LISTS = [
    (1, 'List of Securities Companies',      '/csrc_en/c102044/common_list.shtml', 'f7390694d118449b84d1c8fcb544b122', 'Securities Company',                        4),
    (2, 'List of Futures Companies',         '/csrc_en/c102045/common_list.shtml', '0907ad3806d44a248e536afdbbf1d391', 'Futures Company',                           4),
    (3, 'List of Fund Management Companies', '/csrc_en/c102046/common_list.shtml', '726dfe99bc11474e98df464e810cc24f', 'Fund Management Company',                   4),
    (4, 'List of QFIIs',                     '/csrc_en/c102049/common_list.shtml', '9c0014a9a36d4418be4554645d15139e', 'Qualified Foreign Institutional Investor',   4),
    (5, 'List of Custodian Banks',           '/csrc_en/c102051/common_list.shtml', '36c7a56325cb4177b34d2e6f378fa005', 'QFII Custodian Bank',                       1),
]

# Place of Registration (QFII list) -> ISO-3166 alpha-2. Unmapped values are reported.
CNTRY_MAP = {
    'switzerland': 'CH', 'japan': 'JP', 'united kingdom': 'GB', 'united states': 'US',
    'germany': 'DE', 'hong kong sar': 'HK', 'hong kong': 'HK', 'singapore': 'SG',
    'canada': 'CA', 'france': 'FR', 'netherlands': 'NL', 'the netherlands': 'NL',
    'australia': 'AU', 'south korea': 'KR', 'korea': 'KR', 'republic of korea': 'KR',
    'taiwan': 'TW', 'norway': 'NO', 'sweden': 'SE', 'denmark': 'DK', 'finland': 'FI',
    'ireland': 'IE', 'luxembourg': 'LU', 'italy': 'IT', 'spain': 'ES', 'belgium': 'BE',
    'austria': 'AT', 'malaysia': 'MY', 'thailand': 'TH', 'india': 'IN', 'israel': 'IL',
    'united arab emirates': 'AE', 'uae': 'AE', 'qatar': 'QA', 'kuwait': 'KW',
    'saudi arabia': 'SA', 'macao sar': 'MO', 'macau sar': 'MO', 'new zealand': 'NZ',
    'brazil': 'BR', 'south africa': 'ZA', 'cayman islands': 'KY', 'bermuda': 'BM',
    'british virgin islands': 'VG', 'mauritius': 'MU', 'portugal': 'PT', 'greece': 'GR',
    'poland': 'PL', 'russia': 'RU', 'turkey': 'TR', 'chile': 'CL', 'mexico': 'MX',
    'hungary': 'HU', 'czech republic': 'CZ', 'iceland': 'IS', 'liechtenstein': 'LI',
    'monaco': 'MC', 'cyprus': 'CY', 'malta': 'MT', 'china': 'CN', 'indonesia': 'ID',
    'philippines': 'PH', 'vietnam': 'VN', 'jersey': 'JE', 'guernsey': 'GG',
    'isle of man': 'IM', 'bahamas': 'BS', 'panama': 'PA', 'argentina': 'AR',
    'brunei': 'BN', 'lithuania': 'LT', 'french': 'FR', 'bailiwick of jersey': 'JE',
    'the region of taiwan': 'TW', 'taiwan region': 'TW',
}

TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company', 'ListCode']

#---- Begin_Function ----
def add_row(**kw):
    """Single funnel into sqldict. Appends to EVERY one of the 43 keys; raises on
    an unknown key so the schema cannot drift."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        sqldict[k].append(str(kw.get(k, '')) if kw.get(k, '') is not None else '')
    lens = {len(v) for v in sqldict.values()}
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(lens))


def decode_bytes(raw):
    """Chinese government sites lie about their charset. Never trust r.encoding:
    decode the bytes explicitly, utf-8 first then gb18030 (superset of GBK/GB2312)."""
    for enc in ('utf-8', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def http_get(url, tries=5):
    """The corporate TLS proxy drops connections intermittently. Always verify=False
    (a cert error here is the proxy, not the site) and retry with backoff."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=HEADERS, verify=False, timeout=90)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            print('      retry {}/{} after {}: {}'.format(i + 1, tries, type(e).__name__, url[:90]))
            time.sleep(3 * (i + 1))
    raise last


def get_text(url):
    return decode_bytes(http_get(url).content)


def latest_article(channelid):
    """The landing page is an empty shell; common_list.js fills it from the site's
    own JSON endpoint. _pageSize is capped server-side at 20 regardless of what we
    ask for, so we request 20 and report the declared total."""
    url = ('{}/searchList/{}?_isAgg=true&_isJson=true&_pageSize=20'
           '&_template=index&_rangeTimeGte=&_channelName=&page=1').format(BASE, channelid)
    data = http_get(url).json()['data']
    results = data.get('results') or []
    if not results:
        raise RuntimeError('channel {} returned no articles'.format(channelid))
    if len(results) > 20:
        print('   NOTE: server honoured a pageSize above 20 ({})'.format(len(results)))
    art = results[0]  # newest first
    href = art['url']
    if href.startswith('//'):
        href = 'https:' + href
    elif href.startswith('/'):
        href = BASE + href
    return {'title': art['title'], 'url': href,
            'published': (art.get('publishedTimeStr') or '')[:10],
            'channel_total': data.get('total')}


def find_attachment(article_url):
    """Discover the attachment from the article page. Never hard-code a filename --
    these are republished under new article-id folders."""
    html = get_text(article_url)
    links = re.findall(r'<a[^>]*href="([^"]+\.(?:pdf|xls|xlsx|doc|docx))"', html, re.I)
    if not links:
        raise RuntimeError('no attachment link on {}'.format(article_url))
    return urljoin(article_url, quote(links[0], safe='/:'))


def download(url, dest):
    r = http_get(url)
    if not r.content.startswith(b'%PDF'):
        raise RuntimeError('not a PDF: {} ({} bytes)'.format(url, len(r.content)))
    with open(dest, 'wb') as fh:
        fh.write(r.content)
    return dest


BANNER = re.compile(r'ANNUAL REPORT|China Securities Regulatory Commission|^Table\s+\d', re.I)


def page_records(page, state):
    """These PDFs have no per-row ruling lines, so extract_tables() merges whole
    blocks of rows into one cell. Instead we anchor on the printed sequence number
    (the source's own No. column): each number's vertical centre defines a row, the
    band runs to the midpoint between neighbouring numbers, and every word is
    assigned to the band containing its centre. That reunites names that wrap onto
    the line above or below their number.

    Column boundaries are found per page from vertical whitespace gutters in the
    word x-projection, so no x coordinate is hard-coded."""
    words = page.extract_words(keep_blank_chars=False)
    words = [w for w in words if 'cid:' not in w['text']]
    h = float(page.height)

    keep = []
    for w in words:
        mid = (w['top'] + w['bottom']) / 2.0
        if mid < h * 0.14 and BANNER.search(w['text']):
            continue                                    # running header
        if mid > h * 0.93 and re.fullmatch(r'\d{1,4}', w['text']):
            continue                                    # printed page number
        keep.append(w)
    # drop any residual banner words on the top band
    keep = [w for w in keep
            if not ((w['top'] + w['bottom']) / 2.0 < h * 0.13
                    and w['text'] in ('2020', 'ANNUAL', 'REPORT', 'China', 'Securities',
                                      'Regulatory', 'Commission', 'Table'))]
    if not keep:
        return []

    # --- column gutters -------------------------------------------------
    xs = [(w['x0'], w['x1']) for w in keep]
    lo, hi = min(a for a, _ in xs), max(b for _, b in xs)
    occ = [False] * (int(hi - lo) + 2)
    for a, b in xs:
        for i in range(int(a - lo), int(b - lo) + 1):
            if 0 <= i < len(occ):
                occ[i] = True
    bounds, run = [], 0
    for i, o in enumerate(occ):
        if not o:
            run += 1
        else:
            if run >= 7:
                bounds.append(lo + i - run / 2.0)
            run = 0
    edges = [lo - 1] + bounds + [hi + 1]

    def col_of(w):
        c = (w['x0'] + w['x1']) / 2.0
        for i in range(len(edges) - 1):
            if edges[i] <= c < edges[i + 1]:
                return i
        return len(edges) - 2

    # --- row anchors: the source's own sequence numbers ------------------
    # A 序号 column runs 1,2,3,... without gaps. Enforcing that invariant document-wide
    # rejects stray integers that live in the leftmost column but are not row numbers
    # -- e.g. the "6" of the running title "Table 6 List of QFII Custodian Banks", and
    # the printed page number. It also makes reconciliation exact by construction.
    candidates = sorted([w for w in keep
                         if re.fullmatch(r'\d{1,4}', w['text']) and col_of(w) == 0],
                        key=lambda w: w['top'])
    anchors = []
    for w in candidates:
        if int(w['text']) == state['expect']:
            anchors.append(w)
            state['expect'] += 1
        else:
            state['rejected'].append((page.page_number, w['text']))
    if not anchors:
        return []
    centres = [(a['top'] + a['bottom']) / 2.0 for a in anchors]
    bands = []
    for i, a in enumerate(anchors):
        top = 0 if i == 0 else (centres[i - 1] + centres[i]) / 2.0
        bot = h if i == len(anchors) - 1 else (centres[i] + centres[i + 1]) / 2.0
        bands.append({'no': a['text'], 'top': top, 'bot': bot,
                      'cols': {}, 'anchor': a})

    for w in keep:
        if w is anchors[0] and False:
            continue
        mid = (w['top'] + w['bottom']) / 2.0
        for b in bands:
            if b['top'] <= mid < b['bot']:
                c = col_of(w)
                b['cols'].setdefault(c, []).append(w)
                break

    out = []
    for b in bands:
        rec = {'No': b['no']}
        for c, ws in b['cols'].items():
            ws = [w for w in ws if w is not b['anchor']]
            if not ws:
                continue
            ws = sorted(ws, key=lambda w: (round(w['top'] / 3), w['x0']))
            rec[c] = ' '.join(w['text'] for w in ws).strip()
        out.append(rec)
    return out


def parse_pdf(path):
    recs = []
    state = {'expect': 1, 'rejected': []}
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        for pg in pdf.pages:
            recs.extend(page_records(pg, state))
    if state['rejected']:
        print('   dropped {} non-sequence integer(s) in the No. column: {}'.format(
            len(state['rejected']), state['rejected'][:6]))
    return recs, npages


DATE_RE = re.compile(r'^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$')


def norm_date(s):
    m = DATE_RE.match((s or '').strip())
    if not m:
        return ''
    y, mo, d = m.groups()
    return '{}-{:02d}-{:02d}'.format(y, int(mo), int(d))


def profile_columns(recs):
    """Self-calibrating column roles: the date column is whichever column most often
    holds a yyyy/m/d value; the name column is the first non-empty column; the
    place-of-registration column sits immediately before the date."""
    counts, filled = {}, {}
    for r in recs:
        for c, v in r.items():
            if c == 'No' or not v:
                continue
            filled[c] = filled.get(c, 0) + 1
            if DATE_RE.match(v.strip()):
                counts[c] = counts.get(c, 0) + 1
    date_col = max(counts, key=counts.get) if counts else None
    # The name column is the one carrying real prose: exclude columns that are mostly
    # dates or mostly Yes/No flags, then take the one with the most alphabetic text.
    score = {}
    for c in filled:
        vals = [(r.get(c) or '').strip() for r in recs if (r.get(c) or '').strip()]
        if not vals:
            continue
        dates = sum(1 for v in vals if DATE_RE.match(v))
        flags = sum(1 for v in vals if v.lower() in ('yes', 'no'))
        if dates > 0.5 * len(vals) or flags > 0.5 * len(vals):
            continue
        score[c] = sum(len(re.sub(r'[^A-Za-z]', '', v)) for v in vals) / float(len(recs))
    name_col = max(score, key=score.get) if score else (min(filled) if filled else None)
    return name_col, date_col


def is_mojibake(s):
    return bool(re.search(r'[�]|Ã.|â€|ï¿½', s or ''))

#---- Begin_MainLoop ----
summary = []
unmapped_cntry = set()

for listnr, listname, path, channelid, cotype, listlabel in LISTS:
    landing = '{}{}?channelid={}'.format(BASE, path, channelid)
    print('=' * 70)
    print('List {} | {}'.format(listnr, listname))
    print('   landing : {}'.format(landing))

    art = latest_article(channelid)
    print('   article : {} ({}) [channel holds {} article(s)]'.format(
        art['title'], art['published'], art['channel_total']))

    pdf_url = find_attachment(art['url'])
    print('   pdf     : {}'.format(pdf_url))

    dest = os.path.join(tempfolder, 'CSRC_list{}.pdf'.format(listnr))
    download(pdf_url, dest)

    recs, npages = parse_pdf(dest)
    if not recs:
        raise RuntimeError('list {} parsed zero rows from {}'.format(listnr, pdf_url))

    name_col, date_col = profile_columns(recs)
    declared = max(int(r['No']) for r in recs if r['No'].isdigit())

    emitted = 0
    for r in recs:
        name = (r.get(name_col) or '').strip()
        name = re.sub(r'\s+', ' ', name)
        if not name:
            continue

        cntry, regdate = 'CN', ''
        if listnr == 4:
            # Gutter detection can shift column indices from page to page, so resolve
            # the date column inside THIS record and take the column immediately to its
            # left as Place of Registration -- never a fixed global index.
            dcols = [c for c, v in r.items()
                     if c != 'No' and isinstance(c, int) and DATE_RE.match((v or '').strip())]
            place = ''
            if dcols:
                dc = min(dcols)
                regdate = norm_date(r.get(dc, ''))
                left = [c for c in r if isinstance(c, int) and c < dc
                        and c != name_col and (r.get(c) or '').strip()]
                if left:
                    place = (r.get(max(left)) or '').strip()
            key = re.sub(r'\s+', ' ', place).strip().lower()
            if key:
                if key in CNTRY_MAP:
                    cntry = CNTRY_MAP[key]
                else:
                    unmapped_cntry.add(place)
                    cntry = ''

        add_row(
            Name=name,
            InternalID_1=r['No'],
            InternalID_1_type='CSRC list sequence number (No.)',
            CoType=cotype,
            Cntry=cntry,
            RegulationType='Regulated',
            RegulationDate=regdate,
            RegCtry='CN',
            RegCode='CSRC',
            ListCode=str(listnr),
            ListLabel=str(listlabel),
            ListLanguage='EN',
            ListName=listname,
            ListValidityDate=art['published'],
            ListProcessDate=processdate,
        )
        emitted += 1

    print('   pages {} | rows parsed {} | rows emitted {} | source declares No. up to {}'.format(
        npages, len(recs), emitted, declared))
    if emitted != declared:
        print('   *** RECONCILIATION MISMATCH: emitted {} vs source No. max {} (diff {}) ***'.format(
            emitted, declared, emitted - declared))
    else:
        print('   reconciled OK ({} == {})'.format(emitted, declared))
    summary.append((listnr, listname, emitted, declared, art['title'], art['published']))

print('=' * 70)
if unmapped_cntry:
    print('UNMAPPED Place of Registration values (Cntry left blank): {}'.format(sorted(unmapped_cntry)))
else:
    print('All Place of Registration values mapped to ISO-3166 alpha-2.')

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# column order + count must still be exactly the 43-key schema
assert list(df.columns) == SCHEMA_KEYS, 'column order drifted from the 43-key schema'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

# mojibake gate -- a garbled Name passes every row-count check
bad = df[df['Name'].map(is_mojibake)]
assert len(bad) == 0, 'mojibake detected in {} Name values, e.g. {}'.format(
    len(bad), bad['Name'].head(3).tolist())
print('Mojibake check: 0 of {} Name values garbled.'.format(len(df)))

# Excel silently coerces all-digit strings to floats and eats leading zeros
for c in TEXT_COLS:
    df[c] = df[c].astype(str).replace('nan', '')

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# read the workbook back and prove the ID round-tripped as a digit string
chk = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
assert len(chk) == len(df), 'row count changed on round-trip: {} -> {}'.format(len(df), len(chk))
assert list(chk.columns) == SCHEMA_KEYS, 'column order changed on round-trip'
sample = chk['InternalID_1'].dropna().iloc[0]
assert re.fullmatch(r'\d+', str(sample)), 'InternalID_1 did not round-trip as a digit string: {!r}'.format(sample)
assert chk['RegCode'].dropna().unique().tolist() == ['CSRC'], 'RegCode is not CSRC: {}'.format(chk['RegCode'].unique())
print('Round-trip OK: {} rows, 43 cols, InternalID_1 sample {!r}, RegCode unique {}'.format(
    len(chk), str(sample), chk['RegCode'].unique().tolist()))

print('\n--- per-list reconciliation ---')
for nr, nm, got, dec, title, pub in summary:
    print('  List {} {:<40} emitted {:>4} | source No. max {:>4} | {} ({})'.format(nr, nm, got, dec, title, pub))
print('  TOTAL emitted: {}'.format(len(df)))
print(df['ListName'].value_counts().to_string())
