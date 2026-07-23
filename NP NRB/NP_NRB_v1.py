# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# NP NRB  -  Nepal Rastra Bank (central bank of Nepal)
# Source: https://www.nrb.org.np
# Jira:   DECD-5812  (epic DECD-3438, Regulators 2026 - Internal Crawlers)
#
# One list (Jira ListNr 2): "List of Banks and Financial Institutions".
#   Landing: /category/list-of-bfis/?department=bfr lists dated releases
#   "BFI's List in English (Mid <Month> <Year>)". The most recent one is picked;
#   its link 302-redirects straight to a PDF (List-of-BFIs-*-English.pdf).
#
# The PDF groups the licensed BFIs into classes, each a 6-column table
# (S.No | Name | Date of Operation | Head Office | Paid-up Capital | Working Area):
#   Class "A" Commercial Banks        -> ListLabel 1
#   Class "B" Development Banks        -> ListLabel 1
#   Class "C" Finance Companies        -> ListLabel 4
#   Class "D" Micro Finance Inst.      -> ListLabel 4
#   Infrastructure Development Bank    -> ListLabel 1
# The trailing "Others:" section (Cooperative / Hire Purchase / foreign
# Representative Offices / Hydropower) is NOT part of the licensed-BFI list and
# is EXCLUDED (see README - flagged for ticket-owner confirmation).
#
# Rows are assigned to a class by matching each table row's y-position to the
# nearest class header above it (headers + rows can share a page), so the parse
# stays correct even if class counts change month to month.
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import requests
import urllib3
import pdfplumber
import pandas as pd

urllib3.disable_warnings()

regulatorName = "NP NRB"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.nrb.org.np"
LANDING = BASE + "/category/list-of-bfis/?department=bfr"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

COLUMNS = ['bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
           'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
           'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type',
           'Address_1', 'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax',
           'Website', 'Email', 'RegulationType', 'RegulationTypeCode',
           'RegulationDate', 'CancellationDate', 'RegCtry', 'RegCode', 'ListCode',
           'ListLanguage', 'ListValidityDate', 'ListName', 'ListProcessDate',
           'LEI Code', 'BIC SWIFT Code', 'Name - Mother Company',
           'Address_1 - Mother company', 'Address_2 -  Mother company',
           'City - Mother company', 'Zip - Mother company', 'Cntry - Mother company',
           'Phone - Mother company']

PROCESS_DATE = datetime.datetime.now().strftime('%Y-%m-%d')
LIST_CODE = 2
LIST_NAME = "List of Banks and Financial Institutions"

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}

# class header text -> (CoType, ListLabel, Typology, layout). Order = document order.
# layout "main"  : 6-col table  S.No | Name | Operation Date | Head Office | Capital | Area
# layout "others": 6-col table  S.No | Name | Office(col2) | (empty) | Contact Office(col4)
CLASS_DEFS = [
    (re.compile(r'Class:\s*"?A"?|Commercial Banks', re.I),
     ("Commercial Bank", 1, "Commercial Banks (Class A)", "main")),
    (re.compile(r'Class:\s*"?B"?|Development Banks', re.I),
     ("Development Bank", 1, "Development Banks (Class B)", "main")),
    (re.compile(r'Class:\s*"?C"?|Finance Companies', re.I),
     ("Finance Company", 4, "Finance Companies (Class C)", "main")),
    (re.compile(r'Class:\s*"?D"?|Micro\s*Finance', re.I),
     ("Microfinance Financial Institution", 4, "Micro Finance Institutions (Class D)", "main")),
    (re.compile(r'Infrastructure Development Bank', re.I),
     ("Infrastructure Development Bank", 1, "Infrastructure Development Bank", "main")),
    # "Others:" section (last page) - different 4-visible-column layout.
    # ListLabel: Cooperative & foreign-bank Representative Offices = 1 (banks);
    # Hire Purchase & Hydropower = 4 (other).
    (re.compile(r'\bA\.\s*Cooperative', re.I),
     ("Cooperative", 1, "Others - Cooperative", "others")),
    (re.compile(r'\bB\.\s*Hire\s*Purchase', re.I),
     ("Hire Purchase Company", 4, "Others - Hire Purchase", "others")),
    (re.compile(r'\bC\.\s*Representative\s*Offices', re.I),
     ("Representative Office", 1, "Others - Representative Offices", "others")),
    (re.compile(r'\bD\.\s*Hydropower', re.I),
     ("Hydropower Investment & Development Company", 4,
      "Others - Hydropower Investment and Development", "others")),
]

# foreign country names appearing in the Others "Office" column -> ISO code
COUNTRY_ISO = {"uae": "AE", "qatar": "QA", "india": "IN", "nepal": "NP"}


def parse_others_office(office):
    """Others 'Office' cell -> (address, city, cntry). For foreign Representative
    Offices the last comma-part is a country (Dubai, UAE); domestic ones default NP."""
    office = re.sub(r'\s+', ' ', (office or '')).strip(' ,')
    parts = [p.strip() for p in office.split(',') if p.strip()]
    cntry, city = "NP", ""
    if parts:
        if parts[-1].lower() in COUNTRY_ISO:
            cntry = COUNTRY_ISO[parts[-1].lower()]
            city = parts[-2] if len(parts) >= 2 else ""
        else:
            city = parts[-1]
    return office, city, cntry


def blank_row():
    return {c: '' for c in COLUMNS}


def text_lines(page, tol=3):
    """Cluster words into visual lines -> [{'text','top'}]. Replaces
    page.extract_text_lines() for older pdfplumber (< 0.7.1) that lacks it."""
    if hasattr(page, "extract_text_lines"):
        return page.extract_text_lines()
    buckets = {}
    for w in page.extract_words():
        buckets.setdefault(round(w['top'] / tol), []).append(w)
    out = []
    for key in sorted(buckets):
        ws = sorted(buckets[key], key=lambda w: w['x0'])
        out.append({'text': ' '.join(w['text'] for w in ws),
                    'top': min(w['top'] for w in ws)})
    return out


def row_top(row_obj):
    """Top y of a find_tables() row, robust across pdfplumber versions."""
    try:
        return row_obj.bbox[1]
    except Exception:
        cells = [c for c in getattr(row_obj, "cells", []) if c]
        return min(c[1] for c in cells) if cells else 0


def get(url, retries=3, **kw):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=90, verify=False, **kw)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def find_latest_pdf():
    """Scan the landing page for 'BFI's List in English (Mid <Month> <Year>)'
    anchors, pick the newest by (year, month), follow its redirect to the PDF."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(get(LANDING).text, "html.parser")
    best, best_key, best_label = None, (-1, -1), ""
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        m = re.search(r"BFI.{0,3}s List in English.*?([A-Za-z]+)\s+(\d{4})", txt)
        if not m:
            continue
        mon = MONTHS.get(m.group(1).lower())
        if not mon:
            continue
        key = (int(m.group(2)), mon)
        if key > best_key:
            best_key, best, best_label = key, a["href"], txt
    if not best:
        raise RuntimeError("No 'BFI's List in English' link found on landing page")
    print(f"   latest release: {best_label}")
    url = best if best.startswith("http") else BASE + best
    r = get(url, allow_redirects=True)          # 302 -> PDF
    dest = os.path.join(tempfolder, "bfi.pdf")
    with open(dest, "wb") as fh:
        fh.write(r.content)
    if r.content[:4] != b"%PDF":
        raise RuntimeError(f"Downloaded file is not a PDF (from {r.url})")
    return dest


def split_head_office(text):
    """'Dharmapath, Kathmandu' -> (address_1, city). City = last comma part."""
    text = re.sub(r'\s+', ' ', (text or '')).strip(' ,')
    if not text:
        return '', ''
    parts = [p.strip() for p in text.split(',') if p.strip()]
    city = parts[-1] if parts else ''
    return text, city


def norm_date(text):
    """Operation date -> ISO. Handles 'YYYY-MM-DD', 'DD/MM/YYYY', trailing '*'."""
    t = (text or '').replace('*', '').strip()
    m = re.match(r'(\d{4})-(\d{2})-(\d{2})$', t)
    if m:
        return t
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})$', t)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return ''


def parse_pdf(fp):
    out = []
    # `current` = the (cotype, listlabel, typology, layout) class in effect,
    # carried across page breaks (a class can continue onto the next page before
    # its next header appears).
    current = None
    with pdfplumber.open(fp) as pdf:
        for page in pdf.pages:
            # merged top-to-bottom stream of headers and data rows for this page
            events = []          # (top, kind, payload)
            for line in text_lines(page):
                for rx, defn in CLASS_DEFS:
                    if rx.search(line["text"]):
                        events.append((line["top"], "hdr", defn))
                        break
            for table in page.find_tables():
                for row_obj, row in zip(table.rows, table.extract()):
                    if (row[0] or '').strip().isdigit():
                        events.append((row_top(row_obj), "row", row))
            events.sort(key=lambda e: e[0])

            for _, kind, payload in events:
                if kind == "hdr":
                    current = payload
                    continue
                if current is None:
                    continue
                cotype, listlabel, typ, layout = current
                row = payload
                name = re.sub(r'\s+', ' ', (row[1] or '')).strip(' *')
                if not name:
                    continue
                r = blank_row()
                r.update({
                    "ListLabel": listlabel, "Typology": typ, "Name": name,
                    "CoType": cotype, "Cntry": "NP",
                    "ListCode": LIST_CODE, "ListName": LIST_NAME,
                })
                if layout == "main":
                    addr, city = split_head_office(row[3] if len(row) > 3 else '')
                    r["Address_1"] = addr
                    r["City"] = city
                    r["RegulationDate"] = norm_date(row[2] if len(row) > 2 else '')
                else:   # "others": Name | Office(col2) | (empty col3) | Contact Office(col4)
                    office = row[2] if len(row) > 2 else ''
                    contact = row[4] if len(row) > 4 else ''
                    addr, city, cntry = parse_others_office(office)
                    r["Address_1"] = addr
                    r["City"] = city
                    r["Cntry"] = cntry
                    r["Address_2"] = re.sub(r'\s+', ' ', (contact or '')).strip()
                out.append(r)
    return out


# ==================================================================
# RUN
# ==================================================================
print("[NP NRB] locating latest BFI list PDF ...")
pdf_path = find_latest_pdf()
print("[NP NRB] parsing PDF ...")
all_rows = parse_pdf(pdf_path)

for r in all_rows:
    r["RegCtry"] = "NP"
    r["RegCode"] = "NRB"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "EN"
    r["ListProcessDate"] = PROCESS_DATE

df = pd.DataFrame(all_rows).reindex(columns=COLUMNS, fill_value="")
now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]))
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
for typ in df['Typology'].unique():
    print(f"  {typ}: {len(df[df['Typology'] == typ])}")
print("Output:", outfile)

for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
