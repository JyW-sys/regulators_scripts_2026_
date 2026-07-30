# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# PW PFIC  -  Palau Financial Institutions Commission
# Source: https://ropfic.org/central-registry/
# Jira:   DECD-6348  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The page is behind an nginx-based WAF, so plain requests gets a 403.
# We use DrissionPage (real Chrome) to render it, then parse with
# BeautifulSoup.
#
# Layout: the "Central Registry" page lists, in order:
#   <h3>Active Banks in the Republic of Palau</h3>
#     <h5>Bank Name</h5> <p>address</p> <p>Tel/Fax[/website]</p>
#       <p>Home Country / Date of Charter / License Status</p>  (x5 banks;
#       one bank additionally has a leading "formerly named ..." note <p>)
#   <h3>Closed Banks ...</h3>  <table> ...
#   <h3>Denied Bank License Application</h3>  <table> ...
#   <h3>Withdrawn Bank License Application</h3>  <table> ...
#   <h3>Bank License Applications Currently Under Review</h3>  <table> ...
#
# Per the Jira Comments field: "Extract only the entities under the
# subtitle 'Active Banks in the Republic of Palau'" - the 4 tables
# (closed / denied / withdrawn / under-review) are explicitly out of
# scope for this list.
#
# Lists (from the Jira description):
#   ListNr 1  "Active banks in the Republic of Palau" -> the 5 <h5> banks
#             under the "Active Banks..." <h3> heading only
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

regulatorName = "PW PFIC"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

URL = "https://ropfic.org/central-registry/"

# regdict parsed from the Jira description (DECD-6348)
regdict = {
    1: {"ListName": "Active banks in the Republic of Palau",
        "URL": URL,
        "Comments": "Extract only the entities under the subtitle 'Active Banks in the Republic of Palau'"},
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


def fetch_html(url, timeout=90):
    """Open Chrome via DrissionPage, pass the WAF challenge, return rendered HTML."""
    opt = ChromiumOptions().auto_port()
    dp = ChromiumPage(opt)
    try:
        dp.get(url)
        waited = 0
        while waited < timeout:
            time.sleep(3); waited += 3
            if "Just a moment" not in dp.title and dp.s_ele("tag:h3"):
                break
        html = dp.html
    finally:
        dp.quit()
    return html


ADDR_RE = re.compile(r'^P\.?\s*O\.?\s*Box', re.I)
TEL_RE = re.compile(r'^Tel:\s*(?P<phone>[\d()/\-\s]+?)\s*Fax:\s*(?P<fax>[\d()/\-\s]+?)(?:\s+(?P<website>www\.\S+))?$', re.I)
META_RE = re.compile(r'Home Country:\s*(?P<home>.+?)\s*Date of Charter:\s*(?P<charter>\S+)\s*License Status:\s*(?P<status>.+)$', re.I)
ZIP_RE = re.compile(r'(\d{5})\s*$')


# ---- scrape ---------------------------------------------------------------
html = fetch_html(URL)
soup = BeautifulSoup(html, "html.parser")
main = soup.find("main") or soup.find("article") or soup.body
for tag in main(["script", "style", "nav", "header", "footer"]):
    tag.decompose()

# find the "Active Banks in the Republic of Palau" <h3> heading
active_h3 = None
for h in main.find_all("h3"):
    if "Active Banks" in h.get_text():
        active_h3 = h
        break
if active_h3 is None:
    raise RuntimeError("Could not find the 'Active Banks in the Republic of Palau' heading")

process_date = datetime.date.today().isoformat()
rows = []
bank_name = None
block = []  # <p> texts collected for the current bank


def flush(name, ptexts):
    if not name:
        return
    address = ""
    city = ""
    zipc = ""
    phone = ""
    fax = ""
    website = ""
    reg_date = ""
    for t in ptexts:
        m_tel = TEL_RE.match(t)
        m_meta = META_RE.search(t)
        if ADDR_RE.match(t):
            address = t
            if "Koror" in t:
                city = "Koror"
            m_zip = ZIP_RE.search(t)
            if m_zip:
                zipc = m_zip.group(1)
        elif m_tel:
            phone = m_tel.group("phone").strip()
            fax = m_tel.group("fax").strip()
            website = (m_tel.group("website") or "").strip()
        elif m_meta:
            reg_date = m_meta.group("charter").strip()
    rows.append({
        "Name": name,
        "Address_1": address,
        "City": city,
        "Zip": zipc,
        "Phone": phone,
        "Fax": fax,
        "Website": website,
        "RegulationDate": reg_date,
        "Cntry": "PW",
        "RegulationType": "Regulated",
        "ListCode": 1,
        "ListName": regdict[1]["ListName"],
        "ListLanguage": "EN",
        "ListLabel": 1,          # bank-only list
        "RegCtry": "PW",
        "RegCode": "PFIC",
        "ListProcessDate": process_date,
    })


el = active_h3
while True:
    el = el.find_next()
    if el is None or (el.name == "h3" and el is not active_h3):
        break
    if el.name == "h5":
        flush(bank_name, block)
        bank_name = el.get_text(" ", strip=True)
        block = []
    elif el.name == "p":
        txt = el.get_text(" ", strip=True)
        if txt:
            block.append(txt)
flush(bank_name, block)

df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]),
)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print(df[["Name", "Address_1", "Phone", "Fax", "Website", "RegulationDate"]].to_string(index=False))
print("Columns:", len(df.columns))
print("Output:", outfile)
