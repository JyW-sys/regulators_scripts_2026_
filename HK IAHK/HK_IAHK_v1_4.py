#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HK IAHK -- Insurance Authority (Hong Kong), public registers.

Jira: https://moodysdatapipeline.atlassian.net/browse/DECD-6746

v1.4 changes vs v1.3 -- ONE BUG, the production 403:

    requests.exceptions.HTTPError: 403 Client Error: Forbidden for url:
        https://www.ia.org.hk/iareg/insurerlist.php?lang=en
      File "...HK-IAHK.py", line 301, in <module>
        payload = get_json(session, INSURERS_LIST_API)

  v1.3 opened a browser purely to collect the cf_clearance cookie, copied it
  into a requests.Session, CLOSED THE BROWSER, and then did all 162 detail
  calls plus both workbook downloads over plain requests.  That hand-off is
  the single point of failure, and it is environment-dependent:

    * on the dev Mac it works -- measured again on 2026-08-13, the same day
      the production run failed: cf_clearance issued, requests -> HTTP 200,
      71567 bytes of JSON;
    * on the Windows production box (Python 3.8) the same code 403s.

  Cloudflare does not treat cf_clearance as a bearer token.  It re-checks the
  caller against the client that was issued the cookie -- User-Agent (v1.3
  copied that), but also the TLS handshake fingerprint and the egress IP.
  Python 3.8's requests/urllib3 does not hand shake like Chrome 139 does, and
  the box may leave through a different proxy hop than the browser did, so
  the cookie is rejected.  Nothing about the site changed; the transport did.

  v1.4 therefore stops depending on the hand-off:

    * the browser STAYS OPEN for the whole run (v1.3 quit it after ~10 s);
    * requests is still tried first, because when it works it is fast
      (~0.7 s/call, measured);
    * the FIRST time requests is refused, the run switches to fetching
      through the browser itself -- a synchronous XMLHttpRequest issued from
      the register page's own origin, which carries Cloudflare state natively
      and cannot be fingerprinted apart from the browser, because it IS the
      browser.  Verified live 2026-08-13: HTTP 200 and 162 insurers parsed
      over that channel, and binary (xlsx) transfers through it as well.
    * the Cloudflare wait is now a POLL, not a flat page.wait(5).  A loaded
      or slow box needs longer than five seconds, and v1.3 would sail past
      the challenge and only fail 15 lines later with a bare 403.
    * if NEITHER channel can read the register the script now stops at that
      point with a message naming the cause, instead of raising a raw
      HTTPError from inside a helper.

  SECOND PRODUCTION FAILURE, same day, fixed here too.  The first v1.4 run on
  the Windows box got past the 403 and then died inside the new poll:

      DrissionPage.errors.ContextLostError:
          The page is refreshed. Please wait until the page is refreshed or
          loaded.                                   (DrissionPage 4.1.1.2)
        File "...HK-IAHK.py", line 322, in load_and_clear
          if not looks_like_challenge(page.html) and ...

  The Cloudflare interstitial RELOADS ITSELF while it works, so the DOM root
  object id DrissionPage holds goes stale under the poll.  That exception is
  not a fault -- it is what "the challenge is still running" looks like from
  outside, and the box was showing it because the challenge was genuinely in
  progress.  Every page read in the wait loop is now guarded and treated as
  "not ready yet" (safe_html / safe_title), the budget went 90 -> 120 s, and
  the browser channel re-anchors itself once if the origin page is lost
  mid-run rather than taking all 162 remaining calls down with it.

  Everything else -- parsing, field mapping, counts -- is v1.3 unchanged.

v1.3 changes vs v1.2 (kept for the record):
  * LIST 1 REWRITTEN.  v1.2 did
        driver.find_element(By.LINK_TEXT, 'Download Full List').click()
    on the Register of Authorized Insurers page.  That link no longer exists
    (confirmed live 2026-08-13: the page has 22 alphabetical tables of insurer
    names and no download anchor at all), so v1.2 died with
    NoSuchElementException before it wrote a single row.
    The register is now served by a JSON API that the page itself calls:
        https://www.ia.org.hk/iareg/insurerlist.php?lang=en          -> 162 insurers
        https://www.ia.org.hk/iareg/insurerdetail.php?lang=en&ubi_no=<id>
    v1.3 reads those directly.  The detail endpoint carries every field the
    retired workbook had (address / tel / fax / website / email / place of
    incorporation) plus the UBI number, so no data is lost by the change.
  * pandas 2.x.  v1.2 ended with writer.save(), removed in pandas 2.0
    (AttributeError: 'OpenpyxlWriter' object has no attribute 'save').
  * scriptfolder resolved per project convention -- v1.2 hard-coded
    C:\\Users\\wuj1\\OneDrive - moodys.com\\... which is the retired tenant.
  * Non-schema 'Check' column dropped from sqldict.
  * Per-row padding.  v1.2 called bourange_same_length_array() once per LIST;
    v1.3 pads after every row, so a missing email/fax cannot shift a column.
  * ISO_HK extended and matched case-insensitively; unmapped countries are
    printed as a loud warning instead of silently becoming None.
  * Licence status honoured -- v1.2 stamped every intermediary 'Regulated';
    the workbooks carry 'Active - Suspended' rows, reported as 'Suspended'.
  * New data captured: UBI number -> InternalID_1, insurer type -> CoType,
    business nature -> License_Type, year of first authorization ->
    RegulationDate.
  * ListLanguage = 'EN' on every row.

NOTE -- counts measured live 2026-08-13:
    list 1  Register of Authorized Insurers                 162
    list 2  List of Licensed Insurance Agencies            1467
    list 3  List of Licensed Insurance Broker Companies     811
  v1.2's last good run had 158 / 1569 / 800.  The agency count really did
  fall; it is not a scraping loss -- the workbook itself has 1467 rows.

REQUIRES a real, non-headless Chrome.  headless Chrome is challenged by
Cloudflare and never clears, so options.headless(False) must stay.
"""

# ------------------------------------------------ Begin_Librairie ----------------------------------------

import base64
import datetime
import io
import json
import os
import re
import sys
import time

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from DrissionPage import ChromiumPage, ChromiumOptions

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# The production console is cp1252.  A print() carrying a Chinese licensee name
# -- from an unmapped-country warning or an exception message -- raises
# UnicodeEncodeError there and kills the run instead of degrading.  Repo
# standard, see DZ BAL/_dryrun_parser.py.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

# ------------------------------------------------ Begin_fileName ----------------------------------------

regulatorName = 'HK IAHK'

print("Running {} Web Scraping Tool v.1.4".format(regulatorName))

now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])
processdate = now.strftime('%Y-%m-%d')

try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))   # production environment (.py)
except NameError:
    scriptfolder = os.getcwd()                                  # notebook environment

os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')

if os.path.exists(tempfolder):
    for rem_file in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem_file))
else:
    os.mkdir(tempfolder)

# ------------------------------------------------ Begin_Varible ----------------------------------------

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

BASE = 'https://www.ia.org.hk'

# List 1 -- the register page is loaded to (a) clear Cloudflare, (b) count the
# on-page anchors as a cross-check on the API row count, and (c) act as the
# origin the browser-side XHR fallback fires from.
INSURERS_PAGE = BASE + '/en/supervision/reg_insurers_lloyd/register_of_authorized_insurers.html'
INSURERS_LIST_API = BASE + '/iareg/insurerlist.php?lang=en'
INSURERS_DETAIL_API = BASE + '/iareg/insurerdetail.php?lang=en&ubi_no={}'

# Lists 2 and 3 -- two workbooks linked off the intermediaries page.  The
# file names carry a month ("LALIA_31July2026.xlsx") so they must be
# discovered from the anchor text, never hard-coded.
INTERMEDIARIES_PAGE = BASE + '/en/supervision/reg_ins_intermediaries/registers_of_insurance_intermediaries.html'
AGENCIES_LINK = 'Download Full List \u2013 Licensed Insurance Agencies'
BROKERS_LINK = 'Download Full List \u2013 Licensed Insurance Broker Companies'

LN_INSURERS = 'Register of Authorized Insurers'
LN_AGENCIES = 'List of Licensed Insurance Agencies'
LN_BROKERS = 'List of Licensed Insurance Broker Companies'

# How long to let Cloudflare's interstitial resolve before giving up.  v1.3
# used a flat 5 s; the production box needs the slack -- it was observed
# still refreshing the challenge when v1.4's first poll ran.
CLEARANCE_TIMEOUT = 120

# Place of incorporation -> ISO code.  Keys are matched case-insensitively;
# 'United Kingdom' -> 'UK' is kept exactly as v1.2 had it (see README).
ISO_HK = {
    'HONG KONG': 'HK', 'BERMUDA': 'BM', 'GERMANY': 'DE',
    'FEDERAL REPUBLIC OF GERMANY': 'DE', 'UNITED STATES OF AMERICA': 'US',
    'SINGAPORE': 'SG', 'CHINA': 'CN', "THE PEOPLE'S REPUBLIC OF CHINA": 'CN',
    'ITALY': 'IT', 'NORWAY': 'NO', 'SPAIN': 'ES', 'LUXEMBOURG': 'LU',
    'UNITED KINGDOM': 'UK', 'CANADA': 'CA', 'FRANCE': 'FR', 'BELGIUM': 'BE',
    'ISLE OF MAN': 'IM', 'INDIA': 'IN', 'SOUTH AFRICA': 'ZA',
    'REPUBLIC OF IRELAND': 'IE', 'IRELAND': 'IE', 'PHILIPPINES': 'PH',
    'JAPAN': 'JP', 'GUERNSEY': 'GG', 'JERSEY': 'JE', 'SWITZERLAND': 'CH',
    'SWEDEN': 'SE', 'DENMARK': 'DK', 'FINLAND': 'FI', 'NETHERLANDS': 'NL',
    'AUSTRIA': 'AT', 'PORTUGAL': 'PT', 'GREECE': 'GR', 'AUSTRALIA': 'AU',
    'NEW ZEALAND': 'NZ', 'MALAYSIA': 'MY', 'THAILAND': 'TH', 'TAIWAN': 'TW',
    'MACAU': 'MO', 'ISRAEL': 'IL', 'BARBADOS': 'BB', 'CAYMAN ISLANDS': 'KY',
    'BRITISH VIRGIN ISLANDS': 'VG', 'REPUBLIC OF KOREA': 'KR',
}

unmapped_countries = set()
liquidation_notes = []

# A synchronous XMLHttpRequest issued from inside the loaded page.  Same
# origin, so it carries the Cloudflare cookie, the browser's own TLS
# handshake and its exact headers -- there is nothing left for Cloudflare to
# tell apart from an ordinary page request, because it is one.
SYNC_XHR_TEXT = """
var xhr = new XMLHttpRequest();
xhr.open('GET', arguments[0], false);
xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
xhr.send(null);
return JSON.stringify({status: xhr.status, body: xhr.responseText});
"""

# Same channel for binary payloads (the two .xlsx workbooks).  The
# charCodeAt & 0xff walk is the standard way to get bytes out of the
# x-user-defined charset intact before base64.
SYNC_XHR_BINARY = """
var xhr = new XMLHttpRequest();
xhr.open('GET', arguments[0], false);
xhr.overrideMimeType('text/plain; charset=x-user-defined');
xhr.send(null);
var s = xhr.responseText, out = '';
for (var i = 0; i < s.length; i++) out += String.fromCharCode(s.charCodeAt(i) & 0xff);
return JSON.stringify({status: xhr.status, b64: btoa(out)});
"""

# ------------------------------------------------ Begin_Fonction ----------------------------------------


def norm(text):
    """Collapse whitespace, drop non-breaking spaces."""
    return re.sub(r'\s+', ' ', (text or '').replace('\xa0', ' ')).strip()


def clean(value):
    """Normalise a JSON / worksheet value into a plain string cell."""
    if value is None:
        return ''
    if isinstance(value, float) and pd.isna(value):
        return ''
    value = norm(str(value))
    if value in ('None', 'nan', 'NaN', 'null', '---', 'N/A'):
        return ''
    return value


def english_part(value):
    """The IA workbooks hold 'English / (TC) / (SC)' in one cell -- keep the English."""
    value = clean(value)
    if not value:
        return ''
    return norm(value.split('/')[0])


def regulation_type(status):
    """Licence Status -> RegulationType.

    The intermediary workbooks use exactly two values per list (measured):
    'Active' and 'Active - Suspended' / 'Active - Suspended (No RO)'.  A
    suspended licensee is still on the register but may not carry on
    regulated activity, so it must not be reported as plain 'Regulated'.
    """
    status = clean(status)
    if not status:
        return 'Regulated'
    if status.lower() == 'active':
        return 'Regulated'
    if 'suspend' in status.lower():
        return 'Suspended'
    return status


def iso_country(place):
    """Place of incorporation -> ISO code, case-insensitive, warn if unknown."""
    place = clean(place)
    if not place:
        return ''
    code = ISO_HK.get(place.upper())
    if code is None:
        unmapped_countries.add(place)
        return ''
    return code


def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict


def append_row(row):
    """Append one record and immediately pad every other column."""
    sqldict['ListProcessDate'].append(processdate)
    for key, value in row.items():
        sqldict[key].append(value)
    bourange_same_length_array(sqldict)


def looks_like_challenge(text):
    """True if this is Cloudflare's interstitial rather than the payload."""
    head = (text or '')[:800].lower()
    return ('just a moment' in head
            or 'cf-browser-verification' in head
            or 'challenge-platform' in head)


def safe_html(page):
    """page.html, or None while the page is mid-navigation.

    The Cloudflare interstitial RELOADS ITSELF while it works, so the DOM root
    object id DrissionPage is holding goes stale under the poll and page.html
    raises

        DrissionPage.errors.ContextLostError:
            The page is refreshed. Please wait until the page is refreshed or loaded.

    which is what killed the first production run of v1.4 (DrissionPage
    4.1.1.2).  That exception is not a failure -- it is precisely what "the
    challenge is still running" looks like from the outside, so it has to be
    caught and treated as "not ready yet".  Catch broadly and on purpose:
    ContextLostError, PageDisconnectedError and ElementLossError all mean the
    same thing here, and their names have moved between DrissionPage versions.
    """
    try:
        page.wait.doc_loaded()
    except Exception:
        return None
    try:
        return page.html
    except Exception:
        return None


def safe_title(page):
    """page.title, or '' while the page is mid-navigation.  See safe_html()."""
    try:
        return page.title or ''
    except Exception:
        return ''


def load_and_clear(page, url):
    """Load a page and wait for Cloudflare to actually let go.

    v1.3 waited a flat 5 seconds.  That is enough on a quiet dev machine and
    not enough on a busy one, and when it is not enough the script does not
    notice -- it carries on and dies later on a bare 403.  Here the wait is a
    poll on the page itself, every read of which is guarded, and running out
    of patience is an explicit, named failure that says what it was stuck on.
    """
    try:
        page.get(url)
    except Exception as err:
        # A refresh during the initial load throws the same way the poll does.
        print('  (initial load raised {} -- polling anyway)'.format(type(err).__name__))

    deadline = time.time() + CLEARANCE_TIMEOUT
    last_seen = 'nothing readable yet'

    while time.time() < deadline:
        html = safe_html(page)
        title = safe_title(page)

        if html and not looks_like_challenge(html) and 'just a moment' not in title.lower():
            page.wait(1)
            settled = safe_html(page)          # re-read once it has settled
            if settled and not looks_like_challenge(settled):
                return settled

        last_seen = 'title={!r}, {} bytes of HTML'.format(
            title[:60], len(html) if html else 0)
        page.wait(2)

    raise RuntimeError(
        'Cloudflare did not release {} within {} s -- last seen: {}.  The '
        'browser is still showing the interstitial.  Check that a REAL '
        'visible Chrome window opened (options.headless(False) must stay), '
        'and watch it: if it is sitting on a "Verify you are human" checkbox '
        'that never ticks itself, the box needs the checkbox clicked by hand '
        'or a longer CLEARANCE_TIMEOUT (currently {} s).'
        .format(url, CLEARANCE_TIMEOUT, last_seen, CLEARANCE_TIMEOUT))


class Channel(object):
    """Reads ia.org.hk over requests when allowed, through the browser when not.

    Cloudflare re-validates cf_clearance against the client it was issued to
    -- User-Agent, TLS handshake fingerprint, egress IP.  A requests.Session
    holding the cookie matches on the first of those and can fail the other
    two, which is exactly what the Windows production box hit while the dev
    Mac did not.  So requests is an optimisation here, never a requirement:
    the moment it is refused, every later call goes through the browser,
    which by construction cannot be told apart from the browser.
    """

    def __init__(self, page, session):
        self.page = page
        self.session = session
        self.mode = 'requests'
        self.switch_reason = ''

    def _run(self, script, url, timeout):
        """run_js, re-anchoring the page once if the context is lost.

        The XHR fires from the register page's origin, so if that page
        navigates or refreshes under us -- Cloudflare re-challenging mid-run,
        for instance -- run_js raises ContextLostError and the remaining calls
        would all die with it.  Reload the origin once and try again before
        giving up.
        """
        try:
            return json.loads(self.page.run_js(script, url, timeout=timeout))
        except Exception as err:
            print('  [!] browser context lost on {} ({}); reloading the origin '
                  'page and retrying once'.format(url, type(err).__name__))
            load_and_clear(self.page, INSURERS_PAGE)
            return json.loads(self.page.run_js(script, url, timeout=timeout))

    def _browser_text(self, url):
        payload = self._run(SYNC_XHR_TEXT, url, 180)
        if payload.get('status') != 200:
            raise RuntimeError('the browser itself got HTTP {} for {}'.format(
                payload.get('status'), url))
        return payload.get('body') or ''

    def _browser_binary(self, url):
        payload = self._run(SYNC_XHR_BINARY, url, 600)
        if payload.get('status') != 200:
            raise RuntimeError('the browser itself got HTTP {} for {}'.format(
                payload.get('status'), url))
        return base64.b64decode(payload.get('b64') or '')

    def _fall_back(self, reason):
        self.mode = 'browser'
        self.switch_reason = reason
        print('  [!] requests was refused ({}).  Switching to browser-side '
              'fetching for the rest of the run.'.format(reason))

    def text(self, url):
        if self.mode == 'requests':
            reason = ''
            try:
                response = self.session.get(url, timeout=120)
                if response.status_code == 200 and not looks_like_challenge(response.text):
                    return response.text
                reason = 'HTTP {}'.format(response.status_code)
                if response.status_code == 200:
                    reason = 'HTTP 200 but a Cloudflare challenge page'
            except Exception as err:
                reason = str(err)[:120]
            self._fall_back(reason)
        return self._browser_text(url)

    def json(self, url):
        body = self.text(url).lstrip()
        if not body.startswith('{'):
            raise RuntimeError('{} did not return JSON.  First 120 bytes: {!r}'.format(
                url, body[:120]))
        return json.loads(body)

    def binary(self, url):
        if self.mode == 'requests':
            reason = ''
            try:
                response = self.session.get(url, timeout=300)
                if response.status_code == 200 and not looks_like_challenge(response.text[:800]):
                    return response.content
                reason = 'HTTP {}'.format(response.status_code)
            except Exception as err:
                reason = str(err)[:120]
            self._fall_back(reason)
        return self._browser_binary(url)


def open_channel(page):
    """Clear Cloudflare, capture both pages, and pick the fastest working transport."""
    print('  loading the register page (a Chrome window will open) ...')
    insurers_html = load_and_clear(page, INSURERS_PAGE)

    print('  loading the intermediaries page ...')
    intermediaries_html = load_and_clear(page, INTERMEDIARIES_PAGE)

    # Both reads can still catch a refresh; neither is worth aborting over.
    # The UA only decorates the requests fast path, and an empty cookie list
    # just means the fast path will be refused and the browser takes over.
    try:
        user_agent = page.run_js('return navigator.userAgent;')
    except Exception:
        user_agent = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36')
        print('  (could not read navigator.userAgent -- using a default)')
    try:
        cookies = page.cookies(all_domains=True)
    except Exception:
        cookies = []
        print('  (could not read cookies -- the browser channel will be used)')
    names = [c['name'] for c in cookies]
    print('  cookies held by the browser: {}'.format(', '.join(names) or '(none)'))

    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': user_agent,
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.9',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': INSURERS_PAGE,
    })
    for cookie in cookies:
        try:
            session.cookies.set(cookie['name'], cookie['value'],
                                domain=cookie.get('domain', '.ia.org.hk'))
        except Exception:
            pass

    channel = Channel(page, session)

    # Probe once, before any real work, so the transport decision is made and
    # printed up front rather than discovered 162 calls in.
    print('  probing {} over requests ...'.format(INSURERS_LIST_API))
    try:
        channel.json(INSURERS_LIST_API)
    except Exception as err:
        # text() has already switched to browser mode if requests was the
        # problem; anything still failing here is a hard stop.
        if channel.mode != 'browser':
            raise
        print('  probe over requests failed: {}'.format(str(err)[:160]))

    print('  transport: {}{}'.format(
        channel.mode,
        '' if channel.mode == 'requests' else ' (requests refused: {})'.format(channel.switch_reason)))

    return channel, insurers_html, intermediaries_html


# ------------------------------------------------ Begin_Main ----------------------------------------

print('\n[INFO] : clearing Cloudflare with a visible browser ...')

options = ChromiumOptions().auto_port()
options.headless(False)          # DELIBERATE -- headless never clears the challenge
page = ChromiumPage(options)

try:
    channel, insurers_html, intermediaries_html = open_channel(page)

    # -----------------------------------------------------------------------
    # List 1 -- Register of Authorized Insurers
    # -----------------------------------------------------------------------

    print('\n[INFO] : Working 1/3 _(HK IAHK 1)_  {}'.format(LN_INSURERS))

    # Cross-check: the register page renders one anchor per insurer across its
    # 22 alphabetical tables.  If the API and the page disagree, say so loudly --
    # the delivered row count has to match what a human counts on the site.
    page_names = [norm(a.get_text()) for a in
                  BeautifulSoup(insurers_html, 'html.parser').select('table a[href]')]
    page_names = [n for n in page_names if n]

    payload = channel.json(INSURERS_LIST_API)
    insurers = [entity for letter in payload['data'].values() for entity in letter]
    print('  page anchors {} / API rows {}'.format(len(page_names), len(insurers)))
    if len(page_names) != len(insurers):
        print('  !! MISMATCH between the register page and the API -- check the site before delivering')

    for position, entity in enumerate(insurers, 1):
        ubi = clean(entity.get('ubi_no'))
        detail = channel.json(INSURERS_DETAIL_API.format(ubi)).get('data') or {}

        business_nature = '; '.join(clean(x) for x in (detail.get('en_business_nature')
                                                       or entity.get('en_business_nature') or []) if clean(x))
        insurer_type = clean(detail.get('en_insurer_type')) or clean(entity.get('en_insurer_type'))
        auth_year = clean(detail.get('auth_year')) or clean(entity.get('auth_year'))

        # 2-3 insurers carry a provisional-liquidation / winding-up date but are
        # still on the register.  They are reported at the end of the run rather
        # than written into CancellationDate, which would read as "licence
        # cancelled" -- see the README, this one is open for confirmation.
        liquid = clean(entity.get('liquid_date'))
        windup = clean(entity.get('windup_date'))
        if liquid or windup:
            liquidation_notes.append((clean(entity.get('en_name')), liquid, windup))

        append_row({
            'Name': clean(detail.get('en_name')) or clean(entity.get('en_name')),
            'InternalID_1': ubi,
            'InternalID_1_type': 'Unique Business Identifier' if ubi else '',
            'CoType': insurer_type,
            'License_Type': business_nature,
            'Address_1': clean(detail.get('en_address')),
            'Cntry': iso_country(detail.get('en_poi') or entity.get('en_poi')),
            'Phone': clean(detail.get('tel')),
            'Fax': clean(detail.get('fax')),
            'Website': clean(detail.get('website')),
            'Email': clean(detail.get('email')),
            'RegulationType': 'Regulated',
            'RegulationDate': auth_year,
            'RegCtry': 'HK',
            'RegCode': 'IAHK',
            'ListCode': '1',
            'ListName': LN_INSURERS,
            'ListLanguage': 'EN',
        })

        if position % 25 == 0 or position == len(insurers):
            print('    {}/{} insurer detail pages read'.format(position, len(insurers)))

    print('  [1] {:<50} {:>5} rows'.format(LN_INSURERS, len(insurers)))

    # -----------------------------------------------------------------------
    # Lists 2 and 3 -- licensed insurance agencies / broker companies
    # -----------------------------------------------------------------------

    soup = BeautifulSoup(intermediaries_html, 'html.parser')
    workbook_urls = {}
    for anchor in soup.select('a[href]'):
        label = norm(anchor.get_text())
        for wanted in (AGENCIES_LINK, BROKERS_LINK):
            # compare on the ASCII-folded label so an en-dash / hyphen swap on the
            # site cannot break the match
            if label.replace('\u2013', '-') == wanted.replace('\u2013', '-'):
                workbook_urls[wanted] = urljoin(INTERMEDIARIES_PAGE, anchor['href'])

    for list_code, link_text, list_name in ((2, AGENCIES_LINK, LN_AGENCIES),
                                            (3, BROKERS_LINK, LN_BROKERS)):
        print('\n[INFO] : Working {}/3 _(HK IAHK {})_  {}'.format(list_code, list_code, list_name))

        url = workbook_urls.get(link_text)
        if url is None:
            raise RuntimeError('the "{}" link is gone from {}'.format(link_text, INTERMEDIARIES_PAGE))
        print('  workbook: {}'.format(url))

        content = channel.binary(url)
        tempdf = pd.read_excel(io.BytesIO(content))

        columns = {c: norm(c) for c in tempdf.columns}

        def column(prefix):
            """Columns are trilingual headers -- match on the English prefix."""
            for original, text in columns.items():
                if text.lower().startswith(prefix.lower()):
                    return original
            raise KeyError('no column starting with {!r} in {}'.format(prefix, list(columns.values())))

        col_licence = column('Licence No.')
        col_name = column('English Name')
        col_business = column('Line(s) of Business')
        col_status = column('Licence Status')

        statuses = {}
        for _, record in tempdf.iterrows():
            name = clean(record[col_name])
            if not name:
                continue
            status = english_part(record[col_status])
            statuses[status] = statuses.get(status, 0) + 1

            append_row({
                'Name': name,
                'InternalID_1': clean(record[col_licence]),
                'InternalID_1_type': 'Licence No.',
                'License_Type': english_part(record[col_business]),
                'RegulationType': regulation_type(status),
                'RegCtry': 'HK',
                'RegCode': 'IAHK',
                'ListCode': str(list_code),
                'ListName': list_name,
                'ListLanguage': 'EN',
            })

        print('  workbook rows {} -- licence statuses seen: {}'.format(
            len(tempdf), {k: statuses[k] for k in sorted(statuses)}))
        print('  [{}] {:<50} {:>5} rows'.format(list_code, list_name, len(tempdf)))

finally:
    # The browser is the fallback transport, so unlike v1.3 it has to survive
    # the whole run -- but it must not survive the process.
    try:
        page.quit()
    except Exception:
        pass

# ------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('\nSaved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))

print('\nRows per list:')
summary = df.groupby(['ListCode', 'ListName', 'RegulationType']).size().rename('rows').reset_index()
summary['ListCode'] = summary['ListCode'].astype(int)
print(summary.sort_values('ListCode').to_string(index=False))

print('\nTransport used: {}{}'.format(
    channel.mode,
    '' if channel.mode == 'requests' else ' (requests refused: {})'.format(channel.switch_reason)))

if liquidation_notes:
    print('\n[NOTE] {} insurer(s) on the register carry a provisional liquidation /'
          ' winding up date. They are written as Regulated with an empty'
          ' CancellationDate -- confirm how you want them treated:'.format(len(liquidation_notes)))
    for name, liquid, windup in liquidation_notes:
        print('   {:<55} liquidation={!r} winding-up={!r}'.format(name[:55], liquid, windup))

if unmapped_countries:
    print('\n!! {} place(s) of incorporation are not in ISO_HK and were left blank:'.format(len(unmapped_countries)))
    for place in sorted(unmapped_countries):
        print('   {!r}'.format(place))
