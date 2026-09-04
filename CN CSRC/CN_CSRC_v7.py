#---- Begin_Librairie ----
# CN CSRC v7 -- China Securities Regulatory Commission (DECD-6835)
#
# WHY v7 EXISTS
# -------------
# v6 scraped the CSRC *English* site (/csrc_en/), where each of the five registers is a
# PDF lifted out of the 2020 CSRC Annual Report, published 2021-12-08/09. That data is
# five years stale: 997 rows frozen at the 2020 year-end.
#
# The live registers live on the CHINESE site and are reissued monthly as Excel
# attachments (edition marked in the article title, e.g. 2026-06). v7 scrapes those.
# The ticket owner confirmed 2026-09-03 that the Jira ticket's /csrc_en/ targets are
# outdated and directed that CN CSRC_v4.ipynb's targets be followed instead.
#
# WHAT CHANGED FROM v6
#   * source          : /csrc_en/ annual-report PDFs -> Chinese site monthly .xls
#   * discovery       : channel JSON endpoint -> the site's own search (see find_article)
#   * parsing         : pdfplumber column geometry -> pandas, columns matched BY LABEL
#   * Name            : English (annual report) -> as published per list (see below)
#   * rows            : 997 -> ~1502
#
# NAME LANGUAGE (ticket owner, 2026-09-03): Name is what CSRC actually publishes.
# Lists 1-3 exist in Chinese only, so Name is Chinese and ListLanguage is ZH. Lists 4-5
# carry CSRC's own 英文名称 column, so Name is that English and ListLanguage is EN.
# Nothing is machine-translated. v4 ran every name through googletrans and parked the
# Chinese in 'Name - Mother Company'; that field means PARENT COMPANY in the 43-key
# schema, not "the same name in another language", so v7 leaves it empty.
#
# LIST 3 SCOPE (ticket owner, 2026-09-03): all three worksheets of the 公募基金管理机构
# workbook are in scope (150 + 15 + 14 = 179). The last two are two vintages of the same
# asset-manager register, so 8 firms appear twice under two different legal names. That
# is the requested output -- do NOT add a dedupe step.
import os
import re
import datetime
import time
import warnings
from urllib.parse import urljoin, quote

import requests
import pandas as pd

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
SEARCH_URL = BASE + '/guestweb4/s'
SESSION = requests.Session()
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                         '(KHTML, like Gecko) Chrome/120.0 Safari/537.36',
           'Referer': BASE + '/'}

# The five registers.
#   stem       -- the Chinese register title WITHOUT its trailing (edition). The site's
#                 search is the only reliable way in: these articles are republished each
#                 month under a brand-new article id, and they are not all in one channel
#                 (期货公司名录 sits in c101920 while the other four sit in c101900), so
#                 neither a hard-coded URL nor a single channel walk can find all five.
#   place_role -- what the workbook's place column MEANS. On lists 1-3 it is a CSRC
#                 supervisory jurisdiction inside China -> City. On list 4 (QFII) the same
#                 kind of column holds a foreign country -> Cntry. Same label family, two
#                 completely different fields; never let one resolver guess.
#   name_role  -- which published name column becomes Name. See the header note.
#   cotype_rules -- (substring of the worksheet name, CoType). First hit wins, else cotype.
LISTS = [
    {'nr': 1, 'stem': '证券公司名录',
     'listname': 'List of Securities Companies',
     'cotype': 'Securities Company', 'cotype_rules': [],
     'place_role': 'city', 'name_role': 'zh', 'listlabel': 4},
    {'nr': 2, 'stem': '期货公司名录',
     'listname': 'List of Futures Companies',
     'cotype': 'Futures Company', 'cotype_rules': [],
     'place_role': 'city', 'name_role': 'zh', 'listlabel': 4},
    {'nr': 3, 'stem': '公募基金管理机构名录',
     'listname': 'List of Fund Management Companies',
     'cotype': 'Fund Management Company',
     'cotype_rules': [('资产管理机构', 'Asset Management Institution Qualified for Public Fund Offering')],
     'place_role': 'city', 'name_role': 'zh', 'listlabel': 4},
    {'nr': 4, 'stem': '合格境外投资者名录',
     'listname': 'List of QFIIs',
     'cotype': 'Qualified Foreign Institutional Investor', 'cotype_rules': [],
     'place_role': 'cntry', 'name_role': 'en_then_zh', 'listlabel': 4},
    {'nr': 5, 'stem': '合格境外投资者托管行名录',
     'listname': 'List of Custodian Banks for Qualified Foreign Investors',
     'cotype': 'QFII Custodian Bank', 'cotype_rules': [],
     'place_role': 'city', 'name_role': 'en', 'listlabel': 1},
]

# Row counts measured on the editions current at 2026-09-03 (lists 1/2/3/4/5 =
# 2026-06/2026-07/2026-06/2026-07/2026-07). These registers are reissued monthly, so a
# difference is drift and is reported as a WARNING, never a failure.
EXPECTED = {1: 150, 2: 150, 3: 179, 4: 999, 5: 24}

# QFII 注册地 (Chinese) -> ISO-3166 alpha-2. Every value observed in the 2026-07 edition
# is here; anything new leaves Cntry blank and is printed at the end of the run rather
# than being guessed.
CNTRY_MAP = {
    '中国香港': 'HK', '香港': 'HK', '中国台湾': 'TW', '台湾': 'TW', '中国澳门': 'MO', '澳门': 'MO',
    '中国': 'CN', '中国大陆': 'CN', '新加坡': 'SG', '美国': 'US', '英国': 'GB', '韩国': 'KR',
    '大韩民国': 'KR', '日本': 'JP', '法国': 'FR', '澳大利亚': 'AU', '瑞士': 'CH',
    '阿联酋': 'AE', '阿拉伯联合酋长国': 'AE', '加拿大': 'CA', '开曼群岛': 'KY', '泰国': 'TH',
    '卢森堡': 'LU', '俄罗斯': 'RU', '德国': 'DE', '荷兰': 'NL', '马来西亚': 'MY', '爱尔兰': 'IE',
    '瑞典': 'SE', '卡塔尔': 'QA', '新西兰': 'NZ', '英属维尔京群岛': 'VG', '英属维京群岛': 'VG',
    '哈萨克斯坦': 'KZ', '挪威': 'NO', '意大利': 'IT', '西班牙': 'ES', '科威特': 'KW',
    '南非': 'ZA', '葡萄牙': 'PT', '毛里求斯': 'MU', '泽西岛': 'JE', '巴西': 'BR',
    '沙特阿拉伯': 'SA', '百慕大': 'BM', '阿曼': 'OM', '比利时': 'BE', '立陶宛': 'LT',
    '文莱': 'BN', '奥地利': 'AT', '塞浦路斯': 'CY', '以色列': 'IL', '土耳其': 'TR',
    # not yet seen on this register, but cheap insurance against next month's edition
    '丹麦': 'DK', '芬兰': 'FI', '冰岛': 'IS', '马耳他': 'MT', '摩纳哥': 'MC', '列支敦士登': 'LI',
    '根西岛': 'GG', '马恩岛': 'IM', '直布罗陀': 'GI', '波兰': 'PL', '匈牙利': 'HU',
    '捷克': 'CZ', '希腊': 'GR', '罗马尼亚': 'RO', '保加利亚': 'BG', '克罗地亚': 'HR',
    '斯洛伐克': 'SK', '斯洛文尼亚': 'SI', '拉脱维亚': 'LV', '爱沙尼亚': 'EE', '乌克兰': 'UA',
    '印度': 'IN', '印度尼西亚': 'ID', '菲律宾': 'PH', '越南': 'VN', '巴基斯坦': 'PK',
    '斯里兰卡': 'LK', '孟加拉国': 'BD', '蒙古': 'MN', '巴林': 'BH', '约旦': 'JO',
    '黎巴嫩': 'LB', '埃及': 'EG', '摩洛哥': 'MA', '尼日利亚': 'NG', '肯尼亚': 'KE',
    '墨西哥': 'MX', '智利': 'CL', '阿根廷': 'AR', '哥伦比亚': 'CO', '秘鲁': 'PE',
    '巴拿马': 'PA', '巴哈马': 'BS', '巴巴多斯': 'BB', '库拉索': 'CW',
}

TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company', 'ListCode']

EDITION_RE = re.compile(r'[（(]\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*[）)]')
CJK_RE = re.compile(r'[㐀-䶿一-鿿]')
A_TAG_RE = re.compile(r'<a\b([^>]*)>', re.I)
ATTR_RE = re.compile(r'([A-Za-z_:][-\w:.]*)\s*=\s*"([^"]*)"')
TAG_RE = re.compile(r'<[^>]+>')
DIGITS_RE = re.compile(r'^\d{1,5}$')
ISO_DATE_RE = re.compile(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})')

#---- Begin_Function ----
def add_row(**kw):
    """Single funnel into sqldict. Appends to EVERY one of the 43 keys; raises on an
    unknown key so the schema cannot drift."""
    unknown = set(kw) - set(SCHEMA_KEYS)
    if unknown:
        raise KeyError('add_row got key(s) not in the 43-key schema: {}'.format(sorted(unknown)))
    for k in SCHEMA_KEYS:
        v = kw.get(k, '')
        sqldict[k].append(str(v) if v is not None else '')
    lens = set(len(v) for v in sqldict.values())
    if len(lens) != 1:
        raise AssertionError('sqldict columns fell out of sync: {}'.format(lens))


def ascii_slug(s, limit=90):
    """cp1252 console safety. The Windows control server's console cannot encode a single
    Chinese character, so NOTHING scraped is ever printed raw -- it all comes through here.
    Chinese text degrades to '?', which is why the logs identify a list by its English
    ListName and its ASCII URL, never by its Chinese title."""
    return re.sub(r'[^\x20-\x7e]', '?', s or '')[:limit]


def decode_bytes(raw):
    """Chinese government sites lie about their charset. Never trust r.encoding: decode the
    bytes explicitly, utf-8 first then gb18030 (a superset of GBK/GB2312)."""
    for enc in ('utf-8', 'gb18030'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def http(method, url, tries=4, **kw):
    """The corporate TLS proxy drops connections intermittently and csrc.gov.cn is slow to
    answer a search POST. Always verify=False (a cert error here is the proxy, not the
    site) and retry with escalating backoff."""
    last = None
    for i in range(tries):
        try:
            r = SESSION.request(method, url, headers=HEADERS, verify=False, timeout=90, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            last = e
            print('      retry {}/{} after {}: {} {}'.format(
                i + 1, tries, type(e).__name__, method, ascii_slug(url, 70)))
            time.sleep(4 * (i + 1))
    raise last


def tag_attrs(chunk):
    """Attribute values are stripped. The search results' href ends in a literal CRLF
    ('//www.csrc.gov.cn/.../content.shtml\\r\\n'); left in place it is sent as part of the
    path, the server answers 200 with a page that has no attachment on it, and the run
    fails several steps later blaming the wrong thing."""
    return dict((k.lower(), v.strip()) for k, v in ATTR_RE.findall(chunk))


def find_article(stem, listname):
    """Resolve a register to its CURRENT edition through the site's own search.

    Why search and not a fixed URL or a channel walk:
      * every monthly reissue gets a new article id, so a hard-coded content.shtml goes
        stale the moment CSRC publishes the next edition;
      * the five registers are not in one channel -- 期货公司名录 is in c101920 and the
        other four in c101900 -- so no single channel listing covers the set.

    Selection is by title, not by position: keep only hits whose title starts with the
    register's exact stem (this is what separates 合格境外投资者名录 from
    合格境外投资者托管行名录), read the (YYYY年M月) edition out of the title, and take the
    newest. Anything without a parseable edition is ignored rather than ranked."""
    r = http('POST', SEARCH_URL,
             data={'searchWord': stem, 'uc': '1', 'siteCode': 'bm56000001', 'column': '全部'})
    html = decode_bytes(r.content)

    seen, cands = set(), []
    for chunk in A_TAG_RE.findall(html):
        attrs = tag_attrs(chunk)
        href, title = attrs.get('href', ''), TAG_RE.sub('', attrs.get('title', '')).strip()
        if not href or not title.startswith(stem):
            continue
        m = EDITION_RE.search(title)
        if not m:
            continue
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = BASE + href
        key = (title, href)
        if key in seen:
            continue
        seen.add(key)
        cands.append({'title': title, 'url': href,
                      'edition': '{}-{:02d}'.format(m.group(1), int(m.group(2)))})

    if not cands:
        raise RuntimeError('search returned no dated edition of {} ({} <a> tags scanned)'
                           .format(listname, len(A_TAG_RE.findall(html))))
    cands.sort(key=lambda c: c['edition'], reverse=True)
    editions = sorted(set(c['edition'] for c in cands), reverse=True)
    if len(editions) > 1:
        print('   editions offered: {} -- taking the newest'.format(', '.join(editions[:6])))
    return cands[0]


def article_details(article_url):
    """From the article page: the attachment URL and the publication date.

    The attachment filename is never hard-coded -- it is republished under a new article
    folder each month. quote() keeps '%' safe so an already-percent-encoded Chinese
    filename is not double-encoded."""
    html = decode_bytes(http('GET', article_url).content)

    links = re.findall(r'href="([^"]+\.(?:xls|xlsx))"', html, re.I)
    if not links:
        raise RuntimeError('no .xls/.xlsx attachment on {}'.format(ascii_slug(article_url, 80)))
    attach = urljoin(article_url, quote(links[0], safe='/:%'))

    pub = ''
    m = re.search(r'<meta[^>]+name="PubDate"[^>]+content="([^"]+)"', html, re.I)
    if m:
        d = ISO_DATE_RE.search(m.group(1))
        if d:
            pub = '{}-{:02d}-{:02d}'.format(d.group(1), int(d.group(2)), int(d.group(3)))
    if not pub:
        print('   NOTE: no PubDate meta on the article; ListValidityDate falls back to the edition')
    return attach, pub


def download(url, dest):
    """Save the workbook and identify its real format from the magic bytes rather than the
    file extension -- CSRC serves some '.xls' links that are actually zipped .xlsx, and
    pandas picks the wrong engine if it trusts the name."""
    r = http('GET', url)
    blob = r.content
    if blob.startswith(b'\xd0\xcf\x11\xe0'):
        engine = 'xlrd'                       # OLE2 compound file = real .xls
    elif blob.startswith(b'PK'):
        engine = 'openpyxl'                   # zip container = .xlsx
    else:
        raise RuntimeError('not an Excel workbook: {} ({} bytes, magic {!r})'.format(
            ascii_slug(url, 70), len(blob), blob[:8]))
    with open(dest, 'wb') as fh:
        fh.write(blob)
    return dest, engine


def cell(v):
    """Excel numerics arrive as floats, so a 序号 of 1 reads back as 1.0 -- which fails the
    'is this an integer' row test and would silently drop the row instead of raising.
    Whole floats are normalised to their integer form first; everything else is
    stringified and whitespace-collapsed."""
    if v is None:
        return ''
    if isinstance(v, float):
        if v != v:                      # NaN
            return ''
        if v == int(v):
            return str(int(v))
    s = str(v).strip()
    if s.lower() in ('nan', 'nat', 'none'):
        return ''
    return re.sub(r'\s+', ' ', s)


def resolve_roles(labels, place_role):
    """Map worksheet columns to roles BY LABEL, never by position.

    Positional indexing is what rots between editions: v4 assumed the header was on row 0
    of the QFII sheet, but the current file puts a title note there and the header on row 1,
    so v4's header assignment would silently take the note as column names. Labels are
    stable across editions in a way that row/column offsets are not.

    Order matters -- '合格境外投资者托管行中文名称' ends with BOTH '名称' and '中文名称',
    so the specific suffixes are tested first."""
    roles = {}
    for c, lab in labels.items():
        if lab == '序号':
            roles['seq'] = c
        elif lab.endswith('英文名称'):
            roles.setdefault('name_en', c)
        elif lab.endswith('中文名称'):
            roles.setdefault('name_zh', c)
        elif lab.endswith('名称') or lab.endswith('名单'):
            roles.setdefault('name_zh', c)
        elif lab == '批准日期':
            roles.setdefault('date', c)
        elif lab.startswith('辖区') or lab == '注册地':
            roles.setdefault(place_role, c)
    return roles


def sheet_tables(path, engine, place_role):
    """Yield one parsed table per worksheet that actually holds register rows.

    Iterating every sheet (rather than naming one) is deliberate: list 2's data is on
    'Sheet3' not 'Sheet1', list 5 carries two empty trailing sheets, and list 3 carries
    three real tabs whose names differ only by a LEADING SPACE
    ('取得公募资格的资产管理机构' vs ' 取得公募资格的资产管理机构'). Selecting sheets by
    name would need all of that hard-coded and would break on the next reissue.

    The header row is found by looking for '序号' in the first few rows, which is what makes
    the QFII sheet's row-0 title note harmless. A row is a register row only if its 序号 cell
    is a small integer -- that single rule drops the title note, the blank spacer rows and
    the trailing '注：...' footnote without any of them being enumerated."""
    xl = pd.ExcelFile(path, engine=engine)
    for sheet in xl.sheet_names:
        raw = pd.read_excel(xl, sheet_name=sheet, header=None, dtype=object)
        if raw.empty:
            continue
        try:
            grid = raw.map(cell)            # pandas >= 2.1
        except AttributeError:
            grid = raw.applymap(cell)       # the control server's pandas

        hdr = None
        for i in range(min(6, len(grid))):
            if '序号' in list(grid.iloc[i]):
                hdr = i
                break
        if hdr is None:
            continue

        labels = dict((c, grid.iat[hdr, c]) for c in range(grid.shape[1]) if grid.iat[hdr, c])
        roles = resolve_roles(labels, place_role)
        if 'seq' not in roles or not ({'name_zh', 'name_en'} & set(roles)):
            continue

        body = grid.iloc[hdr + 1:]
        rows = []
        for _, r in body.iterrows():
            seq = r[roles['seq']]
            if not DIGITS_RE.match(seq):
                continue
            rows.append(dict((role, r[c]) for role, c in roles.items()))
        if not rows:
            continue

        # A merged jurisdiction cell reads as blank on every row but the first of the merge
        # (list 2 groups its rows under one 辖区). Forward-fill rebuilds it. Applied to
        # 'city' ONLY: on the QFII list the same-shaped column is a COUNTRY, and two of its
        # rows are genuinely blank -- filling those down would invent a nationality.
        if 'city' in roles:
            carry = ''
            for row in rows:
                if row.get('city'):
                    carry = row['city']
                else:
                    row['city'] = carry

        yield sheet, rows


def cotype_for(sheet, spec):
    for needle, cotype in spec['cotype_rules']:
        if needle in sheet:
            return cotype
    return spec['cotype']


def pick_name(row, name_role):
    """Returns (name, language). Lists 4-5 publish an official 英文名称; list 4 leaves it
    blank on a handful of rows, and those fall back to the Chinese name (ticket owner,
    2026-09-03) rather than being dropped. ListLanguage then describes the language the
    row's Name is actually in."""
    zh, en = row.get('name_zh', ''), row.get('name_en', '')
    if name_role == 'zh':
        return zh, 'ZH'
    if name_role == 'en':
        return en, 'EN'
    return (en, 'EN') if en else (zh, 'ZH')


def norm_date(s):
    m = ISO_DATE_RE.search(s or '')
    if not m:
        return ''
    return '{}-{:02d}-{:02d}'.format(m.group(1), int(m.group(2)), int(m.group(3)))


def is_mojibake(s):
    return bool(re.search(r'[�]|Ã.|â€|ï¿½', s or ''))


def name_defects(names, listnames):
    """ACCEPTANCE TEST ON NAME CONTENT.

    Row counts validate rows, not columns -- v5 of this scraper reconciled 997/997 while 95
    of its Names were a Yes/No flag column. So Name is asserted on its own.

    The length rule had to change for v7: lists 1-3 are Chinese, and a perfectly good name
    like 国泰基金管理有限公司 contains ZERO Latin letters, so v6's 'at least 3 alphabetic
    characters' test would have rejected every row on three of the five lists. A name now
    has to carry either 2+ CJK characters or 3+ Latin letters."""
    out = {}
    titles = tuple(t.lower() for t in listnames)
    for i, raw in enumerate(names):
        s = (raw or '').strip()
        low = s.lower()
        why = None
        if not s:
            why = 'empty'
        elif low in ('yes', 'no', 'nan', 'none'):
            why = 'placeholder value'
        elif ISO_DATE_RE.match(s):
            why = 'date column'
        elif re.match(r'^\d+$', s):
            why = 'bare integer'
        elif len(CJK_RE.findall(s)) < 2 and len(re.sub(r'[^A-Za-z]', '', s)) < 3:
            why = 'too short to be a name'
        elif '名录' in s or '名单' in s or s in ('公司名称', '中文名称', '英文名称', '序号'):
            why = 'header or table title leaked in'
        elif low.startswith('table ') or low.startswith('list of ') or low in titles:
            why = 'header or table title leaked in'
        if why:
            out.setdefault(why, []).append((i, ascii_slug(s, 60)))
    return out

#---- Begin_MainLoop ----
summary = []
unmapped_cntry = {}

for spec in LISTS:
    listnr, listname = spec['nr'], spec['listname']
    print('=' * 78)
    print('List {} | {}'.format(listnr, listname))

    art = find_article(spec['stem'], listname)
    print('   edition : {}'.format(art['edition']))
    print('   article : {}'.format(art['url']))

    attach, published = article_details(art['url'])
    print('   file    : {}'.format(ascii_slug(attach, 110)))

    dest = os.path.join(tempfolder, 'CSRC_list{}{}'.format(
        listnr, os.path.splitext(attach.split('?')[0])[1] or '.xls'))
    dest, engine = download(attach, dest)
    print('   engine  : {} | published {}'.format(engine, published or '(none)'))

    validity = published or (art['edition'] + '-01')
    emitted, sheets_seen = 0, []

    for sheet, rows in sheet_tables(dest, engine, spec['place_role']):
        cotype = cotype_for(sheet, spec)
        seqs = [int(r['seq']) for r in rows]
        contiguous = seqs == list(range(1, len(seqs) + 1))
        sheets_seen.append((sheet, len(rows), cotype, contiguous))

        for row in rows:
            name, lang = pick_name(row, spec['name_role'])
            if not name:
                continue

            city, cntry = '', 'CN'
            if spec['place_role'] == 'city':
                city = row.get('city', '')
            else:
                place = row.get('cntry', '')
                if not place:
                    cntry = ''
                elif place in CNTRY_MAP:
                    cntry = CNTRY_MAP[place]
                else:
                    unmapped_cntry[place] = unmapped_cntry.get(place, 0) + 1
                    cntry = ''

            add_row(
                Name=name,
                InternalID_1=row['seq'],
                InternalID_1_type='CSRC list sequence number',
                CoType=cotype,
                City=city,
                Cntry=cntry,
                RegulationType='Regulated',
                RegulationDate=norm_date(row.get('date', '')),
                RegCtry='CN',
                RegCode='CSRC',
                ListCode=str(listnr),
                ListLabel=str(spec['listlabel']),
                ListLanguage=lang,
                ListName=listname,
                Typology=listname,
                ListValidityDate=validity,
                ListProcessDate=processdate,
            )
            emitted += 1

    if not emitted:
        raise RuntimeError('list {} emitted zero rows from {}'.format(listnr, ascii_slug(attach, 80)))

    for sheet, n, cotype, contiguous in sheets_seen:
        print('   sheet   : {:<62} rows {:>4} | {}'.format(
            ascii_slug(sheet, 62) or '(unnamed)', n,
            'seq 1..n OK' if contiguous else '*** SEQUENCE NOT CONTIGUOUS ***'))
    exp = EXPECTED.get(listnr)
    flag = 'matches the 2026-09-03 baseline' if emitted == exp else \
           '*** DRIFT vs 2026-09-03 baseline {} (diff {:+d}) ***'.format(exp, emitted - exp)
    print('   emitted : {} rows across {} sheet(s) | {}'.format(emitted, len(sheets_seen), flag))
    summary.append((listnr, listname, emitted, exp, art['edition'], validity, len(sheets_seen)))
    time.sleep(2)

print('=' * 78)
if unmapped_cntry:
    print('UNMAPPED 注册地 values (Cntry left blank, never guessed):')
    for k, n in sorted(unmapped_cntry.items(), key=lambda kv: -kv[1]):
        print('   {} x {}'.format(n, ascii_slug(k, 40)))
else:
    print('All QFII places of registration mapped to ISO-3166 alpha-2.')

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

# column order + count must still be exactly the 43-key schema
assert list(df.columns) == SCHEMA_KEYS, 'column order drifted from the 43-key schema'
assert len(df.columns) == 43, 'expected 43 columns, got {}'.format(len(df.columns))

# mojibake gate -- a garbled Chinese Name passes every row-count check
bad = df[df['Name'].map(is_mojibake)]
assert len(bad) == 0, 'mojibake detected in {} Name values, e.g. {}'.format(
    len(bad), [ascii_slug(v, 40) for v in bad['Name'].head(3).tolist()])
print('Mojibake check: 0 of {} Name values garbled.'.format(len(df)))

defects = name_defects(df['Name'].tolist(), [l['listname'] for l in LISTS])
assert not defects, 'Name column is polluted: {}'.format(
    '; '.join('{} x {} (e.g. row {} = {!r})'.format(len(v), k, v[0][0], v[0][1])
              for k, v in sorted(defects.items())))
print('Name content check: 0 of {} Names are a placeholder, a date, a bare integer, '
      'too short, or a leaked header.'.format(len(df)))

# every Chinese-language list must really be carrying Chinese, and every English one
# English -- this is the check that would catch a name/language column swap
zh = df[df['ListLanguage'] == 'ZH']['Name']
en = df[df['ListLanguage'] == 'EN']['Name']
assert zh.map(lambda s: bool(CJK_RE.search(s))).all(), \
    'a ZH row carries a Name with no Chinese character'
assert en.map(lambda s: bool(re.search(r'[A-Za-z]', s))).all(), \
    'an EN row carries a Name with no Latin letter'
print('Language check: {} ZH names all contain CJK, {} EN names all contain Latin.'.format(
    len(zh), len(en)))

# constants that must never be blank
for col in ('RegulationType', 'ListProcessDate', 'ListValidityDate', 'RegCtry', 'RegCode', 'ListCode'):
    assert (df[col] != '').all(), '{} is blank on {} row(s)'.format(col, int((df[col] == '').sum()))

# Excel silently coerces all-digit strings to floats and eats leading zeros
for c in TEXT_COLS:
    df[c] = df[c].astype(str).replace('nan', '')

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

# read the workbook back and prove nothing degraded in the round-trip
chk = pd.read_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', dtype=str)
assert len(chk) == len(df), 'row count changed on round-trip: {} -> {}'.format(len(df), len(chk))
assert list(chk.columns) == SCHEMA_KEYS, 'column order changed on round-trip'
sample = chk['InternalID_1'].dropna().iloc[0]
assert re.match(r'^\d+$', str(sample)), 'InternalID_1 did not round-trip as a digit string: {!r}'.format(sample)
assert chk['RegCode'].dropna().unique().tolist() == ['CSRC'], 'RegCode is not CSRC: {}'.format(chk['RegCode'].unique())
rt = name_defects(chk['Name'].fillna('').tolist(), [l['listname'] for l in LISTS])
assert not rt, 'Name column degraded on the Excel round-trip: {}'.format(sorted(rt))
assert chk['Name'].map(lambda s: bool(CJK_RE.search(str(s)))).sum() == \
    df['Name'].map(lambda s: bool(CJK_RE.search(s))).sum(), 'Chinese names lost on the round-trip'
print('Round-trip OK: {} rows, 43 cols, InternalID_1 sample {!r}, Chinese preserved.'.format(
    len(chk), str(sample)))

print('\n--- per-list reconciliation ---')
for nr, nm, got, exp, edition, validity, nsheets in summary:
    print('  List {} {:<52} {:>4} rows (baseline {:>4}) | edition {} | {} sheet(s)'.format(
        nr, nm, got, exp, edition, nsheets))
print('  TOTAL emitted: {}'.format(len(df)))
print('\n--- rows per ListCode ---')
print(df['ListCode'].value_counts().sort_index().to_string())
print('\n--- rows per CoType ---')
print(df['CoType'].value_counts().to_string())
print('\n--- ListLanguage ---')
print(df['ListLanguage'].value_counts().to_string())
