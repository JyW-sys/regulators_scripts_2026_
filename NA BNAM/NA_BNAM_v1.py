# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# NA BNAM  -  Bank of Namibia
# Jira:   DECD-6333  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# All 4 lists are plain server-rendered ASP.NET HTML pages - no
# Cloudflare/WAF challenge, plain `requests` (verify=False for the
# corporate TLS proxy) returns 200 directly. No DrissionPage needed.
#
# Lists (from the Jira description):
#   ListNr 1  "Authorised Banking Institutions"
#             https://www.bon.com.na/Bank/Banking-Supervision/The-Banking-System-in-Namibia.aspx
#             <h5>Authorised Banking Institutions:</h5> followed by a sibling
#             <ul class="bon-custom-list"> of <li><a href="...">Name</a></li>.
#             One entry (Trustco Bank Namibia Limited) is HTML-commented out
#             on the source page and is correctly excluded by parsing only
#             live <li> tags.
#   ListNr 2  "Authorised Dealers in Foreign Exchange"
#             https://www.bon.com.na/Bank/Exchange-Control.aspx
#             <h5 class="section-title">Authorised Dealers in Foreign Exchange</h5>
#             followed by a card-grid <div class="row row-cols-lg-3"> of
#             cards, each with an <h6> name and a "Visit Their Website" link.
#   ListNr 3  "Authorised Dealer in Foreign Exchange with Limited Authority (ADLA)"
#             https://www.bon.com.na/Bank/Exchange-Control/Authorised-Dealer-in-Foreign-Exchange-with-Limited.aspx
#             <h5 class="section-title">...(ADLA)</h5> followed by raw
#             text/<br> lines (no <ul>) between a "List of the licensed
#             ADLAs:" <strong> marker and the next <strong> marker. One
#             entry (Real Transfer Bureau de Change (Pty) Limited) is
#             HTML-commented out on the source page and is excluded.
#   ListNr 4  "Registered Credit Bureaus"  (NEW LIST per Jira)
#             same page as ListNr 1: <h5>Registered Credit Bureaus</h5>
#             followed by a sibling <ul class="bon-custom-list"> of plain
#             <li>Name</li> (no links/website for these two).
# ------------------------------------------------------------------
import os
import datetime
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup, NavigableString, Tag, Comment

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "NA BNAM"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

# ------ workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
}

URL_BANKING = "https://www.bon.com.na/Bank/Banking-Supervision/The-Banking-System-in-Namibia.aspx"
URL_FX = "https://www.bon.com.na/Bank/Exchange-Control.aspx"
URL_ADLA = "https://www.bon.com.na/Bank/Exchange-Control/Authorised-Dealer-in-Foreign-Exchange-with-Limited.aspx"

# regdict parsed from the Jira description (DECD-6333)
regdict = {
    1: {"ListName": "Authorised Banking Institutions",
        "URL": URL_BANKING,
        "Comments": "Extract all entities under the subtitle: Authorised Banking Institutions"},
    2: {"ListName": "Authorised Dealers in Foreign Exchange",
        "URL": URL_FX,
        "Comments": "Extract all entities under the subtitle Authorised Dealers in Foreign Exchange"},
    3: {"ListName": "Authorised Dealer in Foreign Exchange with Limited Authority (ADLA)",
        "URL": URL_ADLA,
        "Comments": "Extract all entities under the subtitle: List of the licensed ADLAs:"},
    4: {"ListName": "Registered Credit Bureaus",
        "URL": URL_BANKING,
        "Comments": "NEW LIST! Extract all entities under the subtitle: Registered Credit Bureaus"},
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


def fetch_html(url):
    r = requests.get(url, headers=HEADERS, verify=False, timeout=60)
    r.raise_for_status()
    return r.text


def extract_ul_after_h5(soup, heading_text):
    """Find an <h5> whose text matches heading_text, return list of
    (name, href) from the sibling <ul class="bon-custom-list"> that follows it."""
    h5 = None
    for h in soup.find_all("h5"):
        if heading_text in h.get_text():
            h5 = h
            break
    if h5 is None:
        return []
    ul = h5.find_next_sibling("ul")
    if ul is None:
        return []
    out = []
    for li in ul.find_all("li"):
        a = li.find("a")
        if a:
            out.append((a.get_text(strip=True), a.get("href", "")))
        else:
            out.append((li.get_text(strip=True), ""))
    return out


def extract_cards_after_h5(soup, heading_text, exclude_text=None):
    """Find <h5 class="section-title"> matching heading_text (and NOT
    containing exclude_text, to disambiguate from a similarly-named
    heading on the same page), return list of (name, website) from the
    following card-grid <div> of <h6> name + "Visit Their Website" link."""
    h5 = None
    for h in soup.find_all("h5", class_="section-title"):
        txt = h.get_text(strip=True)
        if heading_text in txt and (exclude_text is None or exclude_text not in txt):
            h5 = h
            break
    if h5 is None:
        return []
    cards_div = h5.find_next("div", class_="row-cols-lg-3")
    if cards_div is None:
        return []
    out = []
    for col in cards_div.find_all("div", class_="col"):
        h6 = col.find("h6")
        if not h6:
            continue
        a = col.find("a")
        out.append((h6.get_text(strip=True), a.get("href", "") if a else ""))
    return out


def extract_brlist_after_strong(soup, section_heading, start_marker, end_marker):
    """Find <h5 class="section-title"> containing section_heading, then
    within its parent 'section-wrapper' div, collect the plain text lines
    (separated by <br>) that sit between the <strong>start_marker</strong>
    and the next <strong>end_marker</strong> tag. HTML-commented-out lines
    (<!-- ... -->) are skipped automatically since Comment nodes are
    filtered out explicitly."""
    h5 = None
    for h in soup.find_all("h5", class_="section-title"):
        if section_heading in h.get_text():
            h5 = h
            break
    if h5 is None:
        return []
    wrapper = h5.find_parent("div", class_="section-wrapper") or h5.parent
    contents = list(wrapper.contents)
    start_idx = end_idx = None
    for i, node in enumerate(contents):
        if isinstance(node, Tag) and node.name == "strong":
            txt = node.get_text(strip=True)
            if start_marker in txt and start_idx is None:
                start_idx = i
            elif end_marker in txt and start_idx is not None and end_idx is None:
                end_idx = i
    if start_idx is None:
        return []
    if end_idx is None:
        end_idx = len(contents)
    names = []
    for node in contents[start_idx + 1:end_idx]:
        if isinstance(node, Comment):
            continue
        if isinstance(node, NavigableString):
            txt = str(node).strip()
            if txt:
                names.append(txt)
    return names


process_date = datetime.date.today().isoformat()
rows = []


# ListLabel per ListNr (1=bank, 2=insurance, 3=both, 4=other):
#   1 - Authorised Banking Institutions: commercial banks -> bank list (1)
#   2 - Authorised Dealers in Foreign Exchange: same commercial banks
#       licensed for FX dealing -> bank list (1)
#   3 - ADLA (Limited Authority): independent forex-exchange bureaus
#       (money changers), not licensed banks -> other (4)
#   4 - Registered Credit Bureaus: neither bank nor insurer -> other (4)
LIST_LABEL = {1: 1, 2: 1, 3: 4, 4: 4}


def add_row(name, website="", list_code=1, license_type=""):
    if not name:
        return
    rows.append({
        "Name": name,
        "Website": website,
        "License_Type": license_type,
        "Cntry": "NA",
        "RegulationType": "Regulated",
        "ListCode": list_code,
        "ListName": regdict[list_code]["ListName"],
        "ListLanguage": "EN",
        "ListLabel": LIST_LABEL[list_code],
        "RegCtry": "NA",
        "RegCode": "BNAM",
        "ListProcessDate": process_date,
    })


# ---- List 1 & 4: shared "Banking System in Namibia" page ------------------
html_banking = fetch_html(URL_BANKING)
soup_banking = BeautifulSoup(html_banking, "html.parser")

for name, href in extract_ul_after_h5(soup_banking, "Authorised Banking Institutions"):
    add_row(name, website=href, list_code=1, license_type="Authorised Banking Institution")

for name, href in extract_ul_after_h5(soup_banking, "Registered Credit Bureaus"):
    add_row(name, website=href, list_code=4, license_type="Registered Credit Bureau")

# ---- List 2: Exchange Control page -----------------------------------------
html_fx = fetch_html(URL_FX)
soup_fx = BeautifulSoup(html_fx, "html.parser")

for name, href in extract_cards_after_h5(soup_fx, "Authorised Dealers in Foreign Exchange",
                                         exclude_text="Limited Authority"):
    add_row(name, website=href, list_code=2, license_type="Authorised Dealer in Foreign Exchange")

# ---- List 3: ADLA page -----------------------------------------------------
html_adla = fetch_html(URL_ADLA)
soup_adla = BeautifulSoup(html_adla, "html.parser")

for name in extract_brlist_after_strong(
        soup_adla,
        section_heading="Authorised Dealer in Foreign Exchange with Limited Authority",
        start_marker="licensed ADLAs",
        end_marker="Licensing Requirements"):
    add_row(name, website="", list_code=3, license_type="Authorised Dealer in Foreign Exchange with Limited Authority (ADLA)")

# ---- assemble ---------------------------------------------------------------
df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

now = datetime.datetime.now()
filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode:")
print(df["ListCode"].value_counts().sort_index())
print("\nBy License_Type:")
print(df["License_Type"].value_counts())
print("Columns:", len(df.columns))
print("Saved {} rows to {}".format(len(df), outfile))
