# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# VU RBV  -  Reserve Bank of Vanuatu
# Source: https://www.rbv.gov.vu/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions
# Jira:   DECD-6326  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# Plain requests (verify=False, desktop UA) returns 200 for every page on
# this site - no Cloudflare/WAF challenge, no DrissionPage needed.
#
# Site is a Joomla CMS. Each ListNr's URL is a "list" article that either:
#   (a) lists entities directly in an HTML <table> (id=75, id=423, id=427,
#       and the "International Banks" section of id=74), or
#   (b) lists sub-category links which must themselves be opened to reach
#       the entities (id=74's "Domestic Banks" section -> 3 sub-category
#       pages; id=76 Insurance -> 8 category pages).
# Every entity name is itself a hyperlink to a small Joomla "contact" article
# with free-text (non-tabular) Address/Telephone/Facsimile/Email/Website
# fields, per the Jira comment "click on each entity's hyperlink for
# details". These detail pages are NOT template-consistent (labels appear
# with ':', '-', '–' or on a separate line from their value, and some
# use different job-title labels e.g. "Country Head", "Resident Director"),
# so we parse them with a small line-based label/value state machine
# (see parse_detail_page) rather than fixed CSS selectors.
#
# Lists (from the Jira description, DECD-6326):
#   ListNr 1  Deposit Taking Institutions          id=74   (banks)
#   ListNr 2  Other Financial Institutions          id=75   (mixed)
#   ListNr 3  Insurance                             id=76   (8 sub-categories)
#   ListNr 5  Credit Unions                         id=423  (NEW)
#   ListNr 6  Payment Service Providers             id=427  (NEW)
#   (ListNr 4 does not exist in the Jira description - not our gap.)
# ------------------------------------------------------------------
import os
import re
import time
import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

regulatorName = 'VU RBV'
print(f"Running {regulatorName} Web Scraping Tool v.1.0")

# ------ workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

BASE = "https://www.rbv.gov.vu"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
}

session = requests.Session()
session.headers.update(HEADERS)
session.verify = False


def fetch_body(url, retries=3):
    """GET a page and return the Joomla article body <div>."""
    last_exc = None
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=40)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            body = soup.find("div", class_="com-content-article__body") or soup.find("div", class_="item-page")
            if body is not None:
                return body
            last_exc = RuntimeError("article body not found in %s" % url)
        except Exception as e:
            last_exc = e
        time.sleep(2)
    print("WARN: failed to fetch", url, "->", last_exc)
    return None


def get_links(body):
    """All <a href> entries inside a Joomla article body, absolute URL + text."""
    out = []
    if body is None:
        return out
    for a in body.find_all("a", href=True):
        name = a.get_text(" ", strip=True)
        href = a["href"]
        if not name:
            continue
        if href.startswith("http"):
            url = href
        else:
            url = BASE + href
        out.append((name, url))
    return out


# ---- regdict parsed from the Jira description (DECD-6326) -----------------
regdict = {
    1: {"ListName": "Deposit Taking Institutions",
        "URL": (BASE + "/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions"
                "?view=article&id=74:deposit-taking-institutions&catid=2"),
        "Comments": "Extract all entities under this list, click on each entity's hyperlink for details",
        "ListLabel": 1},
    2: {"ListName": "Other Financial Institutions",
        "URL": (BASE + "/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions"
                "?view=article&id=75:other-financial-institutions&catid=2"),
        "Comments": "Extract all entities under this list, click on each entity's hyperlink for details",
        "ListLabel": 4},
    3: {"ListName": "Insurance",
        "URL": (BASE + "/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions"
                "?view=article&id=76:insurance-companies-and-intermediaries&catid=2"),
        "Comments": "Open each category and extract all entities under each link, click on each entity's hyperlink for details",
        "ListLabel": 2},
    5: {"ListName": "Credit Unions",
        "URL": (BASE + "/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions"
                "?view=article&id=423:credit-unions&catid=2"),
        "Comments": "NEW LIST! Extract all entities under this list, click on each entity's hyperlink for details",
        "ListLabel": 4},
    6: {"ListName": "Payment Service Providers",
        "URL": (BASE + "/index.php/en/financial-stability/authorised-banks-supervised-financial-institutions"
                "?view=article&id=427:payment-service-providers&catid=2:uncategorised"),
        "Comments": "NEW LIST! Extract all entities under this list, click on each entity's hyperlink for details",
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


# ---- detail-page (free-text) parser ----------------------------------------
# These Joomla "contact" articles are hand-typed free text, not a consistent
# template: labels appear with ':', '-', '–' or on their own line from
# the value, and job-title labels vary a lot ("Country Head", "Resident
# Director", "Managing Director", "Board Chairman", ...). Rather than an
# exhaustive label list we classify each candidate label by keyword, and
# anything we don't recognise as address/phone/fax/email/website falls
# through untouched to the address bucket (safe default).
NA_VALUES = {'n/a', 'na', 'none', 'nil', '-', 'not applicable', ''}
IGNORE_KEYWORDS = ('director', 'manager', 'chairman', 'chair', 'ceo', 'chief executive',
                   'contact', 'company', 'name', 'president', 'proprietor', 'owner',
                   'underwriter', 'representative', 'agent', 'head', 'person', 'officer', 'oic')

LABEL_LINE_RE = re.compile(r'^(?P<label>[A-Za-z][A-Za-z .]{0,40}?)\s*[:\-–]\s*(?P<val>.*)$')
PUNCT_ONLY_RE = re.compile(r'^[:\-–,.\s]+$')
LEADING_PUNCT_RE = re.compile(r'^[:\-–]+\s*')
BARE_SENTENCE_IGNORE_RE = re.compile(r'^contact\s*person\s*is\b', re.I)
EMAIL_RE = re.compile(r'[\w.+\'-]+@[\w-]+\.[\w.-]+')
WEBSITE_RE = re.compile(r'(https?://[^\s,;]+|www\.[^\s,;]+)', re.I)
CITY_PORTVILA_RE = re.compile(r'^port\s*vila[,.]?$', re.I)


def classify_label(cand):
    """Map a candidate label word/phrase to a schema field, 'ignore'
    (a job title / contact-person / company-name-echo label whose value we
    don't keep), or None if it's not a label at all (i.e. plain text)."""
    c = cand.strip().lower()
    if not c:
        return None
    if 'website' in c or 'web site' in c or c in ('web', 'url'):
        return 'website'
    if 'email' in c or 'e-mail' in c or 'e mail' in c:
        return 'email'
    if 'facsimile' in c or 'fax' in c:
        return 'fax'
    if 'telephone' in c or 'phone' in c or c == 'tel' or 'mobile' in c:
        return 'phone'
    if 'address' in c:
        return 'address'
    if any(k in c for k in IGNORE_KEYWORDS):
        return 'ignore'
    return None


def is_name_echo(line, entity_name):
    a = re.sub(r'[^a-z0-9]', '', line.lower())
    b = re.sub(r'[^a-z0-9]', '', entity_name.lower())
    return a == b or a == (b + 'contact')


def parse_detail_page(url, entity_name):
    """Parse a Joomla 'contact' article's free-text body into
    address/phone/fax/email/website using a line-based label state machine.
    See header comment for why fixed CSS selectors don't work here."""
    body = fetch_body(url)
    result = {"Address_1": "", "City": "", "Phone": "", "Fax": "", "Email": "", "Website": ""}
    if body is None:
        return result

    raw_text = body.get_text(" ", strip=True)
    text = body.get_text("\n")
    lines = [l.strip() for l in text.split("\n")]
    lines = [LEADING_PUNCT_RE.sub('', l).strip() for l in lines]
    lines = [l for l in lines if l and not is_name_echo(l, entity_name)]

    fields = {'address': [], 'phone': [], 'fax': [], 'email': [], 'website': []}
    pending = None
    for line in lines:
        if PUNCT_ONLY_RE.match(line):
            continue
        if BARE_SENTENCE_IGNORE_RE.match(line):
            continue  # e.g. "Contact person is Jane Doe" - no clean label:value split
        label_norm, val = None, None
        m = LABEL_LINE_RE.match(line)
        if m:
            cand = m.group('label')
            cls = classify_label(cand)
            if cls is not None:
                label_norm, val = cls, m.group('val').strip()
        if label_norm is None:
            bare_cls = classify_label(line.rstrip(':').strip())
            if bare_cls is not None:
                label_norm, val = bare_cls, ''
        if label_norm is not None:
            if label_norm == 'ignore':
                pending = None if val else '__ignore__'
            elif label_norm == 'address':
                if val:
                    fields['address'].append(val)
                pending = None
            else:
                if val and val.lower() not in NA_VALUES:
                    fields[label_norm].append(val)
                    pending = None
                elif val:
                    pending = None  # explicit N/A - nothing to capture
                else:
                    pending = label_norm
            continue
        # plain (non-label) line
        if pending is not None:
            if pending != '__ignore__' and line.lower() not in NA_VALUES:
                fields[pending].append(line.rstrip(':').strip())
            # a value line ending in ':' is itself introducing a further
            # sub-value (e.g. "Mrs Lilon Obed :" before the email on its own
            # line) - keep waiting instead of handing control back to 'address'
            if not line.rstrip().endswith(':'):
                pending = None
        else:
            fields['address'].append(line)

    # Validate + fall back to a whole-page regex scan for email/website -
    # a few pages have broken inline markup (stray link text like "to")
    # that fools the line parser into capturing a non-email/url value.
    email_val = "; ".join(dict.fromkeys(fields['email']))
    if '@' not in email_val:
        m = EMAIL_RE.search(raw_text)
        email_val = m.group(0) if m else ""
    website_val = "; ".join(dict.fromkeys(fields['website']))
    if website_val and '.' not in website_val:
        website_val = ""
    if not website_val:
        m = WEBSITE_RE.search(raw_text)
        if m:
            website_val = m.group(0)

    # Pull a "Port Vila" line out of the address into City
    addr_lines = fields['address']
    city = ""
    kept = []
    for l in addr_lines:
        if not city and CITY_PORTVILA_RE.match(l):
            city = "Port Vila"
            continue
        kept.append(l)
    address = ", ".join(kept)
    address = address.replace('|', ', ')
    address = re.sub(r'\s+', ' ', address).strip(' ,')
    address = re.sub(r'^\(\s*', '', address)
    address = re.sub(r'\s*\)\s*$', '', address)
    address = re.sub(r',\s*\)$', '', address)
    address = re.sub(r'(,\s*){2,}', ', ', address)  # collapse doubled commas
    address = re.sub(r'\s*,\s*', ', ', address).strip(' ,')

    result["Address_1"] = address
    result["City"] = city
    result["Phone"] = "; ".join(dict.fromkeys(fields['phone']))
    result["Fax"] = "; ".join(dict.fromkeys(fields['fax']))
    result["Email"] = email_val
    result["Website"] = website_val
    return result


# Cntry follows the project convention of the regulator's own jurisdiction
# for every row (see PW PFIC / UG IRAUG READMEs) even though a handful of
# "External Insurance"/insurance-broker entities are physically headquartered
# in Australia or New Zealand per their Address_1 (RBV still authorises them
# to do business in Vanuatu) - documented in the README rather than varied here.
def guess_cntry(address):
    return "VU"


# ---- scrape -----------------------------------------------------------------
rows = []


def add_entity(name, url, listnr, license_type):
    detail = parse_detail_page(url, name)
    rows.append({
        "Name": name,
        "License_Type": license_type,
        "Address_1": detail["Address_1"],
        "City": detail["City"],
        "Phone": detail["Phone"],
        "Fax": detail["Fax"],
        "Email": detail["Email"],
        "Website": detail["Website"],
        "Cntry": guess_cntry(detail["Address_1"]),
        "RegulationType": "Regulated",
        "ListCode": listnr,
        "ListName": regdict[listnr]["ListName"],
        "ListLanguage": "EN",
        "ListLabel": regdict[listnr]["ListLabel"],
        "RegCtry": "VU",
        "RegCode": "RBV",
        "ListProcessDate": processdate,
    })


print("\n--- ListNr 1: Deposit Taking Institutions ---")
body74 = fetch_body(regdict[1]["URL"])
# The page has two <strong> section headers: "Domestic Banks" and
# "International Banks", each followed by its own <table>.
sections = body74.find_all(["p", "table"]) if body74 else []
current_section = ""
for el in sections:
    if el.name == "p":
        strong = el.find("strong")
        if strong:
            current_section = strong.get_text(strip=True)
        continue
    # el.name == "table" -> links are either category pages (Domestic Banks)
    # or direct entities (International Banks)
    for name, url in get_links(el):
        if current_section == "Domestic Banks":
            # sub-category page: fetch it and pull its own entity links
            sub_body = fetch_body(url)
            for sub_name, sub_url in get_links(sub_body):
                add_entity(sub_name, sub_url, 1, name)  # name = "Vanuatu Owned Banks" etc.
        else:
            add_entity(name, url, 1, current_section or "International Banks")

print("List 1 rows so far:", len(rows))

print("\n--- ListNr 2: Other Financial Institutions ---")
body75 = fetch_body(regdict[2]["URL"])
for name, url in get_links(body75):
    add_entity(name, url, 2, "Other Financial Institution")

print("\n--- ListNr 3: Insurance ---")
body76 = fetch_body(regdict[3]["URL"])
for cat_name, cat_url in get_links(body76):
    cat_body = fetch_body(cat_url)
    for name, url in get_links(cat_body):
        add_entity(name, url, 3, cat_name)

print("\n--- ListNr 5: Credit Unions ---")
body423 = fetch_body(regdict[5]["URL"])
for name, url in get_links(body423):
    add_entity(name, url, 5, "Credit Union")

print("\n--- ListNr 6: Payment Service Providers ---")
body427 = fetch_body(regdict[6]["URL"])
for name, url in get_links(body427):
    add_entity(name, url, 6, "Payment Service Provider")

# ---- build output -------------------------------------------------------
df = pd.DataFrame(rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != ""]

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
print("By ListCode:")
print(df["ListCode"].value_counts().sort_index())
print("Columns:", len(df.columns))
print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
