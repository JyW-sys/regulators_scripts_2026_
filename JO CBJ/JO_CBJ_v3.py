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
# ListLabel rule (per ticket owner): 1 = bank named in list name, 2 = insurance,
#   3 = bank & insurance, 4 = other.  Only list 1 ("Directory of Banks") = 1.
#
# Scope decisions (confirmed with ticket owner):
#   * Inactive / cancelled / revoked / insolvent / under-liquidation entities
#     are EXCLUDED. Output holds only currently-regulated entities.
#   * List 4 "include everything": the Central Bank of Jordan self-entry and the
#     active money-exchange companies ARE included; the branches table lists
#     sub-locations of already-captured companies, so it is treated as branch
#     info, not separate entities.
#
# --- v3 rebuild note (pagination) -------------------------------------------
# Lists 2 & 3 render as paginated card grids under /EN/List/*. Their numeric
# pager posts back to the same GET-only rewritten URL, which the CBJ server
# answers with HTTP 404 -- the "next page" button is broken server-side even in
# a real browser, so requests AND Selenium both only ever see page 1. v2 worked
# around this with Selenium and captured page 1 only (9 of the 15 specialized
# finance companies were lost).
#
# v3 stops fighting the pager. Every card links to a detail page
#   /EN/ListDetails/<slug>/<blockId>/<n>
# where <n> is a small contiguous index (1, 2, 3, ...). We read <blockId> off
# page 1, then walk the detail indices directly (n = 1, 2, ... until a run of
# "Page not found" pages), which reaches EVERY entity regardless of the pager.
# This is the "page button collects all data" fix requested on the ticket.
#
# The cbj.gov.jo server is very slow to first byte (tens of seconds) and
# intermittently drops requests, so every fetch uses a long timeout + retries
# and detail pages are fetched concurrently.
# ------------------------------------------------------------------
import os
import re
import time
import tempfile
import datetime
import requests
import urllib3
from bs4 import BeautifulSoup
import pandas as pd
import pdfplumber
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings()

# Slow server: long per-request timeout, several retries, and concurrent detail
# fetches (the server serves parallel requests fine).
TIMEOUT = 180
RETRIES = 4
MAX_WORKERS = 8

regulatorName = "JO CBJ"
print(f"Running {regulatorName} Web Scraping Tool v.3.0")

scriptfolder = os.path.dirname(os.path.abspath(__file__))
tempfolder = os.path.join(scriptfolder, "tempfolder")
os.makedirs(tempfolder, exist_ok=True)

BASE = "https://www.cbj.gov.jo"
# Use a real browser User-Agent. A bot UA ("RegulatorBot/1.0") is served fine on
# GET but is a classic thing for a WAF/proxy to block on POST -- which is exactly
# how List 1's pager silently degrades to page 1 only on the control server.
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0.0.0 Safari/537.36"}

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


def new_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    s.verify = False
    return s


def fetch_soup(sess, url, retries=RETRIES):
    """GET url with retries on the flaky/slow CBJ server -> BeautifulSoup."""
    for i in range(retries):
        try:
            r = sess.get(url, timeout=TIMEOUT)
            r.raise_for_status()
            r.encoding = "utf-8"
            return BeautifulSoup(r.text, "html.parser")
        except Exception as e:
            print(f"   retry {i+1}/{retries} for {url}: {e}")
            time.sleep(3 * (i + 1))
    return None


def blank_row():
    return {c: '' for c in COLUMNS}


def clean(v):
    return '' if (v or '').strip() in ('-', '') else v.strip()


def split_city_zip(text):
    """From a 'P.O. Box. 5570 Amman 11953 Jordan' style string -> (city, zip)."""
    zip_m = ZIP_RE.search(text or '')
    zipcode = zip_m.group(1) if zip_m else ''
    city = ''
    if zip_m:
        before = text[:zip_m.start()].strip().split()
        if before:
            city = before[-1].strip(',.')
    if not city and 'Amman' in (text or ''):
        city = 'Amman'
    return city, zipcode


# ==================================================================
# LIST 1 - Directory of Banks (paginated HTML table)
# The /EN/Pages/* route (unlike /EN/List/*) accepts a normal full-form POST, so
# its numeric pager can be walked with requests. Each page is slow to load.
#
# Control-server fix: the POST pager degraded to page 1 only (10 of 20 banks) on
# the control server -- GET works there but the pager POST was being blocked
# (bot User-Agent / missing postback headers / body stripped by a proxy). Now:
#   * a real-browser User-Agent + postback headers (Content-Type/Referer/Origin),
#   * every POST is verified to actually advance the page (a stripped body makes
#     the server return page 1 again -> treated as failure, not silent success),
#   * and a Selenium fallback drives a real browser through the pager if the
#     requests POST path still walks only one page.
# ==================================================================
def aspnet_form_data(soup):
    """input name->value pairs to replay a postback, skipping button inputs so
    we set __EVENTTARGET ourselves."""
    data = {}
    for inp in soup.select("input"):
        name = inp.get("name")
        if not name:
            continue
        if (inp.get("type") or "").lower() in ("image", "submit", "button", "reset"):
            continue
        data[name] = inp.get("value", "")
    return data


def current_page_num(soup):
    el = soup.select_one(".CurrentPageClass")
    if el and el.get_text(strip=True).isdigit():
        return int(el.get_text(strip=True))
    return None


def next_page_target(soup, current):
    """__doPostBack target of the numeric pager link for page current+1, or None
    when the current page is the last."""
    for a in soup.select("a.NumericClass"):
        if a.get_text(strip=True) == str(current + 1):
            m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
            if m:
                return m.group(1)
    return None


def iter_postback_pages(sess, url):
    """Yield a soup for every page of a /EN/Pages/* list by replaying the numeric
    pager via full-form POSTs in one session.

    The POST carries browser-like postback headers (Content-Type / Referer /
    Origin) so a WAF/proxy on the control server treats it as a real form
    submission. After each POST we VERIFY the page actually advanced: a proxy
    that strips the POST body makes the server return page 1 again, which would
    otherwise loop forever or masquerade as success. A page that fails to
    advance is retried, then treated as a hard stop (caller falls back)."""
    post_headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": url,
        "Origin": BASE,
        "X-Requested-With": "XMLHttpRequest",
    }

    def post(data):
        for i in range(RETRIES):
            try:
                r = sess.post(url, data=data, headers=post_headers, timeout=TIMEOUT)
                r.raise_for_status()
                r.encoding = "utf-8"
                return BeautifulSoup(r.text, "html.parser")
            except Exception as e:
                print(f"   retry {i+1}/{RETRIES} POST {url}: {e}")
                time.sleep(3 * (i + 1))
        return None

    soup = fetch_soup(sess, url)
    if soup is None:
        raise RuntimeError(f"Failed to fetch {url}")
    page = 1
    yield soup
    while True:
        cur = current_page_num(soup) or page
        tgt = next_page_target(soup, cur)
        if not tgt:
            break
        data = aspnet_form_data(soup)
        data["__EVENTTARGET"] = tgt
        data["__EVENTARGUMENT"] = ""
        nxt = post(data)
        if nxt is None:
            raise RuntimeError(f"page {cur+1} of {url} failed to load")
        if (current_page_num(nxt) or 0) != cur + 1:
            # POST accepted but page did not advance (body stripped by a proxy,
            # or the pager is server-blocked). Don't silently keep page 1.
            raise RuntimeError(
                f"page {cur+1} of {url} did not advance (got page "
                f"{current_page_num(nxt)}); POST pagination unusable")
        page = cur + 1
        soup = nxt
        yield soup


def _rows_from_bank_table(soup):
    """Turn one Directory-of-Banks table page (soup) into SQL-Ready rows."""
    table = soup.find("table")
    if not table:
        return []
    out = []
    rows = table.find_all("tr")
    header = [c.get_text(" ", strip=True) for c in rows[0].find_all(["th", "td"])]
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
        mailbox = rec.get("Mailbox", "").strip()     # P.O. Box number
        r = blank_row()
        r.update({
            "ListLabel": 1,
            "Name": name,
            "CoType": rec.get("type", "").strip(),
            "Typology": rec.get("type", "").strip(),
            "Address_2": f"P.O. Box {mailbox}" if mailbox else "",
            "City": city if len(city) > 1 else '',
            "Zip": zipcode,
            "Cntry": "JO",
            "Phone": rec.get("phone number", "").strip(),
            "Fax": rec.get("Fax Number", "").strip(),
            "Website": rec.get("website", "").strip(),
            "ListCode": 1,
            "ListName": "Directory of Banks",
        })
        out.append(r)
    return out


def scrape_list1_selenium():
    """Browser fallback for the Directory of Banks pager: drive a real Chrome,
    click the numeric pager (the genuine __doPostBack the server accepts), and
    read the table off each page. Used when the requests-based POST pager is
    blocked on the control server. Dedupes by Name across pages."""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC  # noqa: F401
    except Exception as e:
        print(f"   selenium unavailable for List 1 fallback: {e}")
        return []

    os.environ.setdefault("SE_CACHE_PATH",
                          os.path.join(tempfile.gettempdir(), "selenium_cache"))
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument(f"--user-agent={HEADERS['User-Agent']}")
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"   could not start Chrome for List 1 fallback: {e}")
        return []

    url = BASE + "/EN/Pages/Bankingsectorguide"
    driver.set_page_load_timeout(TIMEOUT)
    # The CBJ server can take >2 min to first byte; raise Selenium's own HTTP
    # command timeout (default 120s) so it doesn't pre-empt the page-load wait.
    try:
        driver.command_executor._client_config.timeout = TIMEOUT
    except Exception:
        pass
    seen, out = set(), []
    try:
        driver.get(url)
        wait = WebDriverWait(driver, TIMEOUT)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "table"))
        while True:
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for rec in _rows_from_bank_table(soup):
                if rec["Name"] in seen:
                    continue
                seen.add(rec["Name"])
                out.append(rec)
            cur = current_page_num(soup) or 1
            tgt = next_page_target(soup, cur)
            if not tgt:
                break
            # Do what __doPostBack does (set the event fields, submit the form)
            # directly. Avoids the sticky-footer overlay that intercepts a native
            # click, and Chrome's strict-mode guard that rejects calling the
            # site's own __doPostBack from injected script.
            driver.execute_script(
                "var f=document.forms[0];"
                f"f['__EVENTTARGET'].value={tgt!r};"
                "f['__EVENTARGUMENT'].value='';"
                "f.submit();")
            try:
                wait.until(lambda d: (current_page_num(
                    BeautifulSoup(d.page_source, "html.parser")) or cur) == cur + 1)
            except Exception:
                print(f"   List 1 fallback: page {cur+1} did not load; stopping")
                break
    except Exception as e:
        print(f"   List 1 fallback error ({e}); keeping {len(out)} rows so far")
    finally:
        driver.quit()
    return out


def scrape_list1():
    """Directory of Banks. Primary path: replay the numeric pager via hardened
    full-form POSTs. If that walks only one page (pager POST blocked on the
    control server), fall back to driving a real browser through the pager so
    every page is still collected. Dedupes by Name."""
    url = BASE + "/EN/Pages/Bankingsectorguide"
    sess = new_session()
    seen, out, pages = set(), [], 0
    try:
        for soup in iter_postback_pages(sess, url):
            pages += 1
            for rec in _rows_from_bank_table(soup):
                if rec["Name"] in seen:
                    continue
                seen.add(rec["Name"])
                out.append(rec)
    except Exception as e:
        print(f"   !! POST pager unusable ({e}); trying browser fallback")

    # One page only means the pager didn't turn (only page 1's ~10 banks). Drive
    # a real browser to collect every page.
    if pages <= 1:
        print("   POST pager returned a single page; using browser fallback")
        fb = scrape_list1_selenium()
        for rec in fb:
            if rec["Name"] in seen:
                continue
            seen.add(rec["Name"])
            out.append(rec)
    return out


# ==================================================================
# LISTS 2 & 3 - card listing -> detail pages, walked by detail index
# ==================================================================
def detail_field_map(soup):
    """Parse the 'General Information' block into {label: value}.
    CBJ detail pages use two markups: plain <p>Label: value</p>, and a nested
    <span><strong>Label:</strong></span> value form. Iterating leaf block-level
    elements and joining their text with a space keeps each label+value on one
    line for both layouts."""
    block = soup.select_one("div.contentbdody") or soup
    fields = {}
    for el in block.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        if el.find(["p", "div"]):          # skip containers, keep leaf blocks
            continue
        for br in el.find_all("br"):
            br.replace_with("\n")
        for raw in el.get_text(" ").split("\n"):
            line = re.sub(r'\s+', ' ', raw).strip()
            if ":" in line:
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k and k not in fields:
                    fields[k] = v
    return fields


def parse_pobox_line(text):
    """From a 'P.O Box and Postal code' value -> (city, zip, 'P.O. Box NNN').
    The PO box number usually appears before the postal code, and some pages use
    reversed parentheses, e.g. 'PO Box )23543( Amman 11115 Jordan'."""
    if not text or text.strip() in ('-', ''):
        return '', '', ''
    t = text
    m = re.search(r'(?:post\s*code|postal\s*code)\D*(\d{4,5})', t, re.I)
    if m:
        zipcode = m.group(1)
    else:
        nums = re.findall(r'\b(\d{5})\b', t)
        zipcode = nums[-1] if nums else ''   # PO box tends to come first
    box_m = re.search(r'(?:p\.?\s*o\.?\s*box|box)\D*?(\d{3,6})', t, re.I)
    addr2 = f"P.O. Box {box_m.group(1)}" if box_m else ''
    city = ''
    if zipcode:
        before = t[:t.rfind(zipcode)].strip().split()
        if before:
            cand = before[-1].strip(',.()/')
            if cand and not cand.isdigit() and len(cand) > 1:
                city = cand
    if not city and 'Amman' in t:
        city = 'Amman'
    return city, zipcode, addr2


def breadcrumb_leaf(soup):
    """Entity name = last breadcrumb crumb. Detail pages that omit the
    'Company Name' field still name the entity in the breadcrumb trail
    (e.g. Home / Financial Stability / ... / <entity name>)."""
    name = ''
    for bc in soup.select(".breadcrumb"):
        lis = bc.select("li")
        if lis:
            name = lis[-1].get_text(" ", strip=True)
    return re.sub(r'\s+', ' ', name).strip()


def list_block_id(sess, list_url):
    """Read the numeric <blockId> shared by a list's detail URLs off page 1's
    cards: href = /EN/ListDetails/<slug>/<blockId>/<n>."""
    soup = fetch_soup(sess, list_url)
    if soup is None:
        return None, {}
    block_id = None
    titles = {}                                     # {index: card title}
    up = soup.select_one("div.UpdatePanel") or soup
    for card in up.select("div.card"):
        a = card.select_one("a.readmore2[href], a#lnkMore[href]")
        if not a:
            continue
        m = re.search(r'/ListDetails/[^/]+/(\d+)/(\d+)', a["href"])
        if not m:
            continue
        block_id = int(m.group(1))
        t = card.select_one("h6.card-title")
        if t:
            titles[int(m.group(2))] = t.get_text(" ", strip=True)
    return block_id, titles


def parse_detail(soup, name):
    """Build a row from a detail-page soup. Returns None if the entity is
    inactive (license cancelled / revoked / insolvent / under liquidation)."""
    if INACTIVE_RE.search(name):
        return None
    # the '/status' suffix (if any) is not part of the legal name
    clean_name = re.split(r'\s*/\s*', name)[0].strip()

    f = detail_field_map(soup)
    clean_name = clean(f.get("Company Name", "")) or clean_name
    addr = clean(f.get("The head office address", ""))
    city, zipcode, addr2 = parse_pobox_line(f.get("P.O Box and Postal code", ""))
    if not city and addr:
        city = re.split(r'[–\-,]', addr)[0].strip()
    phone = re.sub(r'\s+', '', clean(f.get("Telephone number", "")))
    fax = re.sub(r'\s+', '', clean(f.get("Fax number", "")))
    website = clean(f.get("Website", ""))
    email = clean(f.get("E-mail address", ""))

    r = blank_row()
    r.update({
        "ListLabel": 4,
        "Name": clean_name,
        "Address_1": addr,
        "Address_2": addr2,
        "City": city if city not in ('-', '') else 'Amman',
        "Zip": zipcode,
        "Cntry": "JO",
        "Phone": phone,
        "Fax": fax,
        "Website": website,
        "Email": email,
    })
    return r


def scrape_card_list(list_url, slug, list_code, list_name, batch=10, max_index=60):
    """Walk a /EN/List/* card listing by detail index, bypassing the broken pager.
    Reads <blockId> off page 1, then fetches /EN/ListDetails/<slug>/<blockId>/<n>
    for n = 1, 2, ... in concurrent batches, stopping after a whole batch of
    'Page not found' pages. Reaches every entity across every (unreachable) pager
    page."""
    sess = new_session()
    block_id, titles = list_block_id(sess, list_url)
    if block_id is None:
        print(f"   !! could not read blockId for {list_url}")
        return []
    print(f"   blockId {block_id}; page-1 cards {len(titles)}")

    def fetch(n):
        url = f"{BASE}/EN/ListDetails/{slug}/{block_id}/{n}"
        soup = fetch_soup(sess, url)
        if soup is None:
            return n, None, None
        body = soup.select_one("div.contentbdody") or soup
        txt = re.sub(r'\s+', ' ', body.get_text(" ", strip=True))
        if "Page not found" in txt or len(txt) < 70:
            return n, None, None                    # index not used
        name = breadcrumb_leaf(soup) or titles.get(n, "")
        return n, soup, name

    rows = []
    n = 1
    while n <= max_index:
        idxs = list(range(n, n + batch))
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            results = list(ex.map(fetch, idxs))
        any_found = False
        for i, soup, name in results:
            if soup is None:
                continue
            any_found = True
            rec = parse_detail(soup, name)
            if rec is None:
                print(f"   - skip inactive: {name}")
                continue
            rec.update({"ListCode": list_code, "ListName": list_name})
            rows.append(rec)
        if not any_found:                           # whole batch empty -> end
            break
        n += batch
    return rows


# ==================================================================
# PDF helpers  (Lists 4 & 5)
# ==================================================================
def _fetch_pdf(url, dest, attempts=4):
    """GET url and save to dest only if the body is genuinely a PDF. Guards
    against proxy/HTML interstitials, and retries with escalating backoff because
    cbj.gov.jo intermittently throttles the later requests in a session."""
    for attempt in range(attempts):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
            ctype = r.headers.get("Content-Type", "").lower()
            is_pdf = r.content[:4] == b"%PDF" or "application/pdf" in ctype
            if r.status_code == 200 and len(r.content) > 10000 and is_pdf:
                with open(dest, "wb") as fh:
                    fh.write(r.content)
                return True
            print(f"   PDF fetch unusable (status {r.status_code}, "
                  f"{len(r.content)} B, {ctype or 'no ctype'}) from {url}")
        except Exception as e:
            print(f"   PDF fetch error {e} from {url}")
        if attempt < attempts - 1:
            time.sleep(2 * (attempt + 1))
    return False


def _is_pdf_file(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"%PDF"
    except Exception:
        return False


def _await_download(before, wait, suffix=".pdf"):
    """Wait up to wait s for a new finished *.pdf in tempfolder."""
    deadline = time.time() + wait
    while time.time() < deadline:
        try:
            current = set(os.listdir(tempfolder))
        except FileNotFoundError:
            current = set()
        for f in current - before:
            if not f.lower().endswith(suffix):
                continue
            path = os.path.join(tempfolder, f)
            try:
                size = os.path.getsize(path)
                time.sleep(1)
                if (os.path.getsize(path) == size
                        and not os.path.exists(path + ".crdownload")):
                    return path
            except FileNotFoundError:
                continue
        time.sleep(1)
    return None


def _fetch_pdf_selenium(candidates, dest, landing_url=None, wait=600):
    """Browser fallback for the flaky cbj.gov.jo PDFs: a fresh headless-Chrome
    session visits the landing page first (the server is session/referer
    sensitive) then navigates to the PDF URL, saving it into tempfolder."""
    try:
        from selenium import webdriver
    except Exception as e:
        print(f"   selenium unavailable, skipping browser download: {e}")
        return False
    os.environ.setdefault("SE_CACHE_PATH",
                          os.path.join(tempfile.gettempdir(), "selenium_cache"))
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_experimental_option("prefs", {
        "plugins.always_open_pdf_externally": True,
        "download.prompt_for_download": False,
        "download.default_directory": tempfolder,
        "profile.default_content_setting_values.automatic_downloads": 1,
    })
    try:
        driver = webdriver.Chrome(options=opts)
    except Exception as e:
        print(f"   could not start Chrome for browser download: {e}")
        return False
    driver.set_page_load_timeout(wait)
    try:
        try:
            driver.execute_cdp_cmd("Page.setDownloadBehavior",
                                   {"behavior": "allow", "downloadPath": tempfolder})
        except Exception:
            pass
        if landing_url:
            try:
                driver.get(landing_url)
                time.sleep(2)
            except Exception as e:
                print(f"   browser landing nav slow/timeout: {e}")
        seen = set()
        for url in candidates:
            if url in seen:
                continue
            seen.add(url)
            before = set(os.listdir(tempfolder))
            try:
                driver.get(url)
            except Exception as e:
                print(f"   browser nav slow/timeout for {url}: {e}")
            got = _await_download(before, wait)
            if got and _is_pdf_file(got):
                os.replace(got, dest)
                print(f"   browser-downloaded {os.path.basename(dest)}")
                return True
        return False
    finally:
        driver.quit()
        try:
            for f in os.listdir(tempfolder):
                if f.startswith("downloads.html") or f.endswith(".crdownload"):
                    try:
                        os.remove(os.path.join(tempfolder, f))
                    except OSError:
                        pass
        except FileNotFoundError:
            pass


def discover_pdf_links(landing_path, href_keyword):
    """Find PDF anchors on a landing page whose href matches href_keyword
    (the ticket's fallback: 'in case the pdf link is not working, click the
    link under ...')."""
    urls = []
    try:
        soup = fetch_soup(new_session(), BASE + landing_path)
        if soup is None:
            return urls
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if ".pdf" not in href.lower():
                continue
            if href_keyword.lower() in href.lower():
                urls.append(href if href.startswith("http") else BASE + href)
    except Exception as e:
        print(f"   landing-page PDF discovery failed: {e}")
    return urls


def download_pdf(path, dest_name, landing_path=None, href_keyword=None):
    """Download a CBJ PDF robustly: direct URL -> discovered link -> browser
    session -> cached copy -> raise with a manual-download instruction."""
    dest = os.path.join(tempfolder, dest_name)
    candidates = [BASE + path] if path else []
    if landing_path and href_keyword:
        for u in discover_pdf_links(landing_path, href_keyword):
            if u not in candidates:
                candidates.append(u)

    for url in candidates:
        if _fetch_pdf(url, dest):
            return dest

    landing_url = BASE + landing_path if landing_path else None
    if candidates and _fetch_pdf_selenium(candidates, dest, landing_url=landing_url):
        return dest

    if os.path.exists(dest):
        print(f"   using cached copy {dest_name}")
        return dest
    raise RuntimeError(
        f"No PDF available for {dest_name}. All download URLs failed "
        f"(likely a network/proxy block). Manually download it from "
        f"{BASE}{landing_path or path} and place it at {dest}, then rerun.")


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
    return re.sub(r'\s*\*+\s*$', '', name).strip()


# ==================================================================
# LIST 4 - general register of e-payment / money-transfer companies
# ==================================================================
def scrape_list4():
    fp = download_pdf(
        "/EBV4.0/Root_Storage/AR/Domestic/A_general_register_of_licensed_companies.pdf",
        "list4.pdf",
        landing_path="/En/List/Participants_in_Payments_and_Settlements_Systems",
        href_keyword="general_register_of_licensed")
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
    return out


def parse_list4_profile(page, text):
    if INACTIVE_RE.search(text) and re.search(r'license\s+.*(cancel|revok)', text, re.I):
        return None
    rows = rows_by_top(page)
    if not rows:
        return None
    header_size = rows[0][0]
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

    def find_row(label):
        for i, (_, txt) in enumerate(rows):
            if re.search(label, txt):
                return i
        return None

    i_phone = find_row(r'Phone number')
    i_mail = find_row(r'Mailing address')
    i_email = find_row(r'E-?mail')

    addr = ''
    if i_phone is not None:
        chunk = ' '.join(t for _, t in rows[body_start:i_phone])
        chunk = re.sub(r'\bAddress\b\s*:?', '', chunk, count=1)
        chunk = re.sub(r'\bth\b', '', chunk)
        addr = re.sub(r'\s+', ' ', chunk).strip(' :,-')

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
    Cancelled ones carry a trailing '*' pointing to a '*Cancellation of ...'
    footnote and are excluded."""
    page_has_cancellation = bool(re.search(r'Cancellation of', text, re.I))
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or INACTIVE_RE.search(line):
            continue
        m = re.match(r'(.+?)\s+\d{1,3}\s*/\s*\d{4}\s+\d{1,2}/\d{1,2}/\d{4}\s*$', line)
        if not m:
            continue
        raw = m.group(1).strip()
        if raw.endswith('*') and page_has_cancellation:
            continue
        name = raw.strip(' *')
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
        "list5.pdf",
        landing_path="/En/List/Participants_in_Payments_and_Settlements_Systems",
        href_keyword="accredited_international")
    out = []
    with pdfplumber.open(fp) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            if "accreditation" not in text.lower():
                continue
            rows = rows_by_top(page)
            if not rows or not rows[0][1].strip().startswith('"'):
                continue
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
r2 = scrape_card_list(BASE + "/EN/List/Specialized_Finance_Company",
                      "Specialized_Finance_Company", 2, "Specialized Finance Company")
print(f"   {len(r2)} entities"); all_rows += r2

print("[List 3] Microfinance Company ...")
r3 = scrape_card_list(BASE + "/EN/List/Guide_of_Microfinance_Sector",
                      "Guide_of_Microfinance_Sector", 3, "Microfinance Company")
print(f"   {len(r3)} entities"); all_rows += r3

# Lists 4 & 5 are PDFs on a flaky server. Don't let one unreachable PDF crash
# the whole run and discard lists 1-3: warn loudly and carry on.
skipped = []
print("[List 4] Electronic Payment & Money Transfer register (PDF) ...")
try:
    r4 = scrape_list4(); print(f"   {len(r4)} entities"); all_rows += r4
except Exception as e:
    print(f"   !! LIST 4 SKIPPED: {e}"); skipped.append(4)

print("[List 5] Accredited international e-payment systems (PDF) ...")
try:
    r5 = scrape_list5(); print(f"   {len(r5)} entities"); all_rows += r5
except Exception as e:
    print(f"   !! LIST 5 SKIPPED: {e}"); skipped.append(5)

# common fields
for r in all_rows:
    r["RegCtry"] = "JO"
    r["RegCode"] = "CBJ"
    r["RegulationType"] = "Regulated"
    r["ListLanguage"] = "EN"
    r["ListProcessDate"] = PROCESS_DATE

df = pd.DataFrame(all_rows).reindex(columns=COLUMNS, fill_value="")
df['City'] = df['City'].replace({":": ""})
now = datetime.datetime.now()
outfile = os.path.join(
    scriptfolder,
    "{} SQL Ready {}.xlsx".format(regulatorName, str(now).replace(":", ".")[:-7]))
df.to_excel(outfile, sheet_name="SQL Ready", index=False)

print("\n==== SUMMARY ====")
print("Total rows:", len(df))
for code in sorted(df['ListCode'].unique()):
    print(f"  List {code}: {len(df[df['ListCode'] == code])}")
if skipped:
    print(f"  !! INCOMPLETE - lists {skipped} could not be downloaded; "
          f"download the PDF(s) manually into {tempfolder} and rerun.")
print("Output:", outfile)
for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))
# ==================================================================
# Generate one PDF per list (entity names, one per line) into tempfolder,
# the same deliverable as IT CONSOB / HU CBH:
#   "<xlsx basename>- <ListCode>.pdf"
# ==================================================================
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    arial_path = r"C:\Windows\Fonts\arial.ttf"
    if os.path.exists(arial_path):
        pdfmetrics.registerFont(TTFont('ArialUni', arial_path))
        FONT_NAME = 'ArialUni'
    else:
        FONT_NAME = 'Helvetica'

    def safe_filename(name):
        name = str(name).strip()
        return re.sub(r'[\\/:*?"<>|]+', '_', name) or "UNKNOWN"

    def draw_header(c, y):
        c.setFont(FONT_NAME, 14)
        c.drawString(72, y, "Name")
        c.line(72, y - 4, 540, y - 4)
        c.setFont(FONT_NAME, 12)
        return y - 24

    def export_list_to_pdf(data_list, pdf_filename):
        c = canvas.Canvas(pdf_filename, pagesize=letter)
        c.setFont(FONT_NAME, 12)
        y = draw_header(c, 740)
        max_lines_per_page = 32
        line_count = 0
        for item in data_list:
            c.drawString(72, y, str(item))
            y -= 20
            line_count += 1
            if line_count >= max_lines_per_page:
                c.showPage()
                c.setFont(FONT_NAME, 12)
                y = draw_header(c, 740)
                line_count = 0
        c.save()

    print("\nGenerating per-list PDF files ...")
    pdf_base = os.path.splitext(os.path.basename(outfile))[0]
    for list_code, group in df.groupby('ListCode', dropna=False):
        items = group['Name'].dropna().astype(str).tolist()
        if not items:
            continue
        pdf_path = os.path.join(
            tempfolder, f"{pdf_base}- {safe_filename(list_code)}.pdf")
        export_list_to_pdf(items, pdf_path)
        print(f"   {os.path.basename(pdf_path)} ({len(items)} names)")
except Exception as e:
    print(f"!! PDF generation failed (xlsx output is unaffected): {e}")
