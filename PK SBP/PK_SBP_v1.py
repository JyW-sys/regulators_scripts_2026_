# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# PK SBP  -  State Bank of Pakistan
# Source: https://www.sbp.org.pk/sbp-regulated-institutions/*
# Jira:   DECD-6336  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Each of the 6 "sbp-regulated-institutions" pages is a static-looking
# page whose actual entity content is loaded client-side via one or more
# <div class="ajax-slot" data-url="https://www.sbp.org.pk/t_inner/oo-tabs/
# sbp-regulated-institutions/<slug>?i=N"> placeholders (no Cloudflare/WAF -
# plain `requests` gets HTTP 200 on both the shell page and the ajax
# fragments). The "Commercial Banks" page has 6 such ajax slots (one per
# sub-category shown in its "On this Page" table of contents: Digital
# Banks, Public Sector Commercial Banks, Specialized Banks, Local Private
# Banks, Islamic Banks, Foreign Banks); every other page has exactly 1
# ajax slot covering the whole list.
#
# Each ajax fragment renders one category as a vertical Bootstrap
# nav-tabs widget: one <button class="nav-link"> per entity (its text is
# the entity name) paired with a <div class="tab-pane" id="..."> holding:
#   <h5>President/CEO|CEO|Managing Director|...</h5>
#     <p>Contact person name</p>
#     <p>Head-office address ... <br> Tel : ... <br> Fax: ...</p>
#   <h5>Complaint Cell</h5>
#     <p>role / complaint address ... Tel/UAN/Fax ...</p>
#     <p><a href="https://entity-website">...</a> <a href="mailto:...">Email</a></p>
#   <h5>License / Permissions / Authorizations</h5>
#     <ul><li>License type</li> ...</ul>
# A duplicate mobile-only <div class="accordion"> block repeats the exact
# same per-entity content for responsive layout - only the desktop
# <div class="tab-pane"> blocks are parsed, to avoid double-counting.
#
# Per the Jira Comments field, ListNr 1 ("Commercial Banks") explicitly
# says "Extract all entities from each sub category of this page" - so
# all 6 Commercial-Banks ajax slots are fetched and merged into one list.
# The other 5 lists ("NEW LIST!") are each a single page / single ajax
# slot, extracted whole.
#
# Lists (from the Jira description, DECD-6336):
#   ListNr 1  Commercial Banks                  -> 6 sub-category ajax slots
#   ListNr 2  Microfinance Banks                -> 1 ajax slot
#   ListNr 3  Exchange Companies                -> 1 ajax slot
#   ListNr 4  Development Finance Institutions  -> 1 ajax slot
#   ListNr 5  Payment System Operators          -> 1 ajax slot
#   ListNr 6  Credit Bureaus                    -> 1 ajax slot
# ------------------------------------------------------------------
import os
import re
import datetime
import requests
import urllib3
import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import NavigableString

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = "PK SBP"
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

# ------ workspace path -------------------------------------------------
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
}
BASE = "https://www.sbp.org.pk"

session = requests.Session()
session.headers.update(HEADERS)
session.verify = False

# regdict parsed from the Jira description (DECD-6336)
regdict = {
    1: {"ListName": "Commercial Banks",
        "URL": f"{BASE}/sbp-regulated-institutions/commercial-banks",
        "Comments": "Extract all entities from each sub category of this page.",
        "ListLabel": 1},   # bank list
    2: {"ListName": "Microfinance Banks",
        "URL": f"{BASE}/sbp-regulated-institutions/microfinance-banks",
        "Comments": "NEW LIST! Extract all entities from this page.",
        "ListLabel": 1},   # bank list (microfinance banking license)
    3: {"ListName": "Exchange Companies",
        "URL": f"{BASE}/sbp-regulated-institutions/exchange-companies",
        "Comments": "NEW LIST! Extract all entities from this page.",
        "ListLabel": 4},   # currency exchange / money-changer - not bank/insurance
    4: {"ListName": "Development Finance Institutions",
        "URL": f"{BASE}/sbp-regulated-institutions/development-finance-institutions",
        "Comments": "NEW LIST! Extract all entities from this page.",
        "ListLabel": 4},   # non-bank financial institution (judgment call, see README)
    5: {"ListName": "Payment System Operators",
        "URL": f"{BASE}/sbp-regulated-institutions/payment-system-operators",
        "Comments": "NEW LIST! Extract all entities from this page.",
        "ListLabel": 4},   # payments infrastructure - not bank/insurance
    6: {"ListName": "Credit Bureaus",
        "URL": f"{BASE}/sbp-regulated-institutions/credit-bureaus",
        "Comments": "NEW LIST! Extract all entities from this page.",
        "ListLabel": 4},   # credit-reporting company - not bank/insurance
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

PK_CITIES = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi', 'Peshawar', 'Quetta',
             'Faisalabad', 'Multan', 'Hyderabad', 'Sialkot', 'Gujranwala', 'Sukkur',
             'Abbottabad', 'Bahawalpur', 'Sargodha', 'Gujrat', 'Sahiwal', 'Mardan',
             'Sadiqabad', 'Mirpur']

# ---- section / field parsing helpers --------------------------------------
HEAD_KEYWORDS = ['president', 'ceo', 'chief executive', 'managing director',
                 'country head', 'gm', 'chairman']
LICENSE_KEYWORDS = ['license', 'permission', 'authorization']
COMPLAINT_KEYWORDS = ['complaint']

PHONE_RE = re.compile(r'^(?:Tel(?:ephone)?|Phone|Mobile|UAN|PABX|Landline)\s*:\s*(.*)$', re.I)
FAX_RE = re.compile(r'^Fax\s*:\s*(.*)$', re.I)
EMAIL_TEXT_RE = re.compile(r'^Emails?\s*:\s*(.*)$', re.I)
EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
WEBSITE_TEXT_RE = re.compile(r'^(https?://\S+|www\.\S+)$', re.I)
SKIP_RE = re.compile(r'^(Contact Center|Helpline|Toll Free|UAN Helpline|Ext)\b', re.I)
NAME_HONORIFIC_RE = re.compile(
    r'^(Mr|Mrs|Ms|Dr|Syed|Malik|Sheikh|Shaikh|Capt|Maj|Col|Lt|Prof|Mian|Chaudhry|Ch)\.?\s', re.I)


def classify_heading(text):
    t = text.lower()
    if any(k in t for k in LICENSE_KEYWORDS):
        return 'license'
    if any(k in t for k in COMPLAINT_KEYWORDS):
        return 'complaint'
    if any(k in t for k in HEAD_KEYWORDS):
        return 'head'
    return None


def looks_like_person_name(line):
    """Heuristic: is this line the contact person's name (to be skipped),
    as opposed to the head-office address (to be kept)?"""
    if NAME_HONORIFIC_RE.match(line):
        return True
    if not re.search(r'\d', line) and len(line.split()) <= 4 and ',' not in line:
        return True
    return False


def extract_city(address):
    best_idx, best_city = None, ''
    for c in PK_CITIES:
        m = re.search(r'\b' + re.escape(c) + r'\b', address, re.I)
        if m and (best_idx is None or m.start() < best_idx):
            best_idx, best_city = m.start(), c
    return best_city


def parse_tabpane(tp):
    """Parse one entity's <div class="tab-pane"> block into head-office
    address/phone/fax (from the President/CEO section), website/email
    (from the Complaint Cell section's links), and license types."""
    data = {'head_address': [], 'phone': '', 'fax': '', 'website': [], 'email': [], 'license': []}
    section = None
    head_first_p_seen = False
    for child in tp.find_all(['h5', 'p', 'ul'], recursive=False):
        if child.name == 'h5':
            sec = classify_heading(child.get_text(' ', strip=True))
            if sec:
                section = sec
                if sec == 'head':
                    head_first_p_seen = False
            continue
        if child.name == 'ul':
            if section == 'license':
                items = [li.get_text(' ', strip=True) for li in child.find_all('li')]
                data['license'].extend([i for i in items if i])
            continue
        # child.name == 'p' -----------------------------------------------
        # a heading is sometimes embedded as leading <strong>/<b> text
        # inside a <p> instead of being its own <h5> tag.
        contents = list(child.contents)
        idx = 0
        heading_parts = []
        while idx < len(contents):
            c = contents[idx]
            if isinstance(c, NavigableString):
                if not str(c).strip():
                    idx += 1
                    continue
                break
            if getattr(c, 'name', None) in ('strong', 'b'):
                heading_parts.append(c.get_text(' ', strip=True))
                idx += 1
                continue
            break
        heading_text = ' '.join(x for x in heading_parts if x).strip()
        if heading_text and classify_heading(heading_text):
            section = classify_heading(heading_text)
            if section == 'head':
                head_first_p_seen = False
            for c in contents[:idx]:
                c.extract()
        # links (website / mailto) - extracted regardless of section
        for a in child.find_all('a'):
            href = (a.get('href', '') or '').strip()
            if href.lower().startswith('mailto:'):
                e = href[7:].strip()
                if e and e not in data['email']:
                    data['email'].append(e)
            elif href.startswith('http'):
                if href not in data['website']:
                    data['website'].append(href)
            a.extract()
        for br in child.find_all('br'):
            br.replace_with('\n')
        text = child.get_text()
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines:
            if section == 'head' and not head_first_p_seen:
                head_first_p_seen = True
                if looks_like_person_name(line):
                    continue  # contact person's name - not part of sqldict schema
            if SKIP_RE.match(line):
                continue
            m_fax = FAX_RE.match(line)
            m_phone = PHONE_RE.match(line)
            m_email = EMAIL_TEXT_RE.match(line)
            m_web = WEBSITE_TEXT_RE.match(line)
            if m_fax:
                if section == 'head' and not data['fax']:
                    data['fax'] = m_fax.group(1).strip()
            elif m_phone:
                if section == 'head' and not data['phone']:
                    data['phone'] = m_phone.group(1).strip()
            elif m_email:
                for e in EMAIL_PATTERN.findall(m_email.group(1)):
                    if e not in data['email']:
                        data['email'].append(e)
            elif m_web:
                if line not in data['website']:
                    data['website'].append(line)
            else:
                if section == 'head':
                    data['head_address'].append(line)
    return data


def fetch(url):
    r = session.get(url, timeout=60)
    r.raise_for_status()
    return r.text


def parse_ajax_fragment(html):
    """Parse one ajax-slot fragment (one category) into a list of entity dicts."""
    soup = BeautifulSoup(html, "html.parser")
    nav = soup.find(id='nav--tab')
    buttons = nav.find_all('button') if nav else soup.select('button.nav-link')
    button_map = {}
    for b in buttons:
        target = b.get('data-bs-target', '').lstrip('#')
        button_map[target] = b.get_text(' ', strip=True)
    rows = []
    for tp in soup.find_all('div', class_='tab-pane'):
        name = button_map.get(tp.get('id'), '')
        if not name:
            continue
        d = parse_tabpane(tp)
        d['Name'] = name
        rows.append(d)
    return rows


def get_ajax_urls(page_html):
    urls = re.findall(r'data-url="([^"]+)"', page_html)
    # dedupe while preserving order
    seen = []
    for u in urls:
        if u not in seen:
            seen.append(u)
    return seen


# ---- scrape -----------------------------------------------------------
process_date = datetime.date.today().isoformat()
rows = []

for listnr, meta in regdict.items():
    print(f"\n--- ListNr {listnr}: {meta['ListName']} ---")
    page_html = fetch(meta["URL"])
    ajax_urls = get_ajax_urls(page_html)
    if not ajax_urls:
        print(f"  WARNING: no ajax-slot found on {meta['URL']} - skipping")
        continue
    print(f"  {len(ajax_urls)} ajax slot(s)")
    list_entities = []
    for au in ajax_urls:
        frag_html = fetch(au)
        entities = parse_ajax_fragment(frag_html)
        list_entities.extend(entities)
    print(f"  {len(list_entities)} entities")

    for e in list_entities:
        address = ", ".join(e["head_address"])
        city = extract_city(address)
        rows.append({
            "Name": e["Name"],
            "License_Type": "; ".join(e["license"]),
            "Address_1": address,
            "City": city,
            "Cntry": "PK",
            "Phone": e["phone"],
            "Fax": e["fax"],
            "Website": e["website"][0] if e["website"] else "",
            "Email": e["email"][0] if e["email"] else "",
            "RegulationType": "Regulated",
            "RegCtry": "PK",
            "RegCode": "SBP",
            "ListCode": listnr,
            "ListName": meta["ListName"],
            "ListLabel": meta["ListLabel"],
            "ListLanguage": "EN",
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
print("By ListCode / ListName:")
print(df.groupby(["ListCode", "ListName"]).size())
print("Columns:", len(df.columns))
print("Output:", outfile)
