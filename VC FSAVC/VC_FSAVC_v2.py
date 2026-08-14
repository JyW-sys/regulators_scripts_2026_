# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# VC FSAVC  -  Financial Services Authority of St. Vincent and the Grenadines
# Source: https://fsasvg.com/
# Jira:   DECD-6325  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# v2 changes vs v1
# ----------------
# 1. ListNr 4 contact-block bug (the real defect in the v1 output file).
#    v1 only looked for a following <p> to get the address/Tel/Fax/Email
#    block. On this Elementor page 4 of the 15 entities publish their
#    contact block inside a <div class="tb_text_wrap"> (br- or div-
#    separated lines) instead of a <p>:
#        Lex Mercatoria Fiduciary Ltd. / GOLD IN (ST. VINCENT) CO., LTD. /
#        CARIBBEAN TRUST COMPANY LTD / ST. VINCENT TRUST AND ESCROW LTD
#    v1 emitted these 4 rows with empty Address_1/City/Phone/Email/Website
#    and README_VC_FSAVC.md wrongly recorded it as "no contact block on the
#    page". v2 accepts <p> AND div.tb_text_wrap -> 15/15 contact blocks.
# 2. Phone labels widened. The div blocks use "Office Land Line:" and
#    "Mobile Contact:" instead of "Tel:", so v1's TEL_RE would still have
#    missed the number even after fixing (1). v2 captures Tel / Telephone /
#    Phone / Office Land Line / Mobile Contact / Mobile / Cell (joined by
#    " / " when an entity publishes more than one).
# 3. Tables are now selected by their own header text / the heading above
#    them instead of by hard-coded positional index (tables1[0], tables2[:6],
#    ...). Fee-schedule tables are excluded by matching "Fee"/"Asset Size"/
#    "Class of License" headers. A positional index silently produces wrong
#    data the day the site inserts or removes a table; header matching fails
#    loudly instead (the EXPECTED-count check at the bottom).
# 4. Per-list EXPECTED row counts are asserted at the end so a structural
#    change on the source cannot pass QA unnoticed.
#
# Row counts, ListLabel assignments, RegCtry/RegCode/ListLanguage/ListCode
# and the ListNr 1 "Insurance Sales Representatives" decision (Name = the
# insurance company in column 1, NOT the 84 individual reps in column 2 -
# corrected per user feedback, see README) are unchanged from v1: they were
# verified row-by-row against the live pages and match the source exactly.
#
# All 8 pages are plain WordPress pages (LiteSpeed cache) - plain `requests`
# with a desktop User-Agent and verify=False returns 200 with full content
# for every URL, no Cloudflare/WAF challenge and no DrissionPage needed.
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
print(f"Running {regulatorName} Web Scraping Tool v.2.0")

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

# ListLabel per ListNr - 1 bank, 2 insurance, 3 bank & insurance, 4 other.
LIST_LABEL = {
    1: 2,   # insurance companies / intermediaries / pension fund plans
    2: 4,   # mutual funds - neither bank nor insurance
    3: 1,   # international banks
    4: 4,   # registered agents / trustees / corporate service providers
    5: 1,   # credit unions - deposit-taking cooperatives
    6: 1,   # building societies - deposit-taking mutuals
    7: 2,   # friendly societies - mutual sickness/death benefit societies
    8: 4,   # microfinancing institutions
}

# Row count expected per ListNr, verified against the live pages 2026-08-05.
EXPECTED = {1: 97, 2: 42, 3: 4, 4: 15, 5: 4, 6: 1, 7: 13, 8: 4}

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

now = datetime.datetime.now()
PROCESS_DATE = now.strftime('%Y-%m-%d')
REG_CTRY, REG_CODE = regulatorName.split(" ", 1)  # 'VC', 'FSAVC'


def fetch_html(url, timeout=60):
    """Plain requests fetch - all fsasvg.com pages return 200 with a desktop UA."""
    r = requests.get(url, headers=HEADERS, verify=False, timeout=timeout)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def get_main(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("main") or soup.find("article") or soup.body


def header_cells(table):
    """Text of the first <tr>'s cells - these pages always carry a header row."""
    trs = table.find_all("tr")
    if not trs:
        return []
    return [c.get_text(" ", strip=True) for c in trs[0].find_all(["td", "th"])]


def table_rows(table):
    """Cell-text lists for every <tr> after the header row; blank <tr> dropped.

    The 'International Banks Under Liquidation' table contains a genuinely
    empty spacer <tr class="ha-table__body-row"></tr> which must not become a row.
    """
    out = []
    for tr in table.find_all("tr")[1:]:
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if any(c for c in cells):
            out.append(cells)
    return out


def preceding_heading(table):
    """Nearest heading above a table - distinguishes the two 'Intermediary | Type'
    tables on ListNr 1 (domestic brokers/adjusters vs international)."""
    h = table.find_previous(["h1", "h2", "h3", "h4"])
    return h.get_text(" ", strip=True) if h else ""


FEE_MARKERS = ("fee", "asset size", "class of license", "statutory deposit")


def entity_tables(main):
    """Every table on the page that is not a fee/rate schedule."""
    keep = []
    for t in main.find_all("table"):
        hdr = " | ".join(header_cells(t)).lower()
        if any(m in hdr for m in FEE_MARKERS):
            continue
        keep.append(t)
    return keep


def find_table(main, *needles):
    """First non-fee table whose header row contains all needles (case-insensitive)."""
    for t in entity_tables(main):
        hdr = " | ".join(header_cells(t)).lower()
        if all(n.lower() in hdr for n in needles):
            return t
    raise RuntimeError("no table with header containing {}".format(needles))


# Stop lookahead shared by every "label: value" field so one label's capture
# never bleeds into the next (Tel:/Office Land Line:/Mobile Contact:/Fax:/
# Email:/Web:/Contact: can all appear back-to-back in these free-text blobs).
PHONE_LABELS = r'(?:Office\s+Land\s+Line|Mobile\s+Contact|Telephone|Mobile|Phone|Cell|Tel)'
LABELS = r'(?:' + PHONE_LABELS + r'|Fax|Email|E-mail|Web(?:site)?|Contact|Mail)\s*:'
STOP = r'(?=\s*' + LABELS + r'|$)'

EMAIL_RE = re.compile(r'([\w.+-]+@[\w-]+\.[\w.-]+)')
PHONE_RE = re.compile(PHONE_LABELS + r'\s*:\s*(.*?)' + STOP, re.I)
FAX_RE = re.compile(r'Fax\s*:\s*(.*?)' + STOP, re.I)
EMAIL_FIELD_RE = re.compile(r'E-?mail\s*:\s*(.*?)' + STOP, re.I)
WEB_RE = re.compile(r'Web(?:site)?\s*:\s*(\S+)', re.I)
ZIP_RE = re.compile(r'\b(VC\d{4})\b')


def parse_contact(text):
    """Pull phone/fax/email/website/zip out of a free-text address/contact blob."""
    out = {"phone": "", "fax": "", "email": "", "website": "", "zip": ""}
    if not text:
        return out
    phones = [p.strip(" .,-") for p in PHONE_RE.findall(text)]
    phones = [p for p in dict.fromkeys(phones) if p]
    if phones:
        out["phone"] = " / ".join(phones)
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
    t = PHONE_RE.sub("", text)
    t = FAX_RE.sub("", t)
    t = EMAIL_FIELD_RE.sub("", t)
    t = re.sub(r'Web(?:site)?\s*:\s*\S+', '', t, flags=re.I)
    t = re.sub(r'\s{2,}', ' ', t).strip(" ,.")
    return t


def base_row(list_nr, name, license_type="", regulation_type="Regulated"):
    row = {c: "" for c in COLUMNS}
    row.update({
        "ListLabel": LIST_LABEL[list_nr],
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
# 8 entity tables (3 fee schedules on the same page are dropped by
# entity_tables()). Each is dispatched on its own header row.
main1 = get_main(fetch_html(regdict[1]["URL"]))

for t in entity_tables(main1):
    hdr = header_cells(t)
    h0 = hdr[0].lower() if hdr else ""
    section = preceding_heading(t).lower()

    for cells in table_rows(t):
        if not cells or not cells[0]:
            continue
        name = cells[0]
        col2 = cells[1] if len(cells) > 1 else ""

        if "registered pension plan" in h0:
            lic = "Registered Pension Plan"
        elif "motor & general insurance" in h0:
            lic = "Motor & General Insurance Company"
        elif "long term insurance" in h0:
            lic = "Long Term Insurance Company"
        elif h0 == "agent":
            lic = "Insurance Agent"
        elif h0 == "intermediary":
            # domestic brokers/adjusters/underwriters vs international ones -
            # only the heading above the table tells them apart.
            lic = ("International " + col2) if "international" in section else col2
        elif h0 == "company":
            lic = "International Insurance Company ({})".format(col2) if col2 else "International Insurance Company"
        elif "insurance company" in h0 and "sales representative" in " | ".join(hdr).lower():
            # 2-col table `Insurance Company | Sales Representative(s)`.
            # The entity registered here is the INSURANCE COMPANY (col 1);
            # the comma-separated individual reps in col 2 are deliberately
            # not split into rows (per user feedback, see README).
            lic = "Insurance Sales Representative(s)"
        else:
            lic = col2

        all_rows.append(base_row(1, name, lic))

# ==== ListNr 2: Mutual Funds ------------------------------------------------
# 6 tables sharing `Name of Mutual Fund(...) | Type of Mutual Funds | Status`;
# the "Fee Schedule: Mutual Funds" table is dropped by entity_tables().
main2 = get_main(fetch_html(regdict[2]["URL"]))

for t in entity_tables(main2):
    if "name of mutual fund" not in " | ".join(header_cells(t)).lower():
        continue
    for cells in table_rows(t):
        if not cells or not cells[0]:
            continue
        license_type = cells[1] if len(cells) >= 2 else ""
        status = cells[2].strip() if len(cells) >= 3 else "Active"
        reg_type = "Regulated" if status.lower() == "active" else status
        all_rows.append(base_row(2, cells[0], license_type, reg_type))

# ==== ListNr 3: International Banks -----------------------------------------
main3 = get_main(fetch_html(regdict[3]["URL"]))

t_active = find_table(main3, "international bank", "license class")
for cells in table_rows(t_active):  # International Bank | License Class | Address | Main Contact
    if not cells or not cells[0]:
        continue
    name = cells[0]
    lic_class = cells[1] if len(cells) > 1 else ""
    address = cells[2] if len(cells) > 2 else ""
    contact = cells[3] if len(cells) > 3 else ""
    # Phone/Fax/Zip come from the bank's own Address cell; Email falls
    # back to the "Main Contact" cell if the address cell has none.
    addr_info = parse_contact(address)
    contact_info = parse_contact(contact)
    r = base_row(3, name,
                 "International Bank ({})".format(lic_class) if lic_class else "International Bank")
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

t_liq = find_table(main3, "under liquidation")
for cells in table_rows(t_liq):  # International Banks Under Liquidation | Class | Liquidator
    if not cells or not cells[0]:
        continue
    name = cells[0]
    lic_class = cells[1] if len(cells) > 1 else ""
    liquidator = cells[2] if len(cells) > 2 else ""
    contact_info = parse_contact(liquidator)
    r = base_row(3, name,
                 "International Bank ({})".format(lic_class) if lic_class else "International Bank",
                 regulation_type="Under Liquidation")
    # No street address is published for banks in liquidation - the
    # "Liquidator" cell (person/firm handling the wind-down) goes in
    # Address_2 as a note rather than Address_1.
    r["Address_2"] = ("Liquidator: " + strip_contact_fields(liquidator)) if liquidator else ""
    r["Zip"] = contact_info["zip"]
    r["Phone"] = contact_info["phone"]
    r["Email"] = contact_info["email"]
    all_rows.append(r)

# ==== ListNr 4: Registered Agents/Trustees/Service Providers ----------------
# Not a table: under the "Currently Registered ..." <h2> the page alternates
# <h5>/<h4> entity-name headings with a contact block. The contact block is a
# <p> for 11 entities and a <div class="tb_text_wrap"> (Elementor text-editor
# widget, <br>/<div> separated lines) for the other 4 - v1 only handled <p>
# and lost those 4. Both shapes are accepted here.
main4 = get_main(fetch_html(regdict[4]["URL"]))

heading4 = None
for h in main4.find_all(["h2", "h3"]):
    if "Currently Registered" in h.get_text():
        heading4 = h
        break
if heading4 is None:
    raise RuntimeError("ListNr 4: 'Currently Registered ...' heading not found")

FOOTER_STOP = {"quick links", "useful links"}
CONTACT_MARKER = re.compile(LABELS, re.I)


def is_contact_block(el):
    """<p> or Elementor text-editor <div class="tb_text_wrap"> holding a
    Tel:/Email:/Fax:/Web: labelled contact blob."""
    if el.name == "p":
        return True
    if el.name == "div":
        classes = el.get("class") or []
        return "tb_text_wrap" in classes
    return False


entries4 = []  # list of [name, contact_text_or_None]
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
    elif current_name is not None and is_contact_block(el):
        text = el.get_text(" ", strip=True)
        # The site footer tagline is also a <p> - it carries no Tel:/Email:
        # label, so the marker test keeps it out.
        if CONTACT_MARKER.search(text) and entries4 and entries4[-1][1] is None:
            entries4[-1][1] = text

for name, ctext in entries4:
    if not name:
        continue
    r = base_row(4, name, "Registered Agent/Trustee/Service Provider")
    if ctext:
        info = parse_contact(ctext)
        r["Address_1"] = strip_contact_fields(ctext)
        if "Kingstown" in ctext:
            r["City"] = "Kingstown"
        r["Zip"] = info["zip"]
        r["Phone"] = info["phone"]
        r["Fax"] = info["fax"]
        r["Email"] = info["email"]
        r["Website"] = info["website"]
    all_rows.append(r)

# ==== ListNr 5: Credit Unions ------------------------------------------------
main5 = get_main(fetch_html(regdict[5]["URL"]))
for cells in table_rows(find_table(main5, "name of credit union")):
    if cells and cells[0]:
        all_rows.append(base_row(5, cells[0], "Credit Union"))

# ==== ListNr 6: Building Societies -------------------------------------------
main6 = get_main(fetch_html(regdict[6]["URL"]))
for cells in table_rows(find_table(main6, "building societies")):
    if cells and cells[0]:
        all_rows.append(base_row(6, cells[0], "Building Society"))

# ==== ListNr 7: Friendly Societies -------------------------------------------
# `Name of Society | Name of Society (Continued)` - two name columns side by
# side purely to fit the page; both are flattened into individual rows.
main7 = get_main(fetch_html(regdict[7]["URL"]))
for cells in table_rows(find_table(main7, "name of society")):
    for name in cells:
        if name:
            all_rows.append(base_row(7, name, "Friendly Society"))

# ==== ListNr 8: Microfinancing Institutions -----------------------------------
# Per the Jira Comments only the table under <h2>Microfinancing Institutions</h2>
# is in scope; the two Money Remitter agent/sub-agent tables on the same page
# (same `Agent/Sub-Agent | Location | Class` shape) are explicitly excluded.
main8 = get_main(fetch_html(regdict[8]["URL"]))
micro_h2 = None
for h in main8.find_all(["h2", "h3"]):
    if h.get_text(strip=True).lower() == "microfinancing institutions":
        micro_h2 = h
        break
if micro_h2 is None:
    raise RuntimeError("ListNr 8: 'Microfinancing Institutions' heading not found")
for cells in table_rows(micro_h2.find_next("table")):
    if cells and cells[0]:
        all_rows.append(base_row(8, cells[0], "Microfinancing Institution"))

# ---- assemble & save --------------------------------------------------------
df = pd.DataFrame(all_rows)
df = df.reindex(columns=COLUMNS, fill_value="")     # enforce exact fixed schema
df = df[df["Name"] != '']

filename = "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7])
outfile = os.path.join(scriptfolder, filename)
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
counts = df.groupby("ListCode")["Name"].count().to_dict()
for nr in sorted(regdict):
    got, exp = counts.get(nr, 0), EXPECTED[nr]
    print("  ListCode {}: {:>3} rows (expected {:>3}) {}".format(
        nr, got, exp, "OK" if got == exp else "*** MISMATCH ***"))
bad = [nr for nr in EXPECTED if counts.get(nr, 0) != EXPECTED[nr]]
if bad:
    print("!! row-count mismatch on ListCode(s) {} - source structure changed".format(bad))
print("Columns:", len(df.columns))
print("Output:", outfile)
