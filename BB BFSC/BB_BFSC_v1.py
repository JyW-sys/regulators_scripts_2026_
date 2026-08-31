# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# BB BFSC  -  Financial Services Commission, Barbados
# Jira:   DECD-6820  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Landing page (all three lists):  https://www.fsc.gov.bb/regulated-entities
#
# The landing page is plain server-rendered HTML (no JS, no Cloudflare).
# Inside <div id="pageContent"> there is a single <ul> holding one PDF link
# per division:
#       "Pensions - <Month> - <Year>"        (NOT in scope for this ticket)
#       "Securities - <Month> - <Year>"      -> ListNr 1
#       "Credit Unions - <Month> - <Year>"   -> ListNr 2
#       "Insurance - <Month> - <Year>"       -> ListNr 3
# The hrefs are date-stamped upload paths such as
#   /viewPDF/documents/2026-08-05-12-55-16-Securities---List-of-licensed-...pdf
# so they change every quarter.  Links are therefore resolved by the LABEL
# TEXT of the anchor, never by file name (see resolve_pdf_links()).
#
# All three lists are text-layer PDFs (no OCR needed), but each has a
# completely different internal layout:
#
#  1) Securities - one landscape spreadsheet export with ruling lines.
#     pdfplumber.find_tables() finds one table per registration category
#     (Self-Regulatory Organisations, Securities Company, Investment Adviser,
#     Dealers, Underwriters, Reporting Issuers, Other issuers, Mutual Funds,
#     Mutual Fund Administrator General/Restricted) plus a final
#     "STATISTICAL SUMMARY" table which is skipped.
#     Column 0 = the COMPANY; the remaining columns are the natural persons
#     (brokers / traders / advisers / dealers) registered *for* that company.
#     The Jira comment says "Collect companies", so only column 0 is kept
#     (plus column 1 of the Mutual Funds table, which holds sub-funds).
#     page.extract_table() is NOT used: it silently drops entities that sit
#     on a row whose left-hand cell was not detected (e.g. "Quantas Advantage
#     Inc." in Reporting Issuers).  Instead the column is rebuilt from cell
#     geometry, with a per-physical-line fallback for such gap rows.
#
#  2) Credit Unions - one portrait page, no ruling lines at all, just
#     "<Registration No.> <Credit Union Name>" text lines.  Parsed with a
#     line regex.  A stray leftover heading ("COMBINATION/HYBRID PENSION
#     PLANS (DB + DC)") sits at the bottom of the page and is ignored
#     because it does not start with a registration number.
#
#  3) Insurance - 46 portrait pages, one section per licence category.
#     Section titles are bold >18pt and start with "REGISTERED "/"STATISTIC".
#     Entity names are the non-bold ~12pt lines; everything else (page
#     header, "No. of licensees: N", the bold "- Class N Licence" descriptor,
#     the "NAME" column header and the page footer) is filtered out.
#     Class 1 and Class 2 each end with a bold "DORMANT" sub-heading; the
#     entities under it ARE part of the FSC's own licensee count, so they are
#     kept and flagged in License_Type.
#     Per the Jira comment, the Class 3 AGENTS, SUB-AGENTS and SALESMEN
#     sections are NOT collected (rule: skip any section whose title contains
#     "AGENT" or "SALESM").
#
# Reconciliation is automatic: both the Securities PDF and the Insurance PDF
# publish their own counts ("STATISTICAL SUMMARY" table / "No. of licensees:
# N" per section).  Those numbers are parsed and printed next to the scraped
# counts at the end of the run.
# ------------------------------------------------------------------
#---- Begin_Librairie ----
import os
import re
import datetime
from collections import defaultdict

import requests
import pandas as pd
import pdfplumber
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()

#---- Begin_fileName ----
regulatorName = "BB BFSC"
print("Running {} Web Scraping Tool v.1.0".format(regulatorName))

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

#---- Begin_Variable ----
BASE = "https://www.fsc.gov.bb"
ENTRY_URL = BASE + "/regulated-entities"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
}

REG_CTRY = "BB"
REG_CODE = "BFSC"
LIST_LANGUAGE = "EN"          # Barbados publishes in English only
REGULATION_TYPE = "Regulated"  # all three lists are positive / authorised registers

# regdict parsed from the Jira description (DECD-6820).
# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
regdict = {
    1: {"ListName": "List of Securities",
        "ListLabel": 4,
        "link_keyword": "securities",
        "local": "securities.pdf"},
    2: {"ListName": "List of Credit Unions",
        "ListLabel": 4,
        "link_keyword": "credit union",
        "local": "creditunions.pdf"},
    3: {"ListName": "List of Insurances",
        "ListLabel": 2,
        "link_keyword": "insurance",
        "local": "insurance.pdf"},
}

# Jira comment on ListNr 1: 'if the name contains "inactive", do NOT collect it'.
# Applied defensively to all three lists.
INACTIVE_RE = re.compile(r'inactive', re.I)

# Jira comment on ListNr 3: do NOT collect Class 3 Agent, Sub-Agents, Salesmen.
INS_SKIP_SECTION_RE = re.compile(r'AGENT|SALESM', re.I)

# Lines in the Insurance PDF that are chrome rather than entity names.
INS_NOISE_RE = re.compile(
    r'^(WWW\.FSC\.GOV\.BB'
    r'|NAME'
    r'|No\. of licensees.*'
    r'|\(dissolved.*'
    r'|.*Financial Services Commission)$', re.I)
INS_TITLE_RE = re.compile(r'^(REGISTERED |STATISTIC)', re.I)

# "as at July 31, 2026" / "JULY 31, 2026"
VALIDITY_RE = re.compile(r'\b([A-Za-z]{3,9})\s+(\d{1,2}),\s*(\d{4})\b')
MONTHS = {m.lower(): i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], start=1)}

# ---- THE FIXED PROJECT SCHEMA (see CLAUDE.md) - do NOT add/remove/rename keys.
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}


#---- Begin_Function ----
def add_row(**kwargs):
    """Append one record, filling EVERY key of sqldict so columns can never
    drift out of alignment.  Unknown keys raise immediately."""
    unknown = set(kwargs) - set(sqldict)
    if unknown:
        raise KeyError("add_row got keys that are not in the fixed schema: {}".format(sorted(unknown)))
    for key in sqldict:
        sqldict[key].append(kwargs.get(key, ''))


def norm(s):
    """Collapse whitespace / normalise the curly apostrophes used in the PDFs."""
    if not s:
        return ''
    s = s.replace('\n', ' ').replace(' ', ' ')
    return re.sub(r'\s+', ' ', s).strip()


def resolve_pdf_links(url=ENTRY_URL):
    """Return {link_keyword: (label_text, absolute_pdf_url)} resolved by the
    LABEL TEXT of the anchors inside <div id="pageContent"> - never by file
    name, because the FSC re-uploads every quarter under a new timestamped
    path."""
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=60)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    content = soup.find(id='pageContent') or soup
    found = {}
    for a in content.find_all('a', href=True):
        href = a['href']
        if '.pdf' not in href.lower():
            continue
        label = norm(a.get_text(' ', strip=True))
        if not href.lower().startswith('http'):
            href = BASE + '/' + href.lstrip('/')
        for meta in regdict.values():
            kw = meta['link_keyword']
            if kw in label.lower() and kw not in found:
                found[kw] = (label, href)
    return found


def download_pdf(url, dest_path):
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=180)
    resp.raise_for_status()
    if resp.content[:4] != b'%PDF':
        raise RuntimeError("{} did not return a PDF (first bytes: {!r})".format(url, resp.content[:20]))
    with open(dest_path, 'wb') as fh:
        fh.write(resp.content)
    return dest_path


def find_validity_date(pdf_path):
    """Every list PDF carries its own as-of date on page 1 ('as at July 31,
    2026' / 'JULY 31, 2026') -> ListValidityDate."""
    with pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[0].extract_text() or ''
    for m in VALIDITY_RE.finditer(text):
        month = MONTHS.get(m.group(1).lower())
        if month:
            return '{}-{:02d}-{:02d}'.format(m.group(3), month, int(m.group(2)))
    return ''


# ---------- Securities PDF ---------------------------------------------------
def column_entries(page, table, colidx):
    """Rebuild one column of a ruled pdfplumber table from geometry.

    Returns a list of (cell_top, cell_bottom, text) in reading order.  The
    y-bounds are the CELL's, not the ink's: the source is an Excel export and
    text is vertically centred inside tall merged cells, so ink positions
    cannot be used to line a sub-fund up with its parent fund.

    Why not table.extract()?  Rows whose left-hand cell was not detected are
    returned with their text silently dropped (observed: "Quantas Advantage
    Inc." in Reporting Issuers).  Here the column's x-band is taken from the
    cell boundaries, words are bucketed into the real cell y-intervals (which
    correctly keeps wrapped names such as "CIBC ... (formerly FirstCaribbean
    ... Limited)" together), and any word that falls in a gap between cells is
    emitted as its own physical line."""
    xs = sorted({round(c[0], 1) for r in table.rows for c in r.cells if c} |
                {round(c[2], 1) for r in table.rows for c in r.cells if c})
    if colidx + 1 >= len(xs):
        return []
    x_left, x_right = xs[colidx], xs[colidx + 1]

    ivals = sorted({(c[1], c[3]) for r in table.rows for c in r.cells
                    if c and abs(c[0] - x_left) < 2})

    words = [w for w in page.extract_words()
             if w['x0'] >= x_left - 2 and w['x1'] <= x_right + 3
             and w['top'] >= table.bbox[1] - 2 and w['bottom'] <= table.bbox[3] + 2]

    buckets = defaultdict(list)
    for w in words:
        cy = (w['top'] + w['bottom']) / 2.0
        hit = [iv for iv in ivals if iv[0] < cy < iv[1]]
        if hit:                                   # inside a real table cell
            key = min(hit, key=lambda iv: iv[1] - iv[0])
        else:                                     # gap row -> its own line
            key = (round(w['top'], 1), round(w['bottom'], 1))
        buckets[key].append(w)

    out = []
    for key in sorted(buckets):
        # crop+extract_text rather than joining extract_words(): the latter
        # inserts spurious spaces inside words (e.g. "s ub-funds").
        text = norm(page.crop((x_left, key[0] - 0.5, x_right, key[1] + 0.5)).extract_text() or '')
        if text:
            out.append((key[0], key[1], text))
    return out


def parse_securities(pdf_path):
    """-> list of dicts {Name, License_Type, Name - Mother Company}."""
    rows = []
    declared = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.find_tables():
                col0 = column_entries(page, table, 0)
                if not col0:
                    continue
                header = col0[0][2]
                body = col0[1:]

                # The final table is the FSC's own "STATISTICAL SUMMARY"
                # (header "Category" / "Number") - keep its numbers for the
                # reconciliation print-out, but do not emit entities.
                if header.strip().lower() == 'category':
                    col1 = column_entries(page, table, 1)
                    for (t, b, cat), (t2, b2, num) in zip(body, col1[1:]):
                        if num.strip().isdigit():
                            declared[cat.strip()] = int(num.strip())
                    continue

                # License_Type = the category header without the "(companies)"
                # qualifier that only distinguishes it from the person columns.
                lic = re.sub(r'\s*\(companies\)\s*$', '', header).strip()

                for top, bottom, name in body:
                    rows.append({'Name': name, 'License_Type': lic,
                                 'Name - Mother Company': ''})

                # Mutual Funds table: column 1 holds the registered SUB-FUNDS.
                if 'mutual fund' in lic.lower() and 'administrator' not in lic.lower():
                    col1 = column_entries(page, table, 1)
                    for top, bottom, sub in col1[1:]:
                        cy = (top + bottom) / 2.0
                        parents = [n for (t, b, n) in body if t <= cy]
                        rows.append({'Name': sub,
                                     'License_Type': lic + ' - Sub-Fund',
                                     'Name - Mother Company': parents[-1] if parents else ''})
    return rows, declared


def normalise_securities_name(name):
    """The Investment Adviser table lists its 22nd company as
    'Investment Advisers Registered on Behalf of The Bank of Nova Scotia'
    (a phrasing, not a company name).  Keep the company only - this is what
    makes the section reconcile with the PDF's own count of 22."""
    m = re.match(r'^.*?\bRegistered on Behalf of\s+(.+)$', name, re.I)
    return m.group(1).strip() if m else name


# ---------- Credit Unions PDF ------------------------------------------------
CU_ROW_RE = re.compile(r'^(\d{1,6})\s+(\S.*)$')


def parse_credit_unions(pdf_path):
    """-> list of dicts {Name, InternalID_1, License_Type}.  The page has no
    ruling lines; every data line is '<Registration No.> <Credit Union Name>'.
    The section heading is the line immediately above the
    'Registration No. | ... Name' column header, so it is read from the file
    rather than hard-coded."""
    rows = []
    section = ''
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            previous = ''
            for line in (page.extract_text() or '').split('\n'):
                line = norm(line)
                m = CU_ROW_RE.match(line)
                if m:
                    rows.append({'Name': norm(m.group(2)),
                                 'InternalID_1': m.group(1),
                                 'License_Type': section})
                elif re.match(r'^Registration No\.', line, re.I) and previous:
                    section = previous.title()
                previous = line
    return rows


# ---------- Insurance PDF ----------------------------------------------------
def parse_insurance(pdf_path):
    """-> (rows, declared) where rows is a list of dicts
    {Name, License_Type} and declared maps section title -> the FSC's own
    'No. of licensees: N'."""
    sections = []
    cur = None
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = defaultdict(list)
            for w in page.extract_words(extra_attrs=['fontname', 'size']):
                lines[round(w['top'] / 3) * 3].append(w)
            for key in sorted(lines):
                ws = sorted(lines[key], key=lambda w: w['x0'])
                text = norm(' '.join(w['text'] for w in ws))
                bold = any('Bold' in w['fontname'] for w in ws)
                size = max(w['size'] for w in ws)

                if bold and size > 18 and INS_TITLE_RE.match(text):
                    cur = {'title': text, 'declared': None, 'licence': '',
                           'dormant': False, 'rows': []}
                    sections.append(cur)
                    continue
                if cur is None:
                    continue

                m = re.match(r'^No\. of licensees:\s*(\d+)', text)
                if m:
                    cur['declared'] = int(m.group(1))
                    continue
                if bold and 'Licence' in text and not cur['licence']:
                    cur['licence'] = text
                    continue
                if bold and text.upper() == 'DORMANT':
                    cur['dormant'] = True
                    continue
                if INS_NOISE_RE.match(text) or bold:
                    continue
                if not (11.5 <= size <= 12.5):     # entity names are 12pt
                    continue
                cur['rows'].append((text, cur['dormant']))

    rows = []
    declared = {}
    for sec in sections:
        title = sec['title']
        if title.upper().startswith('STATISTIC'):
            continue
        declared[title] = sec['declared']
        if INS_SKIP_SECTION_RE.search(title):      # Class 3 Agents / Sub-Agents / Salesmen
            print("      skipping section (Jira: not to be collected): {} "
                  "[{} lines]".format(title, len(sec['rows'])))
            continue
        # "INSURANCE COMPANIES - Class 1 Licence insurance company ..." ->
        # "Insurance Companies - Class 1 Licence"
        lic = sec['licence']
        m = re.match(r'^(.*?-\s*Class\s*\d+\s*Licence)', lic, re.I)
        lic = (m.group(1) if m else lic or title).title().replace('Licence', 'Licence')
        for name, dormant in sec['rows']:
            rows.append({'Name': name,
                         'License_Type': lic + (' - Dormant' if dormant else ''),
                         'section': title})
    return rows, declared


#---- Begin_MainLoop ----
print("\nResolving PDF links on {} ...".format(ENTRY_URL))
links = resolve_pdf_links()
for kw, (label, href) in sorted(links.items()):
    print("  {:<14} -> {!r}\n{:>20}{}".format(kw, label, '', href))

summary = {}
skipped_inactive = 0

for listcode in sorted(regdict):
    meta = regdict[listcode]
    kw = meta['link_keyword']
    print("\n[List {}] {}".format(listcode, meta['ListName']))
    if kw not in links:
        print("  SKIPPED - no anchor whose label contains {!r} on {}".format(kw, ENTRY_URL))
        continue
    label, href = links[kw]
    pdf_path = os.path.join(tempfolder, meta['local'])
    download_pdf(href, pdf_path)
    validity = find_validity_date(pdf_path)
    print("  label   : {}".format(label))
    print("  pdf     : {}".format(href))
    print("  validity: {}".format(validity))

    if listcode == 1:
        records, declared = parse_securities(pdf_path)
        for rec in records:
            rec['Name'] = normalise_securities_name(rec['Name'])
        summary[listcode] = {'declared': declared}
    elif listcode == 2:
        records = parse_credit_unions(pdf_path)
        summary[listcode] = {'declared': {}}
    else:
        records, declared = parse_insurance(pdf_path)
        summary[listcode] = {'declared': declared}

    kept = 0
    for rec in records:
        name = norm(rec.get('Name', ''))
        if not name:
            continue
        if INACTIVE_RE.search(name):
            skipped_inactive += 1
            print("      dropped (contains 'inactive'): {}".format(name))
            continue
        internal_id = rec.get('InternalID_1', '')
        add_row(
            ListLabel=meta['ListLabel'],
            Name=name,
            InternalID_1=internal_id,
            InternalID_1_type='Registration Number' if internal_id else '',
            License_Type=rec.get('License_Type', ''),
            Cntry=REG_CTRY,
            RegulationType=REGULATION_TYPE,
            RegCtry=REG_CTRY,
            RegCode=REG_CODE,
            ListCode=listcode,
            ListLanguage=LIST_LANGUAGE,
            ListValidityDate=validity,
            ListName=meta['ListName'],
            ListProcessDate=processdate,
            **{'Name - Mother Company': rec.get('Name - Mother Company', '')}
        )
        kept += 1
    summary[listcode]['kept'] = kept
    print("  collected {} rows".format(kept))

#---- Begin_writer and save df to excel ----
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

print("\n==== SUMMARY ====")
print(df.groupby(['ListCode', 'ListName']).size().to_string())
print("Total rows :", len(df))
print("Columns    :", len(df.columns))
print("Dropped for containing 'inactive':", skipped_inactive)

print("\n---- reconciliation against the counts the FSC prints in its own PDFs ----")
if 1 in summary and summary[1]['declared']:
    print("[List 1 Securities] STATISTICAL SUMMARY table vs scraped License_Type:")
    got = df[df['ListCode'] == 1]['License_Type'].value_counts().to_dict()
    for cat, num in summary[1]['declared'].items():
        print("   {:<45} FSC={:>4}".format(cat, num))
    for lic, num in sorted(got.items()):
        print("   scraped {:<37} {:>4}".format(lic, num))
if 3 in summary and summary[3]['declared']:
    print("[List 3 Insurance] 'No. of licensees' per section vs scraped:")
    ins = df[df['ListCode'] == 3]
    for title, num in summary[3]['declared'].items():
        if INS_SKIP_SECTION_RE.search(title):
            print("   {:<45} FSC={:>4}   NOT COLLECTED (Jira)".format(title, num))
        else:
            key = title.replace('REGISTERED ', '')
            print("   {:<45} FSC={:>4}".format(title, num))
    print("   scraped by License_Type:")
    for lic, num in sorted(ins['License_Type'].value_counts().items()):
        print("      {:<45} {:>4}".format(lic, num))
