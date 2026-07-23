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
import tempfile
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
print(f"Running {regulatorName} Web Scraping Tool v.2.0")

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
# ASP.NET __doPostBack pagination
# The CBJ lists page with WebForms __doPostBack links (no JSON API). Two
# different back-ends need two different strategies:
#   * /EN/Pages/* (List 1) accepts a normal full-form POST -> walked with
#     requests below.
#   * /EN/List/*  (Lists 2-3) sit behind a GET-only URL rewrite that 404s any
#     POST (full form AND MS-Ajax UpdatePanel alike), so they are walked with
#     Selenium instead (see collect_card_targets).
# Either way each page costs ~20-60 s because the server is slow to first byte,
# so pagination is unavoidably slow but complete.
# ==================================================================
def aspnet_form_data(soup):
    """All input name->value pairs needed to replay a postback, skipping
    image/submit buttons so we set __EVENTTARGET ourselves."""
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
    """__doPostBack target of the numeric pager link for page `current+1`, or
    None when the current page is the last (the pager renders one <a> per page
    plus a separate prev/next image button)."""
    for a in soup.select("a.NumericClass"):
        if a.get_text(strip=True) == str(current + 1):
            m = re.search(r"__doPostBack\('([^']+)'", a.get("href", ""))
            if m:
                return m.group(1)
    return None


def iter_postback_pages(url, retries=3):
    """Yield a soup for every page of a /EN/Pages/* list by replaying the
    numeric pager via full-form POSTs in one session."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    sess.verify = False

    def fetch(method, **kw):
        for i in range(retries):
            try:
                r = sess.request(method, url, timeout=120, **kw)
                r.raise_for_status()
                r.encoding = "utf-8"
                return BeautifulSoup(r.text, "html.parser")
            except Exception as e:
                print(f"   retry {i+1}/{retries} for {url} ({method}): {e}")
                time.sleep(2)
        return None

    soup = fetch("GET")
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
        nxt = fetch("POST", data=data)
        if nxt is None:
            print(f"   !! page {cur+1} of {url} failed to load; stopping")
            break
        page = cur + 1
        soup = nxt
        yield soup


# ==================================================================
# LIST 1 - Directory of Banks (paginated HTML table)
# ==================================================================
def scrape_list1():
    url = BASE + "/EN/Pages/Bankingsectorguide"
    out = []
    for soup in iter_postback_pages(url):
        table = soup.find("table")
        if not table:
            continue
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
            website = rec.get("website", "").strip()
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
    """Parse the 'General Information' block into {label: value}.
    CBJ detail pages use two markups: plain <p>Label: value</p>, and a nested
    <span><strong>Label:</strong></span> value form. Iterating leaf block-level
    elements and joining their text with a space keeps each label+value on one
    line for both layouts (get_text('\\n') splits the nested form onto separate
    lines and breaks the colon split)."""
    block = soup.select_one("div.contentbdody") or soup
    fields = {}
    for el in block.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
        if el.find(["p", "div"]):          # skip containers, keep leaf blocks
            continue
        # Some pages pack the whole profile into one <p> with <br> separators;
        # turn each <br> into a newline so the label:value pairs split apart,
        # while nested inline <span>/<strong> tags still collapse to one line.
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


def _collect_cards(soup, targets):
    """Add this page's cards to {detail_url: card name}. Name lives on the card
    title (h6.card-title); the <a> text is just 'Read More'."""
    for card in soup.select("div.card"):
        a = card.select_one("a[href]")
        if not a:
            continue
        href = a["href"]
        durl = href if href.startswith("http") else BASE + href
        t = card.select_one("h6.card-title")
        name = t.get_text(" ", strip=True) if t else a.get_text(" ", strip=True)
        targets.setdefault(durl, name.replace("Read More", "").strip())


def _build_chrome():
    from selenium import webdriver
    # Selenium Manager's default driver cache (~/.cache) may not be writable;
    # point it at a writable temp dir so chromedriver is cached and reused.
    os.environ.setdefault("SE_CACHE_PATH",
                          os.path.join(tempfile.gettempdir(), "selenium_cache"))
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    # 'eager' returns at DOMContentLoaded so the MS-Ajax PageRequestManager has
    # initialized - the pager's async postback won't fire otherwise (under
    # 'none' the document stays 'loading' and the handler is never wired).
    opts.page_load_strategy = "eager"
    driver = webdriver.Chrome(options=opts)
    # The server is slow to first byte (~30-70 s to DOMContentLoaded); raise
    # Selenium's client-command timeout above the default 120 s so get() and
    # later commands don't time out on the client side.
    try:
        driver.command_executor._client_config.timeout = 300
    except Exception:
        pass
    return driver


# JS that records the HTTP status of every XHR, so collect_card_targets can tell
# a real page turn from CBJ's broken /EN/List/ pager - clicking "next" there
# fires an async postback the server answers with 404 (verified in a real
# browser), so there's no point waiting the full advance timeout.
_XHR_TAP = (
    "window.__pb=[];"
    "var _o=XMLHttpRequest.prototype.open,_s=XMLHttpRequest.prototype.send;"
    "XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return _o.apply(this,arguments)};"
    "XMLHttpRequest.prototype.send=function(){var x=this;"
    "this.addEventListener('loadend',function(){window.__pb.push({u:x.__u,s:x.status})});"
    "return _s.apply(this,arguments)};"
)


def _wait_for_cards(driver, wait, poll):
    """Poll page_source until a card list with a current-page number has
    rendered. Returns the soup, or None on timeout."""
    deadline = time.time() + wait
    while time.time() < deadline:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if soup.select("div.card") and current_page_num(soup) is not None:
            return soup
        time.sleep(poll)
    return None


def collect_card_targets(list_url, render_wait=180, advance_wait=120, poll=3):
    """Walk every page of a /EN/List/* card listing with Selenium and return
    {detail_url: card name}. These pages 404 on any POST, so requests can't
    page them. The numeric pager advances an MS-Ajax UpdatePanel (no full
    navigation): we click the page link and wait for the CurrentPageClass to
    advance. NOTE: CBJ's own server currently 404s these pager postbacks (the
    page-turn fails even in a real browser), so in practice only page 1 is
    reachable; the XHR tap below detects that 404 and stops fast instead of
    waiting out the full timeout."""
    from selenium.common.exceptions import WebDriverException
    from selenium.webdriver.common.by import By
    targets = {}
    driver = _build_chrome()
    try:
        try:
            driver.get(list_url)
        except WebDriverException as e:
            print(f"   browser landing slow/timeout: {e}")
        try:
            driver.execute_script(_XHR_TAP)
        except WebDriverException:
            pass
        while True:
            soup = _wait_for_cards(driver, render_wait, poll)
            if soup is None:
                print(f"   !! cards never rendered for {list_url}; stopping")
                break
            cur = current_page_num(soup)
            _collect_cards(soup, targets)
            tgt = next_page_target(soup, cur)
            if not tgt:
                break
            # Click the actual <a> so its href runs __doPostBack in the page's
            # own (non-strict) scope; a JS click also dodges the footer overlay
            # that intercepts a real mouse click.
            try:
                driver.execute_script("window.__pb=[];")
                a = driver.find_element(
                    By.XPATH,
                    "//a[@class='NumericClass' and normalize-space(text())='%d']" % (cur + 1))
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", a)
                driver.execute_script("arguments[0].click();", a)
            except WebDriverException as e:
                print(f"   postback click failed on page {cur}: {e}")
                break
            deadline = time.time() + advance_wait
            advanced = False
            server_err = False
            while time.time() < deadline:
                time.sleep(poll)
                if current_page_num(BeautifulSoup(driver.page_source, "html.parser")) == cur + 1:
                    advanced = True
                    break
                bad = [e for e in (driver.execute_script("return window.__pb || []") or [])
                       if e.get("s") and e["s"] >= 400]
                if bad:
                    server_err = True
                    print(f"   !! CBJ returned HTTP {bad[-1]['s']} for the page {cur+1} "
                          f"postback - this list's pagination is broken server-side; "
                          f"stopping with page 1 only")
                    break
            if not advanced:
                if not server_err:
                    print(f"   !! page {cur+1} of {list_url} did not load in "
                          f"{advance_wait}s; stopping")
                break
    finally:
        driver.quit()
    return targets


def scrape_card_list(list_url, list_code, list_name, paginate="selenium"):
    """Scrape a /EN/List/* card listing -> detail pages.
    paginate='selenium' walks every page with a browser (List 2, which has
    multiple pages the GET-only route won't let requests page). paginate='none'
    reads just the single rendered page with requests (List 3)."""
    if paginate == "selenium":
        targets = collect_card_targets(list_url)   # {detail_url: card name}, all pages
        print(f"   {len(targets)} cards across all pages")
    else:
        soup = get_soup(list_url)
        targets = {}
        _collect_cards(soup, targets)
        print(f"   {len(targets)} cards")

    # the server is slow per page, so fetch all detail pages concurrently
    def fetch(durl):
        try:
            return durl, get_soup(durl)
        except Exception as e:
            print(f"   !! detail fetch failed {durl}: {e}")
            return durl, None

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(fetch, targets.keys()))

    def clean(v):
        return '' if (v or '').strip() in ('-', '') else v.strip()

    out = []
    for durl, dsoup in results:
        if dsoup is None:
            continue
        name = targets[durl]
        # inactive status is appended after '/' in the card name -> excluded
        if INACTIVE_RE.search(name):
            print(f"   - skip inactive: {name}")
            continue
        f = detail_field_map(dsoup)
        # detail pages rarely carry 'Company Name'; prefer it if present, else card name
        name = clean(f.get("Company Name", "")) or name

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
            "Name": name,
            "Address_1": addr,
            "Address_2": addr2,
            "City": city if city not in ('-', '') else 'Amman',
            "Zip": zipcode,
            "Cntry": "JO",
            "Phone": phone,
            "Fax": fax,
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
def _fetch_pdf(url, dest, attempts=4):
    """GET url and save to dest only if the body is genuinely a PDF.
    Returns True on success. Guards against proxy/HTML interstitials that
    return 200 with non-PDF content, and retries with escalating backoff
    because cbj.gov.jo intermittently drops/throttles the later requests in
    a session (the last list's PDF is the usual victim)."""
    for attempt in range(attempts):
        try:
            r = requests.get(url, headers=HEADERS, timeout=120, verify=False)
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
            time.sleep(2 * (attempt + 1))   # 2s, 4s, 6s backoff
    return False


def _is_pdf_file(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"%PDF"
    except Exception:
        return False


def _await_download(before, wait, suffix=".pdf"):
    """Wait up to `wait`s for a new, finished file ending in `suffix` to appear
    in tempfolder. Returns its path, or None on timeout. The suffix filter skips
    in-progress (.crdownload) partials and the interstitial 'downloads.html'
    pages cbj.gov.jo sometimes serves; tolerates files that vanish mid-check."""
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
                time.sleep(1)                   # let the write settle
                if (os.path.getsize(path) == size
                        and not os.path.exists(path + ".crdownload")):
                    return path
            except FileNotFoundError:           # vanished mid-check; keep waiting
                continue
        time.sleep(1)
    return None


def _fetch_pdf_selenium(candidates, dest, landing_url=None, wait=600):
    """Browser-based fallback for the flaky cbj.gov.jo PDFs.
    Plain requests get throttled/dropped on the later PDFs in a session
    (list 5 is the usual victim); a fresh headless-Chrome session visits the
    landing page first (the server is session/referer-sensitive) then navigates
    to the PDF URL, saving it straight into tempfolder. Waits up to `wait` s
    because the server can be very slow to first byte. Returns True on success."""
    try:
        from selenium import webdriver
    except Exception as e:
        print(f"   selenium unavailable, skipping browser download: {e}")
        return False
    # Selenium Manager's default driver cache (~/.cache) is not writable on this
    # box; point it at a writable temp dir so chromedriver is cached and reused.
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
        try:                                    # allow downloads in headless mode
            driver.execute_cdp_cmd("Page.setDownloadBehavior",
                                   {"behavior": "allow", "downloadPath": tempfolder})
        except Exception:
            pass
        if landing_url:                         # establish a session/referer first
            try:
                driver.get(landing_url)
                time.sleep(2)
            except Exception as e:
                print(f"   browser landing nav slow/timeout: {e}")
        seen = set()
        for url in candidates:
            if url in seen:                     # the direct + discovered URL often match
                continue
            seen.add(url)
            before = set(os.listdir(tempfolder))
            try:
                driver.get(url)
            except Exception as e:
                print(f"   browser nav slow/timeout for {url}: {e}")
            got = _await_download(before, wait)  # .pdf only -> ignores downloads.html
            if got and _is_pdf_file(got):
                os.replace(got, dest)
                print(f"   browser-downloaded {os.path.basename(dest)}")
                return True
        return False
    finally:
        driver.quit()
        # sweep any interstitial/partial junk the browser dropped
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
    """Find PDF anchors on a landing page whose href matches href_keyword.
    Used as a fallback when the hard-coded PDF URL stops working (the Jira
    ticket says: 'in case the pdf link is not working, click the link
    under ...')."""
    urls = []
    try:
        soup = get_soup(BASE + landing_path)
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
    """Download a CBJ PDF robustly across machines/networks:
       1. try the hard-coded direct URL,
       2. else discover the current link from the landing page,
       3. else fall back to a cached tempfolder copy,
       4. else raise with a manual-download instruction.
    """
    dest = os.path.join(tempfolder, dest_name)
    candidates = [BASE + path] if path else []
    if landing_path and href_keyword:
        for u in discover_pdf_links(landing_path, href_keyword):
            if u not in candidates:
                candidates.append(u)

    for url in candidates:
        if _fetch_pdf(url, dest):
            return dest

    # requests got throttled/dropped -> retry with a real browser session
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
    # drop trailing footnote asterisks / whitespace
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
    are excluded: their footnote line ('*Cancellation of <name>'s final license')
    is skipped by INACTIVE_RE, and their company row carries a trailing '*' that
    points to that footnote (e.g. 'Al-Alami Exchange Company*', 'Swiss Exchange
    Company*'). Active section-1 companies carry no such marker."""
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
        # trailing '*' = per-company cancellation footnote -> exclude
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

print("[List 2] Specialized Finance Company ...")   # multi-page -> Selenium
r2 = scrape_card_list(BASE + "/EN/List/Specialized_Finance_Company", 2,
                      "Specialized Finance Company", paginate="selenium")
print(f"   {len(r2)} entities"); all_rows += r2

print("[List 3] Microfinance Company ...")          # single page -> requests
r3 = scrape_card_list(BASE + "/EN/List/Guide_of_Microfinance_Sector", 3,
                      "Microfinance Company", paginate="none")
print(f"   {len(r3)} entities"); all_rows += r3

# Lists 4 & 5 are PDFs on a flaky server. Don't let one unreachable PDF
# crash the whole run and discard lists 1-3: warn loudly and carry on.
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
df['City'] = df['City'].replace({":": ""})  # default city if missing
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
          f"the output above is missing them. Download the PDF(s) manually "
          f"into {tempfolder} and rerun to capture them.")
print("Output:", outfile)
for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))