# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# PG BPNG  -  Bank of Papua New Guinea
# Source: https://www.bankpng.gov.pg/financial-stability/licensed-entities
# Jira:   DECD-6335  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The page is behind a Cloudflare "Just a moment..." challenge, so plain
# requests gets a 403. We use DrissionPage (real Chrome) to pass Cloudflare,
# then parse the rendered HTML with BeautifulSoup.
#
# Layout: a single <h5>-titled page. Section headings are <h5> tags:
#   - top-level sections "A) Commercial Banks", "B) ... ", ... "I) ..."
#   - two sections (H, I) have <h5> sub-headings "i. ...", "ii. ...", etc.
# Each section/sub-section is followed by one <p> whose text is a run-on
# numbered list "1. Name 2. Name 3. Name ...". There is no address/phone/
# email/website info on this page - just entity names grouped by license type.
#
# Lists (from the Jira description):
#   ListNr 1  "Licensed Entities in Papua New Guinea" -> every entity on the page
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

regulatorName = "PG BPNG"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

URL = "https://www.bankpng.gov.pg/financial-stability/licensed-entities"

# regdict parsed from the Jira description (DECD-6335)
regdict = {
    1: {"ListName": "Licensed Entities in Papua New Guinea",
        "URL": URL,
        "Comments": "Extract all entities in this page"},
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
    """Open Chrome via DrissionPage, pass Cloudflare, return rendered HTML."""
    opt = ChromiumOptions().auto_port()
    dp = ChromiumPage(opt)
    try:
        dp.get(url)
        waited = 0
        while waited < timeout:
            time.sleep(3); waited += 3
            if "Just a moment" not in dp.title and dp.s_ele("tag:h5"):
                break
        html = dp.html
    finally:
        dp.quit()
    return html


TOP_RE = re.compile(r'^([A-Z])\)\s*(.+)$')
SUB_RE = re.compile(r'^([ivx]+)\.\s*(.+)$')
ENTRY_RE = re.compile(r'(\d{1,3})\.\s+')


def split_entries(text):
    """Split a run-on '1. Name 2. Name ...' paragraph into a list of names."""
    matches = list(ENTRY_RE.finditer(text))
    names = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        name = text[start:end].strip().strip('.,;').strip()
        if name:
            names.append(name)
    return names


# ---- scrape ---------------------------------------------------------------
html = fetch_html(URL)
soup = BeautifulSoup(html, "html.parser")
main = soup.find("main") or soup.find("article") or soup.body
for tag in main(["script", "style", "nav", "header", "footer"]):
    tag.decompose()

process_date = datetime.date.today().isoformat()
rows = []
top_label = ""
sub_label = ""
for el in main.find_all(["h5", "p"]):
    text = el.get_text(" ", strip=True)
    if not text:
        continue
    if el.name == "h5":
        m_top = TOP_RE.match(text)
        m_sub = SUB_RE.match(text)
        if m_top:
            top_label = m_top.group(2).strip()
            sub_label = ""
        elif m_sub:
            sub_label = m_sub.group(2).strip()
        continue
    # el.name == "p"
    if not re.match(r'^\s*1\.\s', text):
        continue  # descriptive paragraph, not the numbered entity list
    license_type = sub_label or top_label
    for name in split_entries(text):
        rows.append({
            "Name": name,
            "License_Type": license_type,
            "Cntry": "PG",
            "RegulationType": "Regulated",
            "ListCode": 1,
            "ListName": regdict[1]["ListName"],
            "ListLanguage": "EN",
            "ListLabel": 4,           # mixed: banks, insurance, pension, FX, remittance, payments
            "RegCtry": "PG",
            "RegCode": "BPNG",
            "ListProcessDate": process_date,
        })

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
print("By License_Type:")
print(df["License_Type"].value_counts())
print("Columns:", len(df.columns))
print("Output:", outfile)
