# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# JO CBJ  -  Central Bank of Jordan
# Source: https://www.cbj.gov.jo
# Jira:   DECD-5560  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Five lists (from the Jira description):
#   1  Directory of Banks                  -> HTML <table> (banks)          ListLabel 1
#   2  Specialized Finance Company         -> HTML cards -> detail pages     ListLabel 4
#   3  Microfinance Company                -> HTML cards -> detail pages     ListLabel 4
#   4  Electronic Payment & Money Transfer -> PDF (1 entity/page) + tables   ListLabel 4
#   5  Accredited intl. e-payment systems  -> PDF (1 entity/page)            ListLabel 4
#
# No JSON API exists; lists 1-3 are fully server-rendered (requests + BS4)
# and lists 4-5 are PDFs parsed with pdfplumber.
#
# ListLabel rule (per ticket owner): 1 = bank named in list name, 2 = insurance,
#   3 = bank & insurance, 4 = other.  Only list 1 ("Directory of Banks") = 1.
#
# Scope decisions (confirmed with ticket owner):
#   * Inactive / cancelled / revoked / insolvent / under-liquidation entities
#     are EXCLUDED. Output holds only currently-regulated entities.
#   * List 4 "include everything": the Central Bank of Jordan self-entry and the
#     active money-exchange companies (pages 22-23) ARE included. The page-21
#     branches table lists sub-locations of already-captured companies, so it is
#     treated as branch info, not separate entities.
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings()

# The cbj.gov.jo server is very slow per request (~45-65 s time-to-first-byte),
# but serves parallel requests fine, so detail pages are fetched concurrently.
MAX_WORKERS = 10

regulatorName = "JO CBJ"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.cbj.gov.jo"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RegulatorBot/1.0"}

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

PROCESS_DATE = datetime.datetime.now().strftime('%Y-%m-%d')

# Entities whose status text marks them inactive -> excluded.
INACTIVE_RE = re.compile(
    r'insolven|liquidat|cancel|revok|declared\s+insolvent', re.I)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
WEB_RE = re.compile(r'(?:https?://)?(?:www\.)?[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?:/\S*)?')
ZIP_RE = re.compile(r'\b(\d{5})\b')
PHONE_RE = re.compile(r'\+?\d[\d ]{6,}\d')


def get_soup(url, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120, verify=False)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(2)
    raise RuntimeError(f"Failed to fetch {url}")


def blank_row():
    return {c: '' for c in COLUMNS}


def split_city_zip(text):
    """From a 'P.O. Box. 5570 Amman 11953 Jordan' style string -> (city, zip)."""
    zip_m = ZIP_RE.search(text or '')
    zipcode = zip_m.group(1) if zip_m else ''
    city = ''
    if zip_m:
        # city = word immediately before the postal code
        before = text[:zip_m.start()].strip().split()
        if before:
            city = before[-1].strip(',.')
    if not city and 'Amman' in (text or ''):
        city = 'Amman'
    return city, zipcode


# ==================================================================
# LIST 1 - Directory of Banks (single HTML table)
# ==================================================================
def scrape_list1():
    url = BASE + "/EN/Pages/Bankingsectorguide"
    soup = get_soup(url)
    table = soup.find("table")
    rows = table.find_all("tr")
    header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
    out = []
    for tr in rows[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
        if len(cells) < len(header):
            continue
        rec = dict(zip(header, cells))
        name = rec.get("Bank name", "").strip()
        if not name:
            continue
        post = rec.get("post address", "")          # e.g. "11195 Amman"
        city, zipcode = split_city_zip(post)
        if not city:
            city = post.replace(re.sub(r'\D', '', post) or 'X', '').strip() or 'Amman'
        website = rec.get("website", "").strip()
        mailbox = rec.get("Mailbox", "").strip()     # P.O. Box number
        r = blank_row()
        r.update({
            "ListLabel": 1,
            "Name": name,
            "CoType": rec.get("type", "").strip(),
            "Typology": rec.get("type", "").strip(),
            "Address_2": f"P.O. Box {mailbox}" if mailbox else "",
            "City": city,
            "Zip": zipcode,
            "Cntry": "JO",
            "Phone": rec.get("phone number", "").strip(),
            "Fax": rec.get("Fax Number", "").strip(),
            "Website": website,
            "ListCode": 1,
            "ListName": "Directory of Banks",
        })
        out.append(r)
    return out


# ==================================================================
# LISTS 2 & 3 - card listing -> detail pages
# ==================================================================
def detail_field_map(soup):
    """Parse the 'General Information' block on a detail page into label->value."""
    block = soup.select_one("div.contentbdody") or soup
    text = block.get_text("\n", strip=True)
    fields = {}
    # lines look like 'Label: value'
    for line in text.split("\n"):
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if k and k not in fields:
                fields[k] = v
    return fields


def scrape_card_list(list_url, list_code, list_name):
    soup = get_soup(list_url)
    cards = soup.select("div.card a[href]")
    # de-duplicate detail URLs, keeping the card link text as a name fallback
    targets = {}
    for a in cards:
        href = a["href"]
        durl = href if href.startswith("http") else BASE + href
        targets.setdefault(durl, a.get_text(" ", strip=True).replace("Read More", "").strip())

    # the server is slow per page, so fetch all detail pages concurrently
    def fetch(durl):
        try:
            return durl, get_soup(durl)
        except Exception as e:
            print(f"   !! detail fetch failed {durl}: {e}")
            return durl, None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(fetch, targets.keys()))

    out = []
    for durl, dsoup in results:
        if dsoup is None:
            continue
        f = detail_field_map(dsoup)
        name = f.get("Company Name", "") or targets[durl]
        # exclude inactive entities (status is appended after '/' in the name)
        if INACTIVE_RE.search(name):
            print(f"   - skip inactive: {name}")
            continue
        addr = f.get("The head office address", "")
        city, zipcode = split_city_zip(f.get("P.O Box and Postal code", ""))
        if not city and addr:
            # city = first segment of the head-office address
            city = re.split(r'[–\-,]', addr)[0].strip()
        website = f.get("Website", "").strip()
        website = '' if website in ('-', '') else website
        email = f.get("E-mail address", "").strip()
        email = '' if email == '-' else email
        phone = f.get("Telephone number", "").strip()
        fax = f.get("Fax number", "").strip()
        r = blank_row()
        r.update({
            "ListLabel": 4,
            "Name": name,
            "Address_1": addr if addr != '-' else '',
            "Address_2": f.get("P.O Box and Postal code", "").replace('-', '').strip(),
            "City": city if city not in ('-', '') else 'Amman',
            "Zip": zipcode,
            "Cntry": "JO",
            "Phone": '' if phone == '-' else phone,
            "Fax": '' if fax == '-' else fax,
            "Website": website,
            "Email": email,
            "ListCode": list_code,
            "ListName": list_name,
        })
        out.append(r)
    return out


# ==================================================================
# PDF helpers
# ==================================================================
def download_pdf(path, dest_name):
    """Download a CBJ PDF; fall back to an existing tempfolder copy."""
    dest = os.path.join(tempfolder, dest_name)
    try:
        r = requests.get(BASE + path, headers=HEADERS, timeout=90, verify=False)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(dest, "wb") as fh:
                fh.write(r.content)
            return dest
        print(f"   PDF download status {r.status_code} for {path}; using cached copy")
    except Exception as e:
        print(f"   PDF download error {e}; using cached copy")
    if os.path.exists(dest):
        return dest
    raise RuntimeError(f"No PDF available for {dest_name}")


def rows_by_top(page, tol=3):
    """Reconstruct visual rows: [(max_font_size, joined_text), ...] top-to-bottom."""
    buckets = {}
    for w in page.extract_words(extra_attrs=['size']):
        buckets.setdefault(round(w['top'] / tol), []).append(w)
    out = []
    for k in sorted(buckets):
        ws = sorted(buckets[k], key=lambda w: w['x0'])
        out.append((max(w['size'] for w in ws), ' '.join(w['text'] for w in ws)))
    return out


def clean_name(name):
    # drop trailing footnote asterisks / whitespace
    return re.sub(r'\s*\*+\s*$', '', name).strip()


# ==================================================================
# LIST 4 - general register of e-payment / money-transfer companies
# ==================================================================
def scrape_list4():
    fp = download_pdf(
        "/EBV4.0/Root_Storage/AR/Domestic/A_general_register_of_licensed_companies.pdf",
        "list4.pdf")
    out = []
    with pdfplumber.open(fp) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if "Mailing address" in text:
                rec = parse_list4_profile(page, text)
                if rec:
                    out.append(rec)
            elif "Money exchange companies" in text:
                out.extend(parse_money_exchange(text))
            # page-21 branches table and the title page are intentionally skipped
    return out


def parse_list4_profile(page, text):
    if INACTIVE_RE.search(text) and re.search(r'license\s+.*(cancel|revok)', text, re.I):
        return None  # license canceled / revoked -> excluded
    rows = rows_by_top(page)
    if not rows:
        return None
    header_size = rows[0][0]
    # Name = leading rows sharing the header font size
    name_parts, body_start = [], 0
    for i, (sz, txt) in enumerate(rows):
        if abs(sz - header_size) <= 0.6:
            name_parts.append(txt)
            body_start = i + 1
        else:
            break
    name = clean_name(' '.join(name_parts))
    if not name:
        return None

    # locate label rows
    def find_row(label):
        for i, (_, txt) in enumerate(rows):
            if re.search(label, txt):
                return i
        return None

    i_addr = find_row(r'\bAddress\b')
    i_phone = find_row(r'Phone number')
    i_mail = find_row(r'Mailing address')
    i_email = find_row(r'E-?mail')

    # Address = rows from end-of-name up to (not incl.) Phone number, minus label
    addr = ''
    if i_phone is not None:
        chunk = ' '.join(t for _, t in rows[body_start:i_phone])
        chunk = re.sub(r'\bAddress\b\s*:?', '', chunk, count=1)
        chunk = re.sub(r'\bth\b', '', chunk)  # superscript artefacts
        addr = re.sub(r'\s+', ' ', chunk).strip(' :,-')

    # Mailing-address block -> city / zip / P.O. box
    mail_txt = ''
    if i_mail is not None:
        end = i_email if i_email is not None else i_mail + 3
        mail_txt = ' '.join(t for _, t in rows[i_mail:end])
    city, zipcode = split_city_zip(mail_txt)
    box_m = re.search(r'Box\.?\s*([\d]+)', mail_txt)
    addr2 = f"P.O. Box {box_m.group(1)}" if box_m else ''

    phone = ''
    if i_phone is not None:
        pm = PHONE_RE.findall(rows[i_phone][1])
        phone = '; '.join(p.strip() for p in pm)
    email_m = EMAIL_RE.search(text)
    email = email_m.group(0) if email_m else ''
    website = ''
    i_web = find_row(r'Website')
    if i_web is not None:
        wt = re.sub(r'.*Website\s*:?', '', rows[i_web][1])
        wm = WEB_RE.search(wt)
        website = wm.group(0) if wm else ''

    r = blank_row()
    r.update({
        "ListLabel": 4, "Name": name,
        "Address_1": addr, "Address_2": addr2,
        "City": city or 'Amman', "Zip": zipcode, "Cntry": "JO",
        "Phone": phone, "Website": website, "Email": email,
        "ListCode": 4,
        "ListName": "Companies licensed under the Electronic Payment and Money Transfer Bylaw",
    })
    return r


def parse_money_exchange(text):
    """Active money-exchange companies approved as e-payment system operators.
    Table rows read '<company name> <decision-no>/<year> <date>'. Cancelled ones
    (rows starting with 'Cancellation'/'*Cancellation') are excluded."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or INACTIVE_RE.search(line):
            continue
        m = re.match(r'(.+?)\s+\d{1,3}\s*/\s*\d{4}\s+\d{1,2}/\d{1,2}/\d{4}\s*$', line)
        if not m:
            continue
        name = m.group(1).strip(' *')
        if 'Name of the company' in name or len(name) < 4:
            continue
        r = blank_row()
        r.update({
            "ListLabel": 4, "Name": name, "Cntry": "JO",
            "CoType": "Money exchange company",
            "ListCode": 4,
            "ListName": "Companies licensed under the Electronic Payment and Money Transfer Bylaw",
        })
        out.append(r)
    return out


# ==================================================================
# LIST 5 - accredited international electronic payment systems
# ==================================================================
def scrape_list5():
    fp = download_pdf(
        "/EBV4.0/Root_Storage/AR/Domestic/Register_of_accredited_international_electronic_payment_systems_.pdf",
        "list5.pdf")
    out = []
    with pdfplumber.open(fp) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if "accreditation" not in text.lower():
                continue
            rows = rows_by_top(page)
            if not rows or not rows[0][1].strip().startswith('"'):
                continue
            # holder name = text between the header and the 'Website' row,
            # with the label words removed
            i_web = next((i for i, (_, t) in enumerate(rows) if 'Website' in t), len(rows))
            chunk = ' '.join(t for _, t in rows[1:i_web])
            chunk = re.sub(r'The\s+accreditation|holder|:', ' ', chunk)
            name = re.sub(r'\s+', ' ', chunk).strip()
            if not name:
                continue
            website = ''
            if i_web < len(rows):
                wt = re.sub(r'.*Website\s*:?', '', rows[i_web][1])
                wm = WEB_RE.search(wt)
                website = wm.group(0) if wm else ''
            r = blank_row()
            r.update({
                "ListLabel": 4, "Name": name, "Cntry": "JO",
                "Website": website, "ListCode": 5,
                "ListName": "Accredited international electronic payment systems",
            })
            out.append(r)
    return out


# ==================================================================
# RUN
# ==================================================================
all_rows = []
print("[List 1] Directory of Banks ...")
r1 = scrape_list1(); print(f"   {len(r1)} banks"); all_rows += r1

print("[List 2] Specialized Finance Company ...")
r2 = scrape_card_list(BASE + "/EN/List/Specialized_Finance_Company", 2,
                      "Specialized Finance Company")
print(f"   {len(r2)} entities"); all_rows += r2

print("[List 3] Microfinance Company ...")
r3 = scrape_card_list(BASE + "/EN/List/Guide_of_Microfinance_Sector", 3,
                      "Microfinance Company")
print(f"   {len(r3)} entities"); all_rows += r3

print("[List 4] Electronic Payment & Money Transfer register (PDF) ...")
r4 = scrape_list4(); print(f"   {len(r4)} entities"); all_rows += r4

print("[List 5] Accredited international e-payment systems (PDF) ...")
r5 = scrape_list5(); print(f"   {len(r5)} entities"); all_rows += r5

# common fields
for r in all_rows:
    r["RegCtry"] = "JO"
    r["RegCode"] = "CBJ"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "EN"
    r["ListProcessDate"] = PROCESS_DATE

df = pd.DataFrame(all_rows).reindex(columns=COLUMNS, fill_value="")

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]))
df.to_excel(outfile, "SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
for code in sorted(df['ListCode'].unique()):
    print(f"  List {code}: {len(df[df['ListCode'] == code])}")
print("Output:", outfile)
