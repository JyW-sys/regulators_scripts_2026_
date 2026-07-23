"""
Shared CONSOB parsing/output helpers for Tier 1.

Mirrors the proven Tier 0 parser (IT CONSOB_tier_0/consob_tier0.py): the company
list is server-rendered, each company is
    <div class="boxQuotata"><span class="boxQuotataTitle">A2A SPA</span> ... </div>
so once Radware is passed, the same parser turns page HTML into SQL-Ready rows.
Kept self-contained here so this folder runs without importing across the
space-named Tier 0 folder.
"""

import datetime
import re

from bs4 import BeautifulSoup

LIST7_URL = (
    "https://www.consob.it/web/consob-and-its-activities/"
    "listed-companies/list-old?startsWith={}"
)

# A non-blocked page still references perfdrive.com in a Radware script tag, so
# the bare string is NOT a block signal. A real block redirects to
# validate.perfdrive.com or serves the "Radware Captcha Page".
def is_blocked(url: str, html: str) -> bool:
    if "validate.perfdrive.com" in (url or "").lower():
        return True
    low = (html or "").lower()
    return "radware captcha page" in low or "we apologize for the inconvenience" in low


def parse_listed_companies(html: str) -> list[dict]:
    """Extract one row per company from a list-old letter page."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for box in soup.select("div.boxQuotata"):
        title = box.select_one("span.boxQuotataTitle")
        if not title:
            continue
        name = title.get_text(strip=True)
        if not name:
            continue
        code = ""
        for a in box.find_all("a", href=True):
            m = re.search(r"codConsob=(\d+)", a["href"])
            if m:
                code = m.group(1)
                break
        rows.append({"Name": name, "codConsob": code})
    return rows


def to_sqldict(rows: list[dict]) -> dict:
    """Map parsed rows into the project's fixed SQL-Ready structure (keys frozen)."""
    sqldict = {k: [] for k in (
        'bvdid', 'priority', 'ListLabel', 'Typology', 'EntryType', 'Name',
        'InternalID_1', 'InternalID_1_type', 'InternalID_2', 'InternalID_2_type',
        'InternalID_3', 'InternalID_3_type', 'CoType', 'License_Type', 'Address_1',
        'Address_2', 'City', 'Zip', 'Cntry', 'Phone', 'Fax', 'Website', 'Email',
        'RegulationType', 'RegulationTypeCode', 'RegulationDate', 'CancellationDate',
        'RegCtry', 'RegCode', 'ListCode', 'ListLanguage', 'ListValidityDate',
        'ListName', 'ListProcessDate', 'LEI Code', 'BIC SWIFT Code',
        'Name - Mother Company', 'Address_1 - Mother company',
        'Address_2 -  Mother company', 'City - Mother company',
        'Zip - Mother company', 'Cntry - Mother company', 'Phone - Mother company',
    )}
    processdate = datetime.datetime.now().strftime('%Y-%m-%d')
    for row in rows:
        for k in sqldict:
            sqldict[k].append("")
        sqldict['Name'][-1] = row['Name']
        sqldict['InternalID_1'][-1] = row['codConsob']
        sqldict['InternalID_1_type'][-1] = 'codConsob' if row['codConsob'] else ''
        sqldict['Cntry'][-1] = 'Italy'
        sqldict['RegCtry'][-1] = 'Italy'
        sqldict['RegCode'][-1] = 'CONSOB'
        sqldict['RegulationType'][-1] = 'Regulated'
        sqldict['ListName'][-1] = 'Listed Companies'
        sqldict['ListCode'][-1] = 'IT CONSOB 7'
        sqldict['ListLanguage'][-1] = 'English'
        sqldict['ListProcessDate'][-1] = processdate
    return sqldict
