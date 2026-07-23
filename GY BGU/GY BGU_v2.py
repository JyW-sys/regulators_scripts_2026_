# GY BGU - Bank of Guyana (Jira DECD-5024)
# Source: 5 text-based PDFs on https://www.bankofguyana.org.gy  (no OCR needed).
#
# v2 changes (vs v1):
#   - List 1 (Commercial Banks): switched to camelot lattice. pdfplumber.extract_tables
#     dropped the last bank ("Bank of Baroda") because it sits at the bottom of the final
#     page with no inline address row; camelot reads the ruled grid and recovers all 6.
#   - List 5 (Pension Plans): switched to camelot lattice and now emits ONE ROW PER PLAN
#     (16 Defined Benefit + 43 Defined Contribution = 59), Name = that plan's manager
#     (the "NAMES OF PLAN MANAGERS" column). v1 deduped the column down to 7 and dropped
#     the generic "Plan's Trustees" placeholder; v2 keeps every plan's manager as-is.
#   - Lists 2/3/4 are unchanged from v1 (pdfplumber.extract_tables per-list config).

import os
import re
import shutil
import datetime
import requests
import pandas as pd
import pdfplumber
import camelot
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# camelot.utils.TemporaryDirectory registers `atexit.register(shutil.rmtree, tmpdir)` with no
# error handling. On Windows one Ghostscript-rendered page PDF stays locked until exit, so that
# cleanup raises WinError 32 and dumps a traceback after the scrape is already done. camelot
# captures this shutil.rmtree reference at register time, so wrapping it here makes the at-exit
# cleanup ignore the lock (the temp dir is left for the OS to reap). Scrape results are unaffected.
_orig_rmtree = shutil.rmtree
def _quiet_rmtree(path, *args, **kwargs):
    kwargs['ignore_errors'] = True
    return _orig_rmtree(path, *args, **kwargs)
shutil.rmtree = _quiet_rmtree

regulatorName = 'GY BGU'
print(f'Running {regulatorName} Web Scraping Tool v2.0')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if not os.path.exists(tempfolder):
    os.mkdir(tempfolder)
filename = os.path.join(tempfolder, '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7]))

regdict = {
    'GY BGU 1': 'https://www.bankofguyana.org.gy/bog/images/supervision/List%20of%20commercial%20banks_Update_2.pdf',
    'GY BGU 2': 'https://www.bankofguyana.org.gy/bog/images/bank_supervision/licensed_financial_institutions/nonbanks.pdf',
    'GY BGU 3': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Registered_Insurance_Companies%20v2.pdf',
    'GY BGU 4': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Insurance_Brokers_2025_upd.pdf',
    'GY BGU 5': 'https://www.bankofguyana.org.gy/bog/images/insurance_supervision/List_of_Registered_Pension_Plans.pdf',
}

Typology = {
    'GY BGU 1': 'Commercial Banks',
    'GY BGU 2': 'Non-Bank Financial Institutions',
    'GY BGU 3': 'Registered Insurance Companies in Guyana',
    'GY BGU 4': 'Registered Insurance Brokers in Guyana',
    'GY BGU 5': 'Pension Plan Managers',
}

# per-list extraction config for the pdfplumber path (Lists 2/3/4 only;
# Lists 1 and 5 use the camelot path below).
CONF = {
    'GY BGU 2': {'name_kw': 'institution', 'addr_kw': 'address', 'name_lineonly': True},
    'GY BGU 3': {'name_kw': 'company',     'addr_kw': 'address', 'name_lineonly': False},
    'GY BGU 4': {'name_kw': 'brokers',     'addr_kw': 'address', 'name_lineonly': False, 'date_kw': 'initial date'},
}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

HEADERS = {'User-Agent': 'Mozilla/5.0'}


def clean(s):
    if not s:
        return ''
    s = s.replace('\r', ' ')
    # normalize valid-but-non-ASCII smart punctuation to plain ASCII
    s = s.replace('‘', "'").replace('’', "'")     # curly single quotes
    s = s.replace('“', '"').replace('”', '"')     # curly double quotes
    s = s.replace('–', '-').replace('—', '-')     # en/em dash
    s = s.replace('�', "'")                            # undecodable glyph fallback
    s = re.sub(r'[ \t]+', ' ', s)
    return s.strip()


def ccell(s):
    # clean a camelot cell: lattice inserts \n inside wrapped cells, so flatten to one line.
    return clean(str(s).replace('\n', ' ')) if s is not None else ''


def fix_split_lead(s):
    # camelot lattice sometimes splits the first glyph of a name onto its own line, leaving
    # e.g. "R epublic Bank ..." after flattening. Re-join a lone leading capital to its word.
    return re.sub(r'^([A-Z]) (?=[a-z])', r'\1', s)


def name_value(cell, lineonly):
    if not cell:
        return ''
    lines = [clean(l) for l in cell.split('\n') if clean(l)]
    if not lines:
        return ''
    val = lines[0] if lineonly else ' '.join(lines)
    val = re.sub(r'^\d+[\.\)]\s*', '', val).strip()       # drop leading "1. " numbering
    return val


def first_addr_line(cell):
    if not cell:
        return ''
    for l in cell.split('\n'):
        l = clean(l)
        if not l:
            continue
        if l.lower().strip(':') in ('head office', 'branches', 'branch'):
            continue
        return l
    return ''


def col_index(header_cells, kw):
    if kw is None:
        return None
    for i, c in enumerate(header_cells):
        if c and kw in clean(c).lower():
            return i
    return None


def download(url, dest):
    r = requests.get(url, headers=HEADERS, timeout=60, verify=False)
    open(dest, 'wb').write(r.content)


def add_entity(reg, name, addr='', regdate=''):
    sqldict['Name'].append(name)
    sqldict['Address_1'].append(addr)
    sqldict['RegulationDate'].append(regdate)
    sqldict['Cntry'].append('GY')
    sqldict['RegCtry'].append(reg.split()[0])
    sqldict['RegCode'].append(reg.split()[1])
    sqldict['ListCode'].append(reg.split()[2])
    sqldict['ListName'].append(Typology[reg])
    # sqldict['ListLanguage'].append('English')
    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegulationType'].append('Regulated')
    maxlen = len(sqldict['Name'])
    for key in sqldict:
        if len(sqldict[key]) < maxlen:
            sqldict[key].append('')


def extract_list1_camelot(pdfpath, reg):
    # Ruled 3-column grid: No. | Commercial Banks | Address. One bank per numbered row;
    # extra address-only rows (blank No.) are that bank's branches and are skipped.
    for tb in camelot.read_pdf(pdfpath, pages='all', flavor='lattice'):
        for row in tb.df.values.tolist():
            if not re.fullmatch(r'\d+', ccell(row[0])):
                continue
            name = fix_split_lead(ccell(row[1]))
            addr = first_addr_line(row[2]) if len(row) > 2 else ''
            if name:
                add_entity(reg, name, addr)


def extract_list5_camelot(pdfpath, reg):
    # Ruled 3-column grid: No. | NAMES OF PENSION PLANS | NAMES OF PLAN MANAGERS.
    # One row per plan; Name = the plan's manager (3rd column). No dedupe.
    for tb in camelot.read_pdf(pdfpath, pages='all', flavor='lattice'):
        for row in tb.df.values.tolist():
            if not re.fullmatch(r'\d+\.', ccell(row[0])):
                continue
            manager = ccell(row[2]) if len(row) > 2 else ''
            if manager:
                add_entity(reg, manager)


for reg in regdict:
    pdfpath = os.path.join(tempfolder, reg.replace(' ', '_') + '.pdf')
    download(regdict[reg], pdfpath)
    print(f'Working with list {reg} - {Typology[reg]}')
    rows_before = len(sqldict['Name'])

    if reg == 'GY BGU 1':
        extract_list1_camelot(pdfpath, reg)
    elif reg == 'GY BGU 5':
        extract_list5_camelot(pdfpath, reg)
    else:
        conf = CONF[reg]
        captured = set()
        name_i = addr_i = date_i = None
        with pdfplumber.open(pdfpath) as pdf:
            for page in pdf.pages:
                for table in (page.extract_tables() or []):
                    for row in table:
                        if not row or all(c is None or not str(c).strip() for c in row):
                            continue
                        joined = clean(' '.join(c for c in row if c)).lower()
                        # (re)detect header row whenever we hit one
                        if conf['name_kw'] in joined and ('address' in joined or 'managers' in joined or 'no.' in joined):
                            name_i = col_index(row, conf['name_kw'])
                            addr_i = col_index(row, conf.get('addr_kw'))
                            date_i = col_index(row, conf.get('date_kw'))
                            continue
                        if name_i is None or name_i >= len(row):
                            continue

                        name = name_value(row[name_i], conf['name_lineonly'])
                        if not name:
                            continue

                        addr = first_addr_line(row[addr_i]) if (addr_i is not None and addr_i < len(row)) else ''
                        regdate = clean(row[date_i]) if (date_i is not None and date_i < len(row) and row[date_i]) else ''
                        add_entity(reg, name, addr, regdate)
                        captured.add(name.lower())

    print(f'  -> {len(sqldict["Name"]) - rows_before} entities')

df = pd.DataFrame(sqldict)
df = df.drop_duplicates(subset=['Name', 'ListCode'], keep='first').reset_index(drop=True)
df.to_excel(filename, sheet_name='SQL Ready', index=False)
print(f'\nDONE. {len(df)} rows -> {filename}')
print(df.groupby(['ListCode', 'ListName']).size())

# ---- name-list PDF: one PDF per (RegCtry, ListCode), written next to the xlsx ----
arial_path = r"C:\Windows\Fonts\arial.ttf"
if os.path.exists(arial_path):
    pdfmetrics.registerFont(TTFont("ArialUni", arial_path))
    FONT_NAME = "ArialUni"
else:
    FONT_NAME = "Helvetica"


def safe_filename(name):
    name = str(name).strip()
    return re.sub(r'[\\/:*?"<>|]+', "_", name) or "UNKNOWN"


def draw_header(c, y):
    c.setFont(FONT_NAME, 14)
    c.drawString(72, y, "Name")
    c.line(72, y - 4, 540, y - 4)
    c.setFont(FONT_NAME, 12)
    return y - 24


def export_list_to_pdf(data_list, pdf_filename):
    c = canvas.Canvas(pdf_filename, pagesize=letter)
    c.setFont(FONT_NAME, 12)
    x, y = 72, draw_header(c, 740)
    max_lines_per_page, line_count = 32, 0
    for item in data_list:
        c.drawString(x, y, str(item))
        y -= 20
        line_count += 1
        if line_count >= max_lines_per_page:
            c.showPage()
            c.setFont(FONT_NAME, 12)
            y = draw_header(c, 740)
            line_count = 0
    c.save()


base_name = os.path.splitext(filename)[0]
for (regctry, list_code), group in df.groupby(['RegCtry', 'ListCode'], dropna=False):
    items = group['Name'].dropna().astype(str).tolist()
    if not items:
        continue
    pdf_path = f"{base_name} - {safe_filename(regctry)}-{safe_filename(list_code)}.pdf"
    export_list_to_pdf(items, pdf_path)
    print(f"[INFO] wrote {len(items)} names -> {os.path.basename(pdf_path)}")

# clean up only the downloaded source PDFs (GY_BGU_<n>.pdf); keep the SQL Ready
# workbook and the generated name-list PDFs.
for tf in os.listdir(tempfolder):
    if re.fullmatch(r'GY_BGU_\d+\.pdf', tf):
        try:
            os.remove(os.path.join(tempfolder, tf))
        except Exception:
            print(f'ERROR trying to delete {tf}, please delete manually...')
