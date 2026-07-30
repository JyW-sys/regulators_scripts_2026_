#------------------------------------------------ Begin_Librairie ----------------------------------------
# US FCA - Farm Credit Administration, FCS Institution Directory
# v4 (2026-07-30) : DrissionPage / Chrome transport.  v3 used requests + a raw-socket
# preflight and aborted on the control server with socket.timeout on apps.fca.gov:443.
#
# WHY CHROME MIGHT SUCCEED WHERE THE RAW SOCKET FAILED
# socket.create_connection() always goes DIRECT.  Chrome follows the Windows system
# proxy / PAC script, and on a corporate control box those are frequently the only
# route off the network.  So a socket timeout does NOT prove Chrome is blocked too -
# it only proves the direct path is.  preflight() below now probes BOTH and prints
# each result, so the two cases can be told apart from the log alone:
#
#   socket blocked + Chrome OK       -> proxy-only network, v4 fixes it
#   socket blocked + Chrome blocked  -> no route to 4.79.206.0/24, needs a US VPN
#
# There is still no code-side workaround for a genuinely dropped handshake.

import os
import re
import socket
import datetime
from time import sleep

import pandas as pd
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

#------------------------------------------------ Begin_fileName ----------------------------------------
regulatorName = 'US FCA'

print('Running {} Web Scraping Tool v.4.0 (DrissionPage)'.format(regulatorName))

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

# ------ At first we will define the workspace path -----
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## production environment (.py)
except NameError:
    scriptfolder = os.getcwd()  ## notebook environment

os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

#------------------------------------------------ Begin_chromedriver ----------------------------------------
BASE = 'https://apps.fca.gov/FCSPublicDirectory/'
SEARCH_URL = BASE + 'PubSearchInstitution.aspx'

GRID_ID = 'ctl00_cphMainContent_gvInstitutions'
GRID_SEL = '#' + GRID_ID
DETAIL_SEL = 'span[id$="lblUninum"]'

# Escape hatches for the control server, set as environment variables - no code edit needed.
#   US_FCA_PROXY=http://host:port  -> hand Chrome an explicit proxy. Use this if Chrome
#                                     normally reaches the internet through a corporate
#                                     proxy that this clean automation profile does not
#                                     inherit. This is the single most likely fix if the
#                                     socket is blocked but a normal Chrome window works.
#   US_FCA_HEADLESS=1              -> run headless, for an unattended/service session with
#                                     no interactive desktop.
PROXY = os.environ.get('US_FCA_PROXY', '').strip()
HEADLESS = os.environ.get('US_FCA_HEADLESS', '').strip() in ('1', 'true', 'True', 'yes')

options = ChromiumOptions()
options.auto_port()                     # never collide with the operator's own Chrome
options.set_download_path(tempfolder)
options.set_argument('--ignore-certificate-errors')   # corporate TLS proxy
options.set_argument('--disable-blink-features=AutomationControlled')
if PROXY:
    options.set_argument('--proxy-server={}'.format(PROXY))
    print('[INFO] : - Chrome proxy : {}'.format(PROXY))
if HEADLESS:
    options.headless(True)
    print('[INFO] : - Chrome headless mode')

driver = ChromiumPage(options)
# A page-load timeout is mandatory, not a nicety: a silently dropped handshake never
# fires a load event, so an un-timed page.get() blocks in a socket read indefinitely
# instead of surfacing as an error the retry loop can act on.
driver.set.timeouts(base=10, page_load=60, script=30)


def tcp_probe(host, port=443, timeout=15):
    """Direct-path reachability. INFORMATIONAL ONLY - Chrome may still get through a proxy."""
    try:
        socket.create_connection((host, port), timeout=timeout).close()
        return True
    except OSError:
        return False


def has_ele(selector):
    """True when the selector is present in the currently loaded document."""
    try:
        return bool(driver.s_ele('css:{}'.format(selector)))
    except Exception:
        return False


def load_html(url, selector=None, tries=3, settle=1.0):
    """Navigate and return the rendered HTML, or '' if every attempt failed.

    A non-empty document is NOT the success condition. Chrome answers an unreachable host
    with its own error page, which is perfectly valid non-empty HTML - accepting it would
    parse into a row of blank fields and look like a successful scrape. When a selector is
    given, its presence is the success condition.
    """
    for attempt in range(1, tries + 1):
        try:
            # retry=0 : we run our own retry loop, and a hung load must surface as a
            # return value rather than an indefinite block.
            driver.get(url, retry=0, timeout=60)
        except Exception as exc:
            print('[WARN] : - page.get failed {}/{} on {} ({}: {})'
                  .format(attempt, tries, url, type(exc).__name__, str(exc)[:120]))
            sleep(5)
            continue

        if selector:
            try:
                driver.wait.ele_displayed('css:{}'.format(selector), timeout=25)
            except Exception:
                pass          # fall through - the content check below is what decides

        sleep(settle)
        html = driver.html or ''

        if html.strip() and (selector is None or has_ele(selector)):
            return html

        print('[WARN] : - attempt {}/{} on {} returned {} bytes without "{}" '
              '(Chrome error page or interstitial, not the register)'
              .format(attempt, tries, url, len(html), selector or 'content'))
        sleep(5)
    return ''


def preflight():
    """Fail loudly and specifically when the FCA origin is unreachable.

    Without this the scraper would emit a 0-row workbook that looks like a clean run.
    """
    direct = tcp_probe('apps.fca.gov')
    print('[INFO] : - direct TCP apps.fca.gov:443 : {}'
          .format('open' if direct else 'BLOCKED (timeout)'))

    html = load_html(SEARCH_URL, selector=GRID_SEL)
    reached = bool(html.strip())
    grid_ok = GRID_ID in html
    print('[INFO] : - Chrome page load           : {}'
          .format('OK' if reached else 'BLOCKED'))

    if reached and grid_ok:
        if not direct:
            print('[INFO] : - direct socket is blocked but Chrome is through, so this network '
                  'reaches\n           the FCA origin only via the system proxy / PAC. Expected '
                  'on the control server.')
        print('[INFO] : - preflight OK, apps.fca.gov is reachable')
        return html

    if reached and not grid_ok:
        raise Exception(
            '\n[ERROR] : - Chrome loaded a page from apps.fca.gov but the institution grid\n'
            '            #{} is not in it. The network is fine;\n'
            '            the markup changed, or an interstitial was served. Nothing written.'
            .format(GRID_ID))

    raise Exception(
        '\n[BLOCKED] : - Chrome could not load {}\n'
        '            direct TCP : {}\n'
        '            via Chrome : BLOCKED\n'
        '\n'
        '            Both paths are dead, so this machine has no route to the FCA origin\n'
        '            network (4.79.206.0/24). It is geo-restricted to the US and silently\n'
        '            drops foreign handshakes. www.fca.gov answering is not a counter-\n'
        '            example - that hostname is served by Cloudflare, the origin is not.\n'
        '\n'
        '            Try, in order:\n'
        '              1. set US_FCA_PROXY=http://<host>:<port> if a normal Chrome window\n'
        '                 on this machine can open the URL above - the automation profile\n'
        '                 does not inherit a per-profile or extension-based proxy;\n'
        '              2. re-run on a US VPN.\n'
        '            No output file has been written.'
        .format(SEARCH_URL, 'open' if direct else 'BLOCKED (timeout)'))


#------------------------------------------------ Begin_Dictionnary ----------------------------------------
# ListLabel : 1 = bank, 2 = insurance, 3 = bank & insurance, 4 = everything else.
# The Farm Credit System is a network of lending banks and agricultural credit
# associations, so the whole list is 1.
ListLabel = {'US FCA 1': 1}

Typology = {'US FCA 1': 'List of "Farm Credit System Institutions"'}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
          'Phone - Mother company': []}

#------------------------------------------------ Begin_Fonction ----------------------------------------

def bourange_same_length_array(sqldict):
    """Pad every column of sqldict out to the length of ListProcessDate."""
    maxlen = len(sqldict['ListProcessDate'])
    for key, val in sqldict.items():
        if len(sqldict[key]) != maxlen:
            empty = []
            total_empty = maxlen - len(sqldict[key])
            for i in range(total_empty):
                empty.append('')
            sqldict[key] = sqldict[key] + empty
    return sqldict


def clean(text):
    if text is None:
        return ''
    return ' '.join(str(text).split()).strip()


# Grid columns are located by header text, not by index - same reason the detail page is read
# by span id. A column inserted upstream would otherwise shift every field silently.
GRID_COLS = {
    'uninum':   'uninum',
    'name':     'institution name',
    'district': 'district',
    'state':    'hq state',
    'ceo':      'ceo',
    'rssd':     'rssd',
}


def parse_grid(soup):
    """Rows of the institution grid -> [{'name', 'uninum', 'district', 'state', 'ceo',
    'rssd', 'href'}].

    The grid is a single page - there is no pager - so a pager guard below asserts that
    assumption instead of trusting it.
    """
    grid = soup.find(id=GRID_ID)
    if grid is None:
        raise Exception('[ERROR] : - grid #{} not found. '
                        'Either the page was blocked, or the directory markup changed.'
                        .format(GRID_ID))

    pager = [a for a in grid.find_all('a', href=True) if 'Page$' in a['href']]
    if pager:
        raise Exception('[ERROR] : - the grid is now paginated ({} pager links). This scraper '
                        'assumes a single page and would silently truncate.'.format(len(pager)))

    header = [clean(c.get_text()).lower() for c in grid.find('tr').find_all(['th', 'td'])]
    idx = {}
    for key, label in GRID_COLS.items():
        if label not in header:
            raise Exception('[ERROR] : - grid column "{}" is gone. Header is now: {}'
                            .format(label, header))
        idx[key] = header.index(label)

    out = []
    for tr in grid.find_all('tr'):
        link = tr.find('a', href=lambda h: h and 'PubViewInst.aspx' in h)
        if link is None:
            continue  # header / sort row
        tds = tr.find_all('td')
        rec = {key: clean(tds[pos].get_text()) if pos < len(tds) else ''
               for key, pos in idx.items()}
        rec['name'] = clean(link.get_text())          # the cell holds the anchor
        rec['href'] = BASE + link['href'].lstrip('/')
        out.append(rec)

    if not out:
        raise Exception('[ERROR] : - grid found but produced 0 institutions.')
    return out


# The detail page carries every value in a <span> whose id ends in a stable field name.
# v1 read them by row position (maintable[0]..maintable[6]), which breaks the moment FCA
# inserts or reorders a row - and breaks silently, shifting every field by one.
FIELD_IDS = {
    'uninum':      'lblUninum',
    'short_name':  'lblShortName',
    'status':      'lblStatusAndDesc',
    'phone':       'lblPhone',
    'rssd':        'lblRSSD',
    'ceo':         'lblCEO',
    'chairman':    'lblChairman',
    'address':     'lblCharterAddress',
    'county':      'lblCharterCounty',
    'website':     'hlWebURL',
    'official':    'lblInstName',
    'charterdate': 'lblCharterDate',
    'charternum':  'lblCharterNumber',
}


def parse_detail(soup):
    """Read the institution profile by span-id suffix, never by row position."""
    rec = {}
    for key, suffix in FIELD_IDS.items():
        el = soup.find(id=lambda i, s=suffix: bool(i) and i.endswith(s))
        if el is None:
            rec[key] = ''
            continue
        if key == 'address':
            # '30 E. 7th Street, Suite 700<br/>St. Paul, MN 55101-1810<br/>'
            rec[key] = [clean(p) for p in el.get_text('\n').split('\n') if clean(p)]
        elif key == 'website':
            rec[key] = clean(el.get('href') or el.get_text())
        else:
            rec[key] = clean(el.get_text())
    return rec


US_TAIL = re.compile(r'^(.*?),\s*([A-Z]{2})\s+([0-9]{5}(?:-[0-9]{4})?)\s*$')


def split_address(lines):
    """['30 E. 7th Street, Suite 700', 'St. Paul, MN 55101-1810']
       -> ('30 E. 7th Street, Suite 700', 'St. Paul', 'MN', '55101-1810')"""
    if not lines:
        return '', '', '', ''
    if len(lines) == 1:
        return lines[0], '', '', ''

    street = ', '.join(lines[:-1])
    tail = lines[-1]

    m = US_TAIL.match(tail)
    if m:
        return street, m.group(1).strip(), m.group(2), m.group(3)

    # no recognisable "City, ST ZIP" - keep the whole line as the city rather than
    # inventing a split
    return street, tail, '', ''


def usdate(text):
    """FCA publishes charter dates as m/d/yyyy."""
    text = clean(text)
    if not text:
        return ''
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(text, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return text


#------------------------------------------------ Begin_Main ----------------------------------------
try:
    grid_html = preflight()          # returns the search page it already loaded

    reg = 'US FCA 1'
    listcode = '1'

    print('[INFO] : - loading the institution grid')
    institutions = parse_grid(BeautifulSoup(grid_html, 'html.parser'))
    print('[INFO] : - {} institutions in the directory'.format(len(institutions)))

    statuses = {}

    for num, inst in enumerate(institutions, start=1):

        if num % 10 == 0 or num == len(institutions):
            print('[INFO] : - detail {}/{}'.format(num, len(institutions)))

        detail_html = load_html(inst['href'], selector=DETAIL_SEL)
        if not detail_html.strip():
            raise Exception('[ERROR] : - detail page unreachable after 3 tries at {}/{} : {}\n'
                            '            Aborting rather than writing a short file.'
                            .format(num, len(institutions), inst['href']))

        detail = parse_detail(BeautifulSoup(detail_html, 'html.parser'))

        street, city, state, zipcode = split_address(detail.get('address') or [])

        status = detail.get('status', '')
        statuses[status] = statuses.get(status, 0) + 1

        sqldict['Name'].append(inst['name'])
        sqldict['EntryType'].append(detail.get('short_name', ''))
        sqldict['Typology'].append(inst['district'])
        sqldict['License_Type'].append(status)

        sqldict['InternalID_1'].append(detail.get('uninum') or inst['uninum'])
        sqldict['InternalID_1_type'].append('FCA Institution Number')
        sqldict['InternalID_2'].append(detail.get('rssd') or inst['rssd'])
        sqldict['InternalID_2_type'].append('RSSD Number')
        sqldict['InternalID_3'].append(detail.get('charternum', ''))
        sqldict['InternalID_3_type'].append('Charter Number')

        sqldict['Address_1'].append(street)
        sqldict['Address_2'].append(state or inst['state'])
        sqldict['City'].append(city)
        sqldict['Zip'].append(zipcode)
        sqldict['Cntry'].append('US')          # v1 wrote the US *state* into Cntry - fixed
        sqldict['Phone'].append(detail.get('phone', ''))
        sqldict['Website'].append(detail.get('website', ''))

        sqldict['Name - Mother Company'].append(detail.get('official', ''))
        sqldict['RegulationDate'].append(usdate(detail.get('charterdate', '')))

        sqldict['RegulationType'].append('Regulated')
        sqldict['RegCtry'].append('US')
        sqldict['RegCode'].append('FCA')
        sqldict['ListCode'].append(listcode)
        sqldict['ListName'].append(Typology[reg])
        sqldict['ListLabel'].append(ListLabel[reg])
        sqldict['ListLanguage'].append('EN')
        sqldict['ListProcessDate'].append(processdate)

        sqldict = bourange_same_length_array(sqldict)

    # The directory is a positive register, so every row is emitted as 'Regulated'. If FCA ever
    # starts publishing non-active institutions here, that is a mapping decision for the ticket
    # owner rather than something to guess at - so surface it instead of burying it.
    non_active = {k: v for k, v in statuses.items() if not k.lower().startswith('active')}
    if non_active:
        print('[WARN] : - non-Active statuses present, all still emitted as RegulationType='
              "'Regulated' : {}".format(non_active))

finally:
    try:
        driver.quit()
    except Exception:
        pass

#------------------------------------------------ Begin_writer and save df to excel ----------------------------------------
os.chdir(scriptfolder)

df = pd.DataFrame(sqldict)

df = df[df['Name'] != '']
df = df.drop_duplicates(subset=['Name', 'ListCode'], keep='first')
df = df.reset_index(drop=True)

# Refuse to write an empty workbook. A 0-row file looks like a successful run to whoever
# picks it up next - that is precisely how ES BES v1.2 shipped nothing for months.
if len(df) == 0:
    raise Exception('[ERROR] : - 0 rows collected, no file written. The scrape did not '
                    'complete - check the cells above for the blocking error.')

df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

print('Saved {} rows to {}'.format(len(df), os.path.join(scriptfolder, filename)))
print(df.groupby('ListCode').size())
