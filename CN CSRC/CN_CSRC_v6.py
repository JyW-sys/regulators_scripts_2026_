#---- Begin_Librairie ----
# CN CSRC v6 -- China Securities Regulatory Commission (DECD-6835)
# Source: CSRC English site. Each list is a channel whose latest article links a PDF
# extracted from the CSRC Annual Report. Discovered at runtime via the site's own
# JSON endpoint /searchList/<channelid>?_isJson=true (no Selenium, no browser driver).
#
# v6 fixes the polluted Name column that v5 shipped (95 rows carrying "Yes"/"No"/a date
# instead of a company name, plus the list-5 row 1 carrying the table title). See the
# "COLUMN GEOMETRY" note above page_records() for the mechanism and the fix.
import os
import re
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

DATE_RE = re.compile(r'^(\d{4})[/\-.](\d{1,2})[/\-.](\d{1,2})$')
SEQ_RE = re.compile(r'^\d{1,4}$')
YEAR_RE = re.compile(r'^(19|20)\d{2}$')

# Words of the running header printed at the top of every annual-report page.
# The year is matched by YEAR_RE so a new edition does not need a code change.
HEADER_WORDS = ('ANNUAL', 'REPORT', 'China', 'Securities', 'Regulatory', 'Commission', 'Table')
BANNER = re.compile(r'ANNUAL REPORT|China Securities Regulatory Commission|^Table\s+\d', re.I)

#---- Begin_Function ----
def add_row(**kw):
    """Single funnel into sqldict. Appends to EVERY one of the 43 keys; raises on
    an unknown key so the schema cannot drift."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        sqldict[k].append(str(kw.get(k, '')) if kw.get(k, '') is not None else '')
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(lens))


def ascii_slug(s, limit=70):
    """cp1252 console safety: never print raw scraped text. Non-ASCII becomes '?'."""
    return re.sub(r'[^\x20-\x7e]', '?', s or '')[:limit]


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


def title_key(title):
    """Article titles are '<ListName> (<edition>)'. Strip the trailing parenthetical
    so an edition change does not need a code change."""
    t = re.sub(r'\s*\([^()]*\)\s*$', '', (title or '').strip())
    return re.sub(r'\s+', ' ', t).strip().lower()


def latest_article(channelid, listname):
    """The landing page is an empty shell; common_list.js fills it from the site's
    own JSON endpoint. _pageSize is capped server-side at 20 regardless of what we
    ask for, so we request 20 and report the declared total.

    Newest-first is NOT sufficient on its own. The QFII channel (98 articles) also
    carries 'List of RQFII ...' and 'List of QFIIs Custodian Banks ...' editions, so
    results[0] can be a different register. Prefer the newest article whose title
    (minus its trailing '(edition)') equals the ticket's ListName exactly; fall back
    to results[0] with a loud NOTE rather than failing, so the run never silently
    produces zero rows."""
    url = ('{}/searchList/{}?_isAgg=true&_isJson=true&_pageSize=20'
           '&_template=index&_rangeTimeGte=&_channelName=&page=1').format(BASE, channelid)
    data = http_get(url).json()['data']
    results = data.get('results') or []
    if not results:
        raise RuntimeError('channel {} returned no articles'.format(channelid))
    if len(results) > 20:
        print('   NOTE: server honoured a pageSize above 20 ({})'.format(len(results)))
    want = title_key(listname)
    matches = [r for r in results if title_key(r.get('title')) == want]
    if matches:
        art = matches[0]        # results are newest first
    else:
        art = results[0]
        print('   NOTE: no article titled {!r} in the newest {} of channel {}; '
              'falling back to the newest article.'.format(listname, len(results), channelid))
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


def median(values):
    v = sorted(values)
    n = len(v)
    if not n:
        return None
    if n % 2:
        return v[n // 2]
    return (v[n // 2 - 1] + v[n // 2]) / 2.0


def column_edges(words, min_gutter=7):
    """Column boundaries from vertical whitespace gutters in the word x-projection.
    No x coordinate is hard-coded; a run of >= min_gutter empty points is a gutter."""
    xs = [(w['x0'], w['x1']) for w in words]
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
            if run >= min_gutter:
                bounds.append(lo + i - run / 2.0)
            run = 0
    return [lo - 1] + bounds + [hi + 1]


def col_index(edges, w):
    c = (w['x0'] + w['x1']) / 2.0
    for i in range(len(edges) - 1):
        if edges[i] <= c < edges[i + 1]:
            return i
    return len(edges) - 2


def walk_anchors(keep, edges, expect):
    """Row anchors are the source's own sequence numbers in the leftmost column.
    A 'No.' column runs 1,2,3,... without gaps; enforcing that invariant document-wide
    rejects stray integers in the leftmost column (the '6' of 'Table 6 List of ...',
    the printed page number). Pure function -- the caller decides whether to commit."""
    cand = sorted([w for w in keep if SEQ_RE.match(w['text']) and col_index(edges, w) == 0],
                  key=lambda w: w['top'])
    anchors, rejected = [], []
    for w in cand:
        if int(w['text']) == expect:
            anchors.append(w)
            expect += 1
        else:
            rejected.append(w['text'])
    return anchors, rejected, expect


def page_roles(recs):
    """Resolve the column ROLES inside ONE page.

    This is the v6 fix. Gutter detection is page-local, so the same physical column
    carries a different integer index on different pages; a single global index picked
    across the whole document therefore lands on the wrong column wherever the gutter
    count differs. Roles must be decided with the same granularity as the geometry.

      date  -- the column whose values are mostly yyyy/m/d
      flag  -- a column whose values are mostly Yes/No (the source's own flag columns)
      name  -- the LEFTMOST densely-filled prose column that is neither of the above.
               Name is always the first text column after No. in all five tables, and
               'leftmost' stays correct whether or not the No./Name gutter was found.
    """
    filled, dates, flags, alpha = {}, {}, {}, {}
    n = len(recs)
    for r in recs:
        for c, v in r['_cols'].items():
            v = (v or '').strip()
            if not v:
                continue
            filled[c] = filled.get(c, 0) + 1
            if DATE_RE.match(v):
                dates[c] = dates.get(c, 0) + 1
            if v.lower() in ('yes', 'no'):
                flags[c] = flags.get(c, 0) + 1
            alpha[c] = alpha.get(c, 0) + len(re.sub(r'[^A-Za-z]', '', v))

    date_col = None
    if dates:
        dc = max(dates, key=lambda c: dates[c])
        if dates[dc] >= 0.5 * filled[dc]:
            date_col = dc

    cands = []
    for c in sorted(filled):
        f = filled[c]
        if dates.get(c, 0) > 0.5 * f:
            continue                                   # a date column
        if flags.get(c, 0) > 0.5 * f:
            continue                                   # a Yes/No flag column
        if alpha.get(c, 0) / float(f) < 3:
            continue                                   # not prose
        if f < 0.5 * n:
            continue                                   # too sparse to be Name
        cands.append(c)
    if cands:
        name_col = min(cands)
    else:
        score = dict((c, alpha[c] / float(n)) for c in filled if alpha.get(c, 0))
        name_col = max(score, key=lambda c: score[c]) if score else None
    return name_col, date_col


def page_records(page, state):
    """COLUMN GEOMETRY -- read this before touching the numbers below.

    These PDFs have no per-row ruling lines, so extract_tables() merges whole blocks of
    rows into one cell. Instead we anchor on the printed sequence number (the source's
    own No. column): each number's vertical centre defines a row, the band runs to the
    midpoint between neighbouring numbers, and every word is assigned to the band
    containing its centre. That reunites names that wrap onto the line above or below
    their number.

    Two page-local hazards, both fixed in v6:

    1. THE PAGE-1 TITLE BRIDGES THE GUTTERS. Page 1 of every table carries a full-width
       title line ("Table 2   List of Securities Companies"). Its words span the x range
       where the No./Name gutter lives, so the x-projection shows no whitespace there and
       the two columns merge -- page 1 came out with 3 column edges where its neighbours
       had 5-7. So: probe for the anchors, then cut everything above the first anchor by
       more than 0.75 of a row pitch, then recompute the gutters from what is left. The
       0.75 margin keeps a name that wraps onto the line above its number.

    2. COLUMN INDICES ARE PAGE-LOCAL. Because of (1) -- and because a narrow column can
       collapse on any page -- integer column index N is not the same physical column on
       every page. Roles are therefore resolved per page by page_roles(), and each record
       carries its own resolved 'name'. Never reach for a fixed global index.
    """
    words = [w for w in page.extract_words(keep_blank_chars=False) if 'cid:' not in w['text']]
    h = float(page.height)

    keep = []
    for w in words:
        mid = (w['top'] + w['bottom']) / 2.0
        if mid < h * 0.14 and BANNER.search(w['text']):
            continue                                    # running header
        if mid > h * 0.93 and SEQ_RE.match(w['text']):
            continue                                    # printed page number
        if mid < h * 0.13 and (w['text'] in HEADER_WORDS or YEAR_RE.match(w['text'])):
            continue                                    # residual banner words
        keep.append(w)
    if not keep:
        return []

    # --- pass 1: rough gutters, probe for the anchors, cut the table title ----
    edges = column_edges(keep)
    probe, _, _ = walk_anchors(keep, edges, state['expect'])
    if probe:
        centres = [(a['top'] + a['bottom']) / 2.0 for a in probe]
        gaps = [centres[i + 1] - centres[i] for i in range(len(centres) - 1)]
        pitch = median(gaps) or 22.0
        cut = centres[0] - 0.75 * pitch
        trimmed = [w for w in keep if (w['top'] + w['bottom']) / 2.0 >= cut]
        if trimmed and len(trimmed) < len(keep):
            state['title_words_cut'] += len(keep) - len(trimmed)
            keep = trimmed
            edges = column_edges(keep)          # gutters re-appear once the title is gone

    # --- pass 2: the anchors we commit to --------------------------------
    anchors, rejected, newexpect = walk_anchors(keep, edges, state['expect'])
    state['expect'] = newexpect
    state['rejected'].extend((page.page_number, t) for t in rejected)
    if not anchors:
        return []

    centres = [(a['top'] + a['bottom']) / 2.0 for a in anchors]
    bands = []
    for i, a in enumerate(anchors):
        top = 0 if i == 0 else (centres[i - 1] + centres[i]) / 2.0
        bot = h if i == len(anchors) - 1 else (centres[i] + centres[i + 1]) / 2.0
        bands.append({'no': a['text'], 'top': top, 'bot': bot, 'cols': {}, 'anchor': a})

    for w in keep:
        mid = (w['top'] + w['bottom']) / 2.0
        for b in bands:
            if b['top'] <= mid < b['bot']:
                b['cols'].setdefault(col_index(edges, w), []).append(w)
                break

    recs = []
    for b in bands:
        cols = {}
        for c, ws in b['cols'].items():
            ws = [w for w in ws if w is not b['anchor']]
            if not ws:
                continue
            ws = sorted(ws, key=lambda w: (round(w['top'] / 3), w['x0']))
            cols[c] = ' '.join(w['text'] for w in ws).strip()
        recs.append({'No': b['no'], 'page': page.page_number, '_cols': cols})

    # --- roles resolved with the same granularity as the geometry ---------
    name_col, date_col = page_roles(recs)
    for r in recs:
        r['name'] = re.sub(r'\s+', ' ', (r['_cols'].get(name_col) or '')).strip()
        r['name_col'] = name_col
        r['date_col'] = date_col
    state['pages'].append((page.page_number, len(edges) - 1, name_col, date_col, len(recs)))
    return recs


def parse_pdf(path):
    state = {'expect': 1, 'rejected': [], 'pages': [], 'title_words_cut': 0}
    recs = []
    with pdfplumber.open(path) as pdf:
        npages = len(pdf.pages)
        for pg in pdf.pages:
            recs.extend(page_records(pg, state))
    if state['rejected']:
        print('   dropped {} non-sequence integer(s) in the No. column: {}'.format(
            len(state['rejected']), state['rejected'][:6]))
    return recs, npages, state


def norm_date(s):
    m = DATE_RE.match((s or '').strip())
    if not m:
        return ''
    y, mo, d = m.groups()
    return '{}-{:02d}-{:02d}'.format(y, int(mo), int(d))


def place_and_date(rec):
    """QFII rows only. Resolve the approval date INSIDE this record and take the nearest
    filled column to its left (excluding the resolved name column) as Place of
    Registration -- never a fixed global index."""
    cols = rec['_cols']
    dcols = [c for c, v in cols.items() if DATE_RE.match((v or '').strip())]
    if not dcols:
        return '', ''
    dc = min(dcols)
    regdate = norm_date(cols.get(dc, ''))
    left = [c for c in cols if c < dc and c != rec['name_col'] and (cols.get(c) or '').strip()]
    place = (cols.get(max(left)) or '').strip() if left else ''
    return place, regdate


def is_mojibake(s):
    return bool(re.search(r'[�]|Ã.|â€|ï¿½', s or ''))


def name_defects(names, listnames):
    """ACCEPTANCE TEST on Name CONTENT.

    Row-count reconciliation validates rows, not columns: v5 reconciled 997/997 while 95
    of its Names were the Yes/No flag column or the approval-date column, and list 5 row 1
    carried the table title. None of that moves a row count. These five rules are what
    actually failed, so they are what is asserted.
    """
    out = {}
    # The ticket's ListName, and the PDF's own running title, which is not always the
    # same string -- the custodian PDF is headed "List of QFII Custodian Banks" while
    # the ticket calls the list "List of Custodian Banks". Both must be caught, so a
    # bare "List of ..." / "Table ..." prefix is treated as a leak on its own. No
    # entity in any of the five registers legitimately begins with either.
    titles = tuple(t.lower() for t in listnames)
    for i, raw in enumerate(names):
        s = (raw or '').strip()
        low = s.lower()
        why = None
        if not s:
            why = 'empty'
        elif low in ('yes', 'no'):
            why = 'yes/no flag column'
        elif DATE_RE.match(s):
            why = 'date column'
        elif re.match(r'^\d+$', s):
            why = 'bare integer'
        elif len(re.sub(r'[^A-Za-z]', '', s)) < 3:
            why = 'fewer than 3 alphabetic characters'
        elif low.startswith('table ') or low.startswith('list of ') or low in titles:
            why = 'table title leaked in'
        else:
            for t in titles:
                if low.startswith(t):
                    why = 'table title leaked in'
                    break
        if why:
            out.setdefault(why, []).append((i, ascii_slug(s, 60)))
    return out

#---- Begin_MainLoop ----
summary = []
unmapped_cntry = set()

for listnr, listname, path, channelid, cotype, listlabel in LISTS:
    landing = '{}{}?channelid={}'.format(BASE, path, channelid)
    print('=' * 70)
    print('List {} | {}'.format(listnr, listname))
    print('   landing : {}'.format(landing))

    art = latest_article(channelid, listname)
    print('   article : {} ({}) [channel holds {} article(s)]'.format(
        ascii_slug(art['title'], 90), art['published'], art['channel_total']))

    pdf_url = find_attachment(art['url'])
    print('   pdf     : {}'.format(pdf_url))

    dest = os.path.join(tempfolder, 'CSRC_list{}.pdf'.format(listnr))
    download(pdf_url, dest)

    recs, npages, state = parse_pdf(dest)
    if not recs:
        raise RuntimeError('list {} parsed zero rows from {}'.format(listnr, pdf_url))

    # Column geometry is page-local. Report the spread so a layout change is visible.
    edgecounts = sorted(set(p[1] for p in state['pages']))
    namecols = sorted(set(p[2] for p in state['pages']))
    print('   geometry: columns per page {} | name col per page {} | title words cut {}'.format(
        edgecounts, namecols, state['title_words_cut']))

    declared = max(int(r['No']) for r in recs if r['No'].isdigit())

    emitted = 0
    for r in recs:
        name = r['name']
        if not name:
            continue

        cntry, regdate = 'CN', ''
        if listnr == 4:
            place, regdate = place_and_date(r)
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
    print('UNMAPPED Place of Registration values (Cntry left blank): {}'.format(
        sorted(ascii_slug(v, 40) for v in unmapped_cntry)))
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
    len(bad), [ascii_slug(v, 40) for v in bad['Name'].head(3).tolist()])
print('Mojibake check: 0 of {} Name values garbled.'.format(len(df)))

# NAME CONTENT GATE -- the v5 regression this version exists to fix
defects = name_defects(df['Name'].tolist(), [l[1] for l in LISTS])
assert not defects, 'Name column is polluted: {}'.format(
    '; '.join('{} x {} (e.g. row {} = {!r})'.format(len(v), k, v[0][0], v[0][1])
              for k, v in sorted(defects.items())))
print('Name content check: 0 of {} Names are Yes/No, a date, a bare integer, '
      'sub-3-alpha or a leaked table title.'.format(len(df)))

# RegulationType and ListProcessDate must always be populated
assert (df['RegulationType'] != '').all(), 'RegulationType is blank on {} row(s)'.format(
    int((df['RegulationType'] == '').sum()))
assert (df['ListProcessDate'] != '').all(), 'ListProcessDate is blank on {} row(s)'.format(
    int((df['ListProcessDate'] == '').sum()))

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
assert re.match(r'^\d+$', str(sample)), 'InternalID_1 did not round-trip as a digit string: {!r}'.format(sample)
assert chk['RegCode'].dropna().unique().tolist() == ['CSRC'], 'RegCode is not CSRC: {}'.format(chk['RegCode'].unique())
rt = name_defects(chk['Name'].fillna('').tolist(), [l[1] for l in LISTS])
assert not rt, 'Name column degraded on the Excel round-trip: {}'.format(sorted(rt))
print('Round-trip OK: {} rows, 43 cols, InternalID_1 sample {!r}, RegCode unique {}'.format(
    len(chk), str(sample), chk['RegCode'].unique().tolist()))

print('\n--- per-list reconciliation ---')
for nr, nm, got, dec, title, pub in summary:
    print('  List {} {:<40} emitted {:>4} | source No. max {:>4} | {}'.format(nr, nm, got, dec, pub))
print('  TOTAL emitted: {}'.format(len(df)))
print(df['ListName'].value_counts().to_string())
