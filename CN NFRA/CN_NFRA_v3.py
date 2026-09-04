#---- Begin_Librairie ----

import os
import re
import sys
import json
import datetime
import warnings

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

requests.packages.urllib3.disable_warnings()
warnings.filterwarnings('ignore')

# The control server runs a cp1252 console: printing a scraped Chinese string
# raises UnicodeEncodeError and kills the run. Belt: force the stream to utf-8
# where the interpreter allows it. Braces: never hand raw scraped text to
# print() - always route it through safe() below.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass


def safe(value, limit=80):
    """ASCII-only, length-capped rendering of any scraped value, for print()."""
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return '[' + ', '.join(safe(v, limit) for v in value) + ']'
    text = str(value).encode('ascii', 'replace').decode('ascii')
    return text if len(text) <= limit else text[:limit] + '...'


#---- Begin_fileName ----

regulatorName = 'CN NFRA'
print('Running {} Web Scraping Tool v.3.0'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        try:
            os.remove(os.path.join(tempfolder, rem))
        except OSError:
            pass
else:
    os.mkdir(tempfolder)

print('[INFO] : - scriptfolder = {}'.format(scriptfolder))


#---- Begin_Variable ----

# NOTE: the ticket URLs all point at www.cbirc.gov.cn. CBIRC was replaced by the
# National Financial Regulatory Administration (NFRA) in 2023 and the domain
# www.cbirc.gov.cn no longer resolves for us. Everything now lives on www.nfra.gov.cn.
BASE = 'https://www.nfra.gov.cn'

# Landing page named in the ticket (same path, new host).
TICKET_PAGE = BASE + '/cn/view/pages/zhengwuxinxi/zhengfuxinxi.html#1'

# JSON/AJAX endpoints behind the AngularJS grid (no browser needed).
ITEM_API = BASE + '/cbircweb/DocInfo/SelectDocByItemIdAndChild?itemId={itemId}&pageSize={pageSize}&pageIndex={pageIndex}'
DOC_API = BASE + '/cbircweb/DocInfo/SelectByDocId?docId={docId}'

# "机构名单" (institution lists) column of 政务信息 -> 政府信息公开.
ITEM_ID = 863

HEADERS = {
    'User-Agent': ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Referer': TICKET_PAGE,
    'Accept': 'application/json, text/plain, */*',
}

regdict = {
    'CN NFRA 1': TICKET_PAGE,
    'CN NFRA 2': TICKET_PAGE,
    'CN NFRA 3': TICKET_PAGE,
    'CN NFRA 4': TICKET_PAGE,
    'CN NFRA 5': TICKET_PAGE,
}

# ListName exactly as written on the Jira ticket DECD-6831.
ListNames = {
    'CN NFRA 1': 'List of Banking Financial Institutions',
    'CN NFRA 2': 'List of Branches of Foreign Banks',
    'CN NFRA 3': 'List of Insurance Institutions',
    'CN NFRA 4': 'List of Foreign Reinsurance Company Branches',
    'CN NFRA 5': 'List of Financial Holding Companies',
}

# Chinese title keyword used to DISCOVER the current document each run.
# Never hard-code a docId or a file URL - the regulator republishes twice a year.
KeyWords = {
    'CN NFRA 1': '银行业金融机构法人名单',
    'CN NFRA 2': '外国及港澳台银行分行名单',
    'CN NFRA 3': '保险机构法人名单',
    'CN NFRA 4': '外国再保险公司分公司名单',
    'CN NFRA 5': '金融控股公司法人名单',
}

# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
ListLabels = {
    'CN NFRA 1': 1,   # banking legal persons
    'CN NFRA 2': 1,   # branches of foreign / HK / Macau / Taiwan banks
    'CN NFRA 3': 2,   # insurance legal persons
    'CN NFRA 4': 2,   # branches of foreign reinsurers
    'CN NFRA 5': 4,   # financial holding companies - holding vehicles, not operating banks/insurers
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

SQLKEYS = list(sqldict.keys())
assert len(SQLKEYS) == 43, '[ERROR] : - schema must have exactly 43 keys, got {}'.format(len(SQLKEYS))

# Columns that Excel would happily turn into floats / strip leading zeros from.
TEXT_COLS = ['InternalID_1', 'InternalID_2', 'InternalID_3', 'Zip', 'Phone', 'Fax',
             'Zip - Mother company', 'Phone - Mother company', 'ListCode']

# Expected header of every one of the five PDFs.
EXPECTED_HEADER = ['序号', '中文全称', '英文全称', '机构编码', '机构类型', '监管责任单位']


#---- Begin_Function ----

def add_row(**kw):
    """Append exactly one value to EVERY one of the 43 keys. Raises on an unknown key."""
    unknown = set(kw) - set(SQLKEYS)
    if unknown:
        raise KeyError('[ERROR] : - unknown sqldict key(s): {}'.format(sorted(unknown)))
    for key in SQLKEYS:
        sqldict[key].append(kw.get(key, ''))


def get_json(url):
    """GET a NFRA JSON endpoint. verify=False because of the corporate TLS proxy."""
    r = requests.get(url, headers=HEADERS, verify=False, timeout=90)
    r.raise_for_status()
    # Do not trust r.encoding on Chinese government sites: decode r.content explicitly.
    raw = r.content
    for enc in ('utf-8', 'gb18030'):
        try:
            txt = raw.decode(enc)
            break
        except UnicodeDecodeError:
            txt = None
    if txt is None:
        raise ValueError('[ERROR] : - could not decode response from {}'.format(url))
    payload = json.loads(txt)
    if payload.get('rptCode') != 200:
        raise ValueError('[ERROR] : - API said {} for {}'.format(payload.get('msg'), url))
    return payload['data']


def list_item_documents(item_id, max_pages=10, page_size=20):
    """Discover every document published under an itemId. The API caps pageSize at 20,
    so we page until we have the declared total or run out of pages."""
    docs = []
    declared = None
    for page in range(1, max_pages + 1):
        data = get_json(ITEM_API.format(itemId=item_id, pageSize=page_size, pageIndex=page))
        if declared is None:
            declared = data.get('total')
            print('[INFO] : - itemId {} declares {} documents'.format(item_id, declared))
        rows = data.get('rows') or []
        if not rows:
            break
        docs.extend(rows)
        if declared is not None and len(docs) >= declared:
            break
    print('[INFO] : - collected {} document headers from itemId {}'.format(len(docs), item_id))
    return docs


def parse_asof(title):
    """'银行业金融机构法人名单（截至2025年12月末）' -> '2025-12-31' (best effort)."""
    m = re.search(r'截至\s*(\d{4})\s*年\s*(\d{1,2})\s*月', title or '')
    if not m:
        return ''
    year, month = int(m.group(1)), int(m.group(2))
    if month == 12:
        return '{}-12-31'.format(year)
    nxt = datetime.date(year + (month // 12), (month % 12) + 1, 1)
    return (nxt - datetime.timedelta(days=1)).strftime('%Y-%m-%d')


def pick_latest(docs, keyword):
    """Newest document whose title contains keyword. Loud SKIPPED message if none."""
    hits = [d for d in docs if keyword in (d.get('docSubtitle') or d.get('docTitle') or '')]
    if not hits:
        print("SKIPPED - no document whose title contains '{}'".format(safe(keyword)))
        return None
    hits.sort(key=lambda d: d.get('publishDate') or '', reverse=True)
    return hits[0]


def download_attachment(doc_id):
    """Resolve the document's attachment (the real list PDF) and download it.
    Returns (local_path, attachment_title, publishDate, docSubtitle)."""
    data = get_json(DOC_API.format(docId=doc_id))
    attachments = data.get('attachmentInfoVOList') or []
    if not attachments:
        print('SKIPPED - no attachment on docId {}'.format(doc_id))
        return None, None, None, None
    att = attachments[0]
    url = att.get('urlOtherName') or ('/' + att.get('attachmentUrl', '').strip('/') + '/' + att.get('attachmentName', ''))
    url = BASE + url if url.startswith('/') else url
    r = requests.get(url, headers=HEADERS, verify=False, timeout=300)
    r.raise_for_status()
    # Soft-404 guard: an HTML error page served with HTTP 200 is not a PDF.
    if not r.content.startswith(b'%PDF'):
        print('SKIPPED - {} is not a PDF (first bytes {!r})'.format(url, r.content[:16]))
        return None, None, None, None
    path = os.path.join(tempfolder, 'doc_{}.pdf'.format(doc_id))
    with open(path, 'wb') as fh:
        fh.write(r.content)
    print('[INFO] : - downloaded {} ({} bytes) -> {}'.format(safe(att.get('title')), len(r.content), os.path.basename(path)))
    return path, att.get('title'), data.get('publishDate'), data.get('docSubtitle')


def clean(cell):
    """Collapse the hard line breaks pdfplumber leaves inside wrapped table cells."""
    if cell is None:
        return ''
    return re.sub(r'\s+', ' ', str(cell).replace('\n', ' ')).strip()


def extract_pdf_rows(path):
    """Every data row of a NFRA institution-list PDF, in source order, no dedup."""
    rows = []
    header = None
    with pdfplumber.open(path) as pdf:
        n_pages = len(pdf.pages)
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for raw in table:
                cells = [clean(c) for c in raw]
                if not any(cells):
                    continue
                # The header repeats on most pages - record it once, skip every repeat.
                if cells[:len(EXPECTED_HEADER)] == EXPECTED_HEADER or cells[0] == '序号':
                    if header is None:
                        header = cells
                    continue
                rows.append(cells)
    return rows, header, n_pages


def is_missing(value):
    """NFRA writes '无' (none) or '-' where an entity has no official English name."""
    return value in ('', '无', '-', '--', '/', 'None')


#---- Begin_MainLoop ----

print('[INFO] : - discovering current documents from {}'.format(ITEM_API.format(itemId=ITEM_ID, pageSize=20, pageIndex=1)))
documents = list_item_documents(ITEM_ID)

summary = []

for reg in regdict:
    listcode = reg.split()[2]
    print('\n' + '=' * 70)
    print('Working with list {} - {}'.format(reg, ListNames[reg]))

    doc = pick_latest(documents, KeyWords[reg])
    if doc is None:
        summary.append((reg, ListNames[reg], 0, 0, 'SKIPPED - document not found'))
        continue

    doc_id = doc['docId']
    title = doc.get('docSubtitle') or doc.get('docTitle') or ''
    print('[INFO] : - matched docId {} "{}" published {}'.format(doc_id, safe(title), doc.get('publishDate')))

    path, att_title, publish_date, subtitle = download_attachment(doc_id)
    if path is None:
        summary.append((reg, ListNames[reg], 0, 0, 'SKIPPED - no usable attachment'))
        continue

    rows, header, n_pages = extract_pdf_rows(path)
    print('[INFO] : - {} pages, header = {}'.format(n_pages, safe(header)))
    print('[INFO] : - extracted {} data rows'.format(len(rows)))

    if header is None:
        print('SKIPPED - no header row found in {}'.format(os.path.basename(path)))
        summary.append((reg, ListNames[reg], 0, 0, 'SKIPPED - no header'))
        continue

    idx = {name: header.index(name) for name in EXPECTED_HEADER if name in header}
    missing_cols = [c for c in EXPECTED_HEADER if c not in idx]
    if missing_cols:
        print('[WARN] : - PDF header is missing expected column(s) {}'.format(safe(missing_cols)))

    regdate = (publish_date or doc.get('publishDate') or '')[:10]
    validity = parse_asof(title)

    # The last 序号 printed by the regulator is its own declared record count.
    declared = 0
    for cells in reversed(rows):
        seq = cells[idx['序号']] if '序号' in idx and idx['序号'] < len(cells) else ''
        if seq.isdigit():
            declared = int(seq)
            break

    added = 0
    for cells in rows:
        def col(name):
            i = idx.get(name)
            return cells[i] if i is not None and i < len(cells) else ''

        cn_name = col('中文全称')
        en_name = col('英文全称')
        code = col('机构编码')
        cotype = col('机构类型')

        # Name: the official English name the regulator itself publishes; fall back to
        # the Chinese legal name when NFRA prints none.
        used_chinese = is_missing(en_name)
        name = cn_name if used_chinese else en_name
        if is_missing(name):
            continue

        add_row(
            ListLabel=ListLabels[reg],
            Name=name,
            InternalID_1=str(code),
            InternalID_1_type='Organization code' if code else '',
            CoType=cotype,
            Cntry='CN',
            RegulationType='Regulated',
            RegulationDate=regdate,
            RegCtry='CN',
            RegCode='NFRA',
            ListCode=listcode,
            # Honest per-row language: the PDF carries both a Chinese and an English
            # name column, but NFRA leaves the English blank for ~1/4 of the banks.
            ListLanguage='ZH' if used_chinese else 'EN',
            ListValidityDate=validity,
            ListName=ListNames[reg],
            ListProcessDate=processdate,
        )
        added += 1

    print('[INFO] : - list {} -> {} rows added (source declares {})'.format(listcode, added, declared))
    if declared and added != declared:
        print('[WARN] : - ROW COUNT MISMATCH on list {}: scraped {} vs declared {}'.format(listcode, added, declared))
    summary.append((reg, ListNames[reg], added, declared, 'OK'))

    lengths = {len(v) for v in sqldict.values()}
    assert len(lengths) == 1, '[ERROR] : - sqldict columns out of sync after list {}: {}'.format(listcode, lengths)

print('\n' + '=' * 70)
print('RECONCILIATION (scraped vs declared by the source)')
for reg, lname, added, declared, status in summary:
    flag = 'OK' if (declared and added == declared) else ('CHECK' if status == 'OK' else status)
    print('  {:12s} {:48s} scraped={:6d} declared={:6d}  {}'.format(reg, lname[:48], added, declared, flag))
print('  TOTAL scraped = {}'.format(sum(s[2] for s in summary)))


#---- Begin_writer and save df to excel ----

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)
df = df[df['Name'] != '']

# Keep IDs / zips / phones as TEXT so Excel cannot turn '000001' into 1 or
# '40003764029' into 4.000376e+10.
for c in TEXT_COLS:
    df[c] = df[c].astype(str).replace('nan', '')

out_path = os.path.join(scriptfolder, filename)
with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='SQL Ready', index=False)
    ws = writer.sheets['SQL Ready']
    header_row = [c.value for c in ws[1]]
    for col_name in TEXT_COLS:
        if col_name in header_row:
            letter = ws.cell(row=1, column=header_row.index(col_name) + 1).column_letter
            for cell in ws[letter][1:]:
                cell.number_format = '@'

print('Saved {} rows to {}'.format(len(df), out_path))

# Read the workbook back and assert a known all-digit ID survived as a string.
check = pd.read_excel(out_path, sheet_name='SQL Ready', dtype=str)
assert len(check) == len(df), '[ERROR] : - round-trip row count changed'
sample = check.loc[check['ListCode'] == '3', 'InternalID_1']
if len(sample):
    val = sample.iloc[0]
    print('[INFO] : - round-trip check InternalID_1 = {} (type {})'.format(safe(val), type(val).__name__))
    assert isinstance(val, str) and val.isdigit() and val.startswith('0'), \
        '[ERROR] : - leading-zero ID was destroyed by Excel: {!r}'.format(val)
print('[INFO] : - round-trip check passed, {} columns'.format(len(check.columns)))
