# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# KH NBC  -  National Bank of Cambodia
# Jira:   DECD-6366  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Each of the 9 lists lives on its own English-language page under
# nbc.gov.kh/english/supervision/<slug>.php (plain requests works fine,
# no Cloudflare/WAF - HTTP 200 with a desktop User-Agent). Each page has
# a small "FILENAME / FORMAT / UPDATED" table with a single PDF download
# link (the "PDF icon under FORMAT" mentioned in the Jira Comments).
#
# The PDFs are bilingual (Khmer official register, Cambodia's official
# language, plus an English translation on the following text line for
# every field). pdfplumber's extract_tables() returns one 4-column table
# (No. | Name | Address | Contact) per page; the Khmer and English text
# for a given entity are NOT always laid out the same way across files -
# sometimes they're two separate physical table rows (2nd row's "No."
# cell is None), sometimes both languages are stacked with a literal
# "\n" inside a single cell. Rather than hard-code either layout, the
# parser groups rows into per-entity blocks (a new block starts every
# time the "No." column is a bare integer; blank-"No." rows are treated
# as continuation rows of the current entity) and then, within each
# block, classifies every text line as Khmer or English by checking for
# Khmer-block Unicode codepoints (U+1780-U+17FF). Only the English lines
# are kept for Name/Address (Contact is language-neutral digits, so all
# lines are kept). This matches the Jira Comments instruction to
# "extract the English line of all entities" while being robust to the
# per-file/per-row layout differences observed across the 9 PDFs.
#
# Lists (from the Jira description, DECD-6366):
#   1  Commercial Banks
#   2  Specialized Banks
#   3  Microfinance Non Deposit Taking Institutions
#   4  Microfinance Deposit Taking Institutions
#   5  Representative Offices
#   6  Financial Leasing Companies
#   7  Payment Service Institutions   (NEW LIST)
#   8  Credit Bureau Companies        (NEW LIST)
#   9  Rural Credit Institutions      (NEW LIST)
# ------------------------------------------------------------------
import os
import re
import datetime
import requests
import pandas as pd
import pdfplumber

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "KH NBC"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  # notebook environment
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")
}

BASE = "https://www.nbc.gov.kh"

# regdict parsed from the Jira description (DECD-6366).
# ListLabel: 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
#   1/2 (Commercial/Specialized Banks) and 5 (Representative Offices - all of
#   foreign BANKS, per the entity names) -> 1.
#   3/4 (microfinance, incl. deposit-taking MDIs) and 6/7/8/9 (leasing,
#   payment services, credit bureau, rural credit) -> 4, following the same
#   "non-bank microfinance = 4" judgment call used in TJ NBTAJ, since none of
#   these lists are literally named "Bank".
regdict = {
    1: {"ListName": "Commercial Banks",
        "page": f"{BASE}/english/supervision/commercial_banks.php",
        "ListLabel": 1},
    2: {"ListName": "Specialized Banks",
        "page": f"{BASE}/english/supervision/specialized_banks.php",
        "ListLabel": 1},
    3: {"ListName": "Microfinance Non Deposit Taking Institutions",
        "page": f"{BASE}/english/supervision/microfinance_non_deposit_taking_institutions.php",
        "ListLabel": 4},
    4: {"ListName": "Microfinance Deposit Taking Institutions",
        "page": f"{BASE}/english/supervision/microfinance_deposit_taking_institutions.php",
        "ListLabel": 4},
    5: {"ListName": "Representative Offices",
        "page": f"{BASE}/english/supervision/representative_offices.php",
        "ListLabel": 1},
    6: {"ListName": "Financial Leasing Companies",
        "page": f"{BASE}/english/supervision/leasing_companies.php",
        "ListLabel": 4},
    7: {"ListName": "Payment Service Institutions",
        "page": f"{BASE}/english/supervision/payment_service.php",
        "ListLabel": 4},
    8: {"ListName": "Credit Bureau Companies",
        "page": f"{BASE}/english/supervision/credit_bureau_companies.php",
        "ListLabel": 4},
    9: {"ListName": "Rural Credit Institutions",
        "page": f"{BASE}/english/supervision/rural_credit_institutions.php",
        "ListLabel": 4},
}

# SQL-Ready column order. THIS IS THE FIXED PROJECT SCHEMA (see CLAUDE.md) -
# do NOT add, remove, or reorder keys. Note the double space in
# 'Address_2 -  Mother company'.
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

KHMER_RE = re.compile(r'[ក-៿]')
ZW_RE = re.compile(r'[​‌‍]')  # zero-width space/joiner noise seen in the PDFs


def is_khmer_line(s):
    return bool(KHMER_RE.search(s))


def clean(s):
    return ZW_RE.sub('', s or '').strip()


def find_pdf_url(page_url):
    """Fetch an nbc.gov.kh English list page and return the absolute URL of its PDF link."""
    resp = requests.get(page_url, headers=HEADERS, verify=False, timeout=60)
    resp.raise_for_status()
    m = re.search(r'href="([^"]+\.pdf)"', resp.text, re.IGNORECASE)
    if not m:
        raise RuntimeError(f"No PDF link found on {page_url}")
    href = m.group(1)
    if href.startswith("http"):
        return href
    # relative path like "../../download_files/data/khmer/KH/Commercial_Banks.pdf"
    return BASE + "/" + href.replace("../../", "").lstrip("/")


def download_pdf(url, dest_path):
    resp = requests.get(url, headers=HEADERS, verify=False, timeout=90)
    resp.raise_for_status()
    if resp.content[:4] != b"%PDF":
        raise RuntimeError(f"Downloaded content from {url} is not a PDF (magic bytes: {resp.content[:20]!r})")
    with open(dest_path, "wb") as f:
        f.write(resp.content)


def parse_pdf(path):
    """Parse an NBC bilingual license-list PDF into a list of dicts with
    English name / address / contact per entity (see module docstring)."""
    blocks = []
    current = None
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    row = (list(row) + [None, None, None, None])[:4]
                    c0 = clean(row[0])
                    if re.fullmatch(r'\d+', c0):
                        if current:
                            blocks.append(current)
                        current = {"name_lines": [], "addr_lines": [], "contact_lines": []}
                    elif c0 == "":
                        pass  # continuation row of the current entity
                    else:
                        continue  # title / repeated-header row -> skip entirely
                    if current is None:
                        continue
                    for col, key in ((1, "name_lines"), (2, "addr_lines"), (3, "contact_lines")):
                        val = row[col]
                        if val:
                            for line in val.split("\n"):
                                line = clean(line)
                                if line:
                                    current[key].append(line)
    if current:
        blocks.append(current)

    entities = []
    for b in blocks:
        name_en = " ".join(l for l in b["name_lines"] if not is_khmer_line(l)).strip()
        addr_en = " ".join(l for l in b["addr_lines"] if not is_khmer_line(l)).strip()
        contact = "; ".join(b["contact_lines"])
        entities.append({"Name": name_en, "Address_1": addr_en, "Phone": contact})
    return entities


MONTHS = {"January": "01", "February": "02", "March": "03", "April": "04", "May": "05",
          "June": "06", "July": "07", "August": "08", "September": "09", "October": "10",
          "November": "11", "December": "12"}
VALIDITY_RE = re.compile(r'As at\s+(\d{1,2})\s+(\w+)\s+(\d{4})')


def find_validity_date(path):
    """Every list PDF's title block reads 'As at DD Month YYYY' (the NBC's
    own as-of date for that register) - extract it as ListValidityDate."""
    with pdfplumber.open(path) as pdf:
        text = pdf.pages[0].extract_text() or ""
    m = VALIDITY_RE.search(text)
    if not m:
        return ""
    day, month_name, year = m.groups()
    month = MONTHS.get(month_name, "")
    if not month:
        return ""
    return "{}-{}-{:02d}".format(year, month, int(day))


CITY_HINTS = ["Phnom Penh", "Battambang Province", "Siem Reap Province", "Kandal Province",
              "Kampong Cham Province", "Kampong Speu Province", "Kampong Thom Province",
              "Kampong Chhnang Province", "Kampot Province", "Kep Province", "Koh Kong Province",
              "Kratie Province", "Mondulkiri Province", "Oddar Meanchey Province", "Pailin Province",
              "Preah Sihanouk Province", "Preah Vihear Province", "Prey Veng Province",
              "Pursat Province", "Ratanakiri Province", "Stung Treng Province", "Svay Rieng Province",
              "Takeo Province", "Tboung Khmum Province"]


COUNTRY_SUFFIXES = ["kingdom of cambodia", "cambodia"]


def derive_city(address):
    """Best-effort City extraction: match a known Cambodian city/province name
    at the end of the address string, else fall back to the last comma segment.
    A handful of Payment Service Institution addresses end with a trailing
    ", Cambodia"/", Kingdom of Cambodia" country suffix (rather than a
    city/province) - strip that first so City reflects the actual city."""
    addr = address.rstrip(".")
    segments = [s.strip() for s in addr.split(",")]
    while segments and segments[-1].lower() in COUNTRY_SUFFIXES:
        segments.pop()
    addr = ", ".join(segments)
    for hint in CITY_HINTS:
        if addr.endswith(hint):
            return hint
    if segments:
        return segments[-1]
    return ""


# ---- scrape -----------------------------------------------------------------
process_date = datetime.date.today().isoformat()
rows = []

for listcode, meta in regdict.items():
    list_name = meta["ListName"]
    print(f"\n[List {listcode}] {list_name}")
    try:
        pdf_url = find_pdf_url(meta["page"])
        print("  page:", meta["page"])
        print("  pdf :", pdf_url)
        pdf_path = os.path.join(tempfolder, os.path.basename(pdf_url))
        download_pdf(pdf_url, pdf_path)
        entities = parse_pdf(pdf_path)
        validity_date = find_validity_date(pdf_path)
    except Exception as exc:
        print(f"  SKIPPED - {exc}")
        continue

    print(f"  parsed {len(entities)} entities, ListValidityDate={validity_date}")
    for e in entities:
        if not e["Name"]:
            continue
        rows.append({
            "Name": e["Name"],
            "License_Type": list_name,
            "Address_1": e["Address_1"],
            "City": derive_city(e["Address_1"]),
            "Phone": e["Phone"],
            "Cntry": "KH",
            "RegulationType": "Regulated",
            "ListValidityDate": validity_date,
            "ListCode": listcode,
            "ListName": list_name,
            "ListLanguage": "EN",
            "ListLabel": meta["ListLabel"],
            "RegCtry": "KH",
            "RegCode": "NBC",
            "ListProcessDate": process_date,
        })

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")  # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode/ListName:")
print(df.groupby(["ListCode", "ListName"]).size())
print("Columns:", len(df.columns))
print("Saved {} rows to {}".format(len(df), outfile))
