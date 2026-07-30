# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# VC FSAVC  -  Financial Services Authority of St. Vincent and the Grenadines
# Source: https://fsasvg.com/
# Jira:   DECD-6325  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# All 8 pages are plain WordPress pages (LiteSpeed cache) - plain `requests`
# with a desktop User-Agent and verify=False returns 200 with full content
# for every URL, no Cloudflare/WAF challenge and no DrissionPage needed.
#
# Each page is a mix of HTML <table>s (most lists) and, for ListNr 4, a
# heading+paragraph pattern (<h5>/<h4> entity name followed by a <p> with
# address/Tel/Fax/Email/Web). Fee-schedule tables (present on most pages)
# are explicitly out of scope and skipped.
#
# Lists (from the Jira description, DECD-6325):
#   ListNr 1  List of Insurance Companies, Intermediaries and Pension Fund
#             Plans Operating in St. Vincent and the Grenadines
#             -> all non-fee tables on the page (pension plans, motor &
#                general insurers, long-term insurers, agents, brokers/
#                adjusters/underwriters, international insurers &
#                intermediaries, sales representatives)
#   ListNr 2  Mutual Funds in St. Vincent and the Grenadines
#             -> the 6 "Name of Mutual Fund(...)" tables (fee schedule
#                table excluded)
#   ListNr 3  International Banks In St. Vincent and the Grenadines
#             -> both tables: active licensed international banks, and
#                international banks under liquidation
#   ListNr 4  List of Registered Agents/Trustees/Service Providers
#             -> entities under "Currently Registered Agents/Trustees/
#                Service Providers:" only (fee schedule / forms excluded)
#   ListNr 5  Credit Unions in St. Vincent and the Grenadines
#             -> the "Name of Credit Union" table (fee schedule excluded)
#   ListNr 6  Licensed Building Societies in St. Vincent and the Grenadines
#             -> the "Building Societies" table
#   ListNr 7  Friendly Societies in St. Vincent and the Grenadines
#             -> the two-column "Name of Society" table (fee schedule
#                excluded)
#   ListNr 8  Microfinancing Institutions in St. Vincent and the Grenadines
#             -> only the "Microfinancing Institutions" table (Jira
#                Comments explicitly scope out the Money Remitter agent
#                tables on the same page)
# ------------------------------------------------------------------
import os
import re
import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "VC FSAVC"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
}

# regdict parsed from the Jira description (DECD-6325)
regdict = {
    1: {"ListName": "List of Insurance Companies, Intermediaries and Pension Fund Plans Operating in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/licensed-insurance-and-pension-plans-2/",
        "Comments": "Extract the entities from the different tables of Insurances."},
    2: {"ListName": "Mutual Funds in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/mutual-funds/",
        "Comments": "Extract the entities from the different table of funds."},
    3: {"ListName": "International Banks In St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/international-bank-list/",
        "Comments": "NEW LIST! Extract the entities from the two tables."},
    4: {"ListName": "List of Registered Agents/Trustees/Service Providers",
        "URL": "https://fsasvg.com/registered-agents-and-trustees-service-providers/",
        "Comments": "NEW LIST! Extract the entities under the “Currently Registered Agents/Trustees/Service Providers:”"},
    5: {"ListName": "Credit Unions in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/credit-union/",
        "Comments": "NEW LIST! Extract the entities from the table."},
    6: {"ListName": "Licensed Building Societies in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/building-societies/",
        "Comments": "NEW LIST! Extract the entities from the table."},
    7: {"ListName": "Friendly Societies in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/friendly-societies/",
        "Comments": "NEW LIST! Extract the entities from the table."},
    8: {"ListName": "Microfinancing Institutions in St. Vincent and the Grenadines",
        "URL": "https://fsasvg.com/money-services-businesses/",
        "Comments": "NEW LIST! Extract the entities from the table under “Microfinancing Institutions“"},
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

PROCESS_DATE = datetime.date.today().isoformat()
REG_CTRY, REG_CODE = regulatorName.split(" ", 1)  # 'VC', 'FSAVC'


def fetch_html(url, timeout=30):
    """Plain requests fetch - all fsasvg.com pages return 200 with a desktop UA."""
    r = requests.get(url, headers=HEADERS, verify=False, timeout=timeout)
    r.raise_for_status()
    return r.text


def get_main(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.find("article") or soup.body
    return main


def table_rows(table):
    """Return list of cell-text lists for every <tr>, skipping the header row."""
    trs = table.find_all("tr")
    out = []
    for tr in trs[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if any(c for c in cells):
            out.append(cells)
    return out


# Stop lookahead shared by every "label: value" field so one label's capture
# never bleeds into the next (Tel:/Fax:/Email:/Web:/Contact: can all appear
# back-to-back in these free-text address/contact blobs).
STOP = r'(?=(?:Tel:|Fax:|Email:|Web(?:site)?:|Contact:)|$)'
EMAIL_RE = re.compile(r'([\w.+-]+@[\w-]+\.[\w.-]+)')
TEL_RE = re.compile(r'Tel:\s*(.*?)' + STOP, re.I)
FAX_RE = re.compile(r'Fax:\s*(.*?)' + STOP, re.I)
EMAIL_FIELD_RE = re.compile(r'Email:\s*(.*?)' + STOP, re.I)
WEB_RE = re.compile(r'Web(?:site)?:\s*(\S+)', re.I)
ZIP_RE = re.compile(r'\b(VC\d{4})\b')


def parse_contact(text):
    """Pull phone/fax/email/website/zip out of a free-text address/contact blob."""
    out = {"phone": "", "fax": "", "email": "", "website": "", "zip": ""}
    if not text:
        return out
    m = TEL_RE.search(text)
    if m:
        out["phone"] = m.group(1).strip(" .,-")
    m = FAX_RE.search(text)
    if m:
        out["fax"] = m.group(1).strip(" .,-")
    emails = EMAIL_RE.findall(text)
    if emails:
        out["email"] = "; ".join(dict.fromkeys(emails))  # dedupe, keep order
    m = WEB_RE.search(text)
    if m:
        out["website"] = m.group(1).strip(" .,")
    m = ZIP_RE.search(text)
    if m:
        out["zip"] = m.group(1)
    return out


def strip_contact_fields(text):
    """Remove Tel/Fax/Email/Web segments, leaving the plain street address."""
    t = text
    t = TEL_RE.sub("", t)
    t = FAX_RE.sub("", t)
    t = EMAIL_FIELD_RE.sub("", t)
    t = re.sub(r'Web(?:site)?:\s*\S+', '', t, flags=re.I)
    t = re.sub(r'\s{2,}', ' ', t).strip(" ,.")
    return t


def base_row(list_nr, name, license_type="", regulation_type="Regulated"):
    row = {c: "" for c in COLUMNS}
    row.update({
        "Name": name,
        "License_Type": license_type,
        "Cntry": "VC",
        "RegulationType": regulation_type,
        "RegCtry": REG_CTRY,
        "RegCode": REG_CODE,
        "ListCode": list_nr,
        "ListName": regdict[list_nr]["ListName"],
        "ListLanguage": "EN",
        "ListProcessDate": PROCESS_DATE,
    })
    return row


all_rows = []

# ==== ListNr 1: Insurance / Pension --------------------------------------
html1 = fetch_html(regdict[1]["URL"])
main1 = get_main(html1)
tables1 = main1.find_all("table")
# tables1[0..7] are entity tables in document order (see exploration notes);
# tables1[8:] are fee schedules -> excluded.
lbl1 = 2  # insurance + pension fund list (no dedicated pension ListLabel)

for cells in table_rows(tables1[0]):  # Registered Pension Plan | Status
    if len(cells) >= 1 and cells[0]:
        r = base_row(1, cells[0], "Registered Pension Plan")
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[1]):  # Motor & General Insurance Companies
    if cells and cells[0]:
        r = base_row(1, cells[0], "Motor & General Insurance Company")
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[2]):  # Long Term Insurance Companies
    if cells and cells[0]:
        r = base_row(1, cells[0], "Long Term Insurance Company")
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[3]):  # Agent | Insurance Company Represented
    if cells and cells[0]:
        r = base_row(1, cells[0], "Insurance Agent")
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[4]):  # Intermediary | Type (brokers/adjusters/underwriters)
    if len(cells) >= 2 and cells[0]:
        r = base_row(1, cells[0], cells[1])
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[5]):  # Company | Class (international insurance cos)
    if len(cells) >= 2 and cells[0]:
        r = base_row(1, cells[0], "International Insurance Company ({})".format(cells[1]))
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[6]):  # Intermediary | Type (international)
    if len(cells) >= 2 and cells[0]:
        r = base_row(1, cells[0], "International " + cells[1])
        r["ListLabel"] = lbl1
        all_rows.append(r)

for cells in table_rows(tables1[7]):  # Insurance Company | Sales Representative(s)
    if cells and cells[0]:
        r = base_row(1, cells[0], "Insurance Sales Representative(s)")
        r["ListLabel"] = lbl1
        all_rows.append(r)

# ==== ListNr 2: Mutual Funds ------------------------------------------------
html2 = fetch_html(regdict[2]["URL"])
main2 = get_main(html2)
tables2 = main2.find_all("table")
# tables2[0..5] are "Name of Mutual Fund(...) | Type of Mutual Funds | Status";
# tables2[6] is the fee schedule -> excluded.
for t in tables2[:6]:
    for cells in table_rows(t):
        if len(cells) >= 1 and cells[0]:
            license_type = cells[1] if len(cells) >= 2 else ""
            status = cells[2].strip() if len(cells) >= 3 else "Active"
            reg_type = "Regulated" if status.lower() == "active" else status
            r = base_row(2, cells[0], license_type, reg_type)
            r["ListLabel"] = 4  # mutual funds - not a bank or insurance list
            all_rows.append(r)

# ==== ListNr 3: International Banks -----------------------------------------
html3 = fetch_html(regdict[3]["URL"])
main3 = get_main(html3)
tables3 = main3.find_all("table")

for cells in table_rows(tables3[0]):  # International Bank | License Class | Address | Main Contact
    if len(cells) >= 1 and cells[0]:
        name, lic_class = cells[0], cells[1] if len(cells) > 1 else ""
        address = cells[2] if len(cells) > 2 else ""
        contact = cells[3] if len(cells) > 3 else ""
        # Phone/Fax/Zip come from the bank's own Address cell; Email falls
        # back to the "Main Contact" cell if the address cell has none.
        addr_info = parse_contact(address)
        contact_info = parse_contact(contact)
        r = base_row(3, name, "International Bank ({})".format(lic_class) if lic_class else "International Bank")
        r["ListLabel"] = 1  # bank list
        r["Address_1"] = strip_contact_fields(address)
        r["Address_2"] = strip_contact_fields(contact)  # "Contact: <person>" note
        if "Kingstown" in address:
            r["City"] = "Kingstown"
        r["Zip"] = addr_info["zip"]
        r["Phone"] = addr_info["phone"]
        r["Fax"] = addr_info["fax"]
        r["Email"] = addr_info["email"] or contact_info["email"]
        r["Website"] = addr_info["website"] or contact_info["website"]
        all_rows.append(r)

for cells in table_rows(tables3[1]):  # International Banks Under Liquidation | Class | Liquidator
    if len(cells) >= 1 and cells[0]:
        name, lic_class = cells[0], cells[1] if len(cells) > 1 else ""
        liquidator = cells[2] if len(cells) > 2 else ""
        contact_info = parse_contact(liquidator)
        r = base_row(3, name,
                     "International Bank ({})".format(lic_class) if lic_class else "International Bank",
                     regulation_type="Under Liquidation")
        r["ListLabel"] = 1
        # No street address is published for banks in liquidation - the
        # "Liquidator" cell (person/firm handling the wind-down) goes in
        # Address_2 as a note rather than Address_1.
        r["Address_2"] = ("Liquidator: " + strip_contact_fields(liquidator)) if liquidator else ""
        r["Zip"] = contact_info["zip"]
        r["Phone"] = contact_info["phone"]
        r["Email"] = contact_info["email"]
        all_rows.append(r)

# ==== ListNr 4: Registered Agents/Trustees/Service Providers ----------------
html4 = fetch_html(regdict[4]["URL"])
main4 = get_main(html4)
heading4 = None
for h in main4.find_all(["h2", "h3"]):
    if "Currently Registered" in h.get_text():
        heading4 = h
        break

FOOTER_STOP = {"quick links", "useful links"}
entries4 = []  # list of (name, address_p_text_or_None)
if heading4 is not None:
    current_name = None
    el = heading4
    while True:
        el = el.find_next()
        if el is None or el.name in ("h2", "h3"):
            break
        if el.name in ("h4", "h5"):
            text = el.get_text(" ", strip=True)
            if text.lower() in FOOTER_STOP:
                break
            current_name = text
            entries4.append([current_name, None])
        elif el.name == "p" and current_name is not None:
            text = el.get_text(" ", strip=True)
            if ("Tel:" in text or "Email:" in text) and entries4 and entries4[-1][1] is None:
                entries4[-1][1] = text

for name, ptext in entries4:
    if not name:
        continue
    r = base_row(4, name, "Registered Agent/Trustee/Service Provider")
    r["ListLabel"] = 4  # corporate/trust service providers - not bank/insurance
    if ptext:
        info = parse_contact(ptext)
        r["Address_1"] = strip_contact_fields(ptext)
        if "Kingstown" in ptext:
            r["City"] = "Kingstown"
        r["Zip"] = info["zip"]
        r["Phone"] = info["phone"]
        r["Fax"] = info["fax"]
        r["Email"] = info["email"]
        r["Website"] = info["website"]
    all_rows.append(r)

# ==== ListNr 5: Credit Unions ------------------------------------------------
html5 = fetch_html(regdict[5]["URL"])
main5 = get_main(html5)
tables5 = main5.find_all("table")
for cells in table_rows(tables5[0]):  # Name of Credit Union
    if cells and cells[0]:
        r = base_row(5, cells[0], "Credit Union")
        r["ListLabel"] = 1  # deposit-taking cooperative - treated as bank list
        all_rows.append(r)

# ==== ListNr 6: Building Societies -------------------------------------------
html6 = fetch_html(regdict[6]["URL"])
main6 = get_main(html6)
tables6 = main6.find_all("table")
for cells in table_rows(tables6[0]):  # Building Societies
    if cells and cells[0]:
        r = base_row(6, cells[0], "Building Society")
        r["ListLabel"] = 1  # deposit-taking mutual - treated as bank list
        all_rows.append(r)

# ==== ListNr 7: Friendly Societies -------------------------------------------
html7 = fetch_html(regdict[7]["URL"])
main7 = get_main(html7)
tables7 = main7.find_all("table")
for cells in table_rows(tables7[0]):  # Name of Society | Name of Society (Continued) - two-column layout
    for name in cells:
        if name:
            r = base_row(7, name, "Friendly Society")
            r["ListLabel"] = 2  # member mutual-aid/benefit societies - insurance-like
            all_rows.append(r)

# ==== ListNr 8: Microfinancing Institutions -----------------------------------
html8 = fetch_html(regdict[8]["URL"])
main8 = get_main(html8)
micro_h2 = None
for h in main8.find_all("h2"):
    if "Microfinancing Institutions" == h.get_text(strip=True):
        micro_h2 = h
        break
if micro_h2 is not None:
    micro_table = micro_h2.find_next("table")
    for cells in table_rows(micro_table):  # Name of Institution
        if cells and cells[0]:
            r = base_row(8, cells[0], "Microfinancing Institution")
            r["ListLabel"] = 4  # microfinance - not a traditional bank/insurance list
            all_rows.append(r)

# ---- assemble & save --------------------------------------------------------
df = pd.DataFrame(all_rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode:")
print(df.groupby("ListCode")["Name"].count())
print("Columns:", len(df.columns))
print("Output:", outfile)
