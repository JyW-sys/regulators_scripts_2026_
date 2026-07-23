#------------------------------------------------ Begin_Librairie ----------------------------------------
from bs4 import BeautifulSoup
import datetime, os, re
from time import sleep
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import requests

#------------------------------------------------ Begin_fileName ----------------------------------------
regulatorName = 'EE FSAEE'   # Estonia - Finantsinspektsioon (Estonian Financial Supervision Authority)
print(f"Running {regulatorName} Web Scraping Tool v.2.0")

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')
if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

#------------------------------------------------ Begin_Fonction ----------------------------------------
def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict

def follow_meta_refresh(session, resp):
    # fi.ee uses HTML <meta http-equiv="refresh"> for some old category URLs;
    # requests follows HTTP redirects but not meta-refresh, so do one hop here.
    m = re.search(r'http-equiv="refresh"[^>]*url=\'?([^\'">]+)', resp.text, re.I)
    if m:
        target = m.group(1).replace('&amp;', '&')
        if not target.startswith('http'):
            target = 'https://www.fi.ee' + target
        return session.get(target, timeout=30, allow_redirects=True)
    return resp

def polite_get(url, tries=6, **kw):
    # fi.ee rate-limits bursts with HTTP 429; back off (honouring Retry-After) and retry.
    kw.setdefault('timeout', 30)
    kw.setdefault('allow_redirects', True)
    delay = 3.0
    resp = None
    for _ in range(tries):
        resp = session.get(url, **kw)
        if resp.status_code == 429 or resp.status_code >= 500:
            wait = delay
            try:
                wait = float(resp.headers.get('Retry-After', delay))
            except ValueError:
                pass
            sleep(min(wait, 30))
            delay = min(delay * 2, 30)
            continue
        return resp
    return resp

def parse_address(addr):
    # fi.ee Address is comma-separated "street, city, district, county, zip, country"
    # for domestic entities, and just a bare "country" for cross-border foreign ones.
    out = {'Address_1': '', 'City': '', 'Zip': '', 'Cntry': ''}
    parts = [p.strip() for p in (addr or '').split(',') if p.strip()]
    if not parts:
        return out
    if len(parts) == 1:                       # cross-border: country only
        out['Cntry'] = parts[0]
        return out
    out['Cntry'] = parts[-1]
    out['Address_1'] = parts[0]
    out['City'] = parts[1]
    for p in parts:                           # postal code = a 4-6 digit chunk
        if re.fullmatch(r'\d{4,6}', p.replace(' ', '')):
            out['Zip'] = p
            break
    return out

def fetch_entity_details(href):
    # Each list entry links to a www.fi.ee detail page whose <article> embeds an
    # <iframe src="https://subjektid.fi.ee/view/{id}/{TYPE}"> holding the real per-entity
    # data as <tr class="table-subtype-row"><td>label</td><td>value</td></tr> rows.
    # Branch lists repeat Address/Phone/etc. in a later home-state table, so first-
    # occurrence-wins keeps the entity's own block. Returns {} on any failure.
    out = {}
    try:
        url = href if href.startswith('http') else 'https://www.fi.ee' + href
        resp = polite_get(url)
        resp = follow_meta_refresh(session, resp)
        soup = BeautifulSoup(resp.text, 'lxml')
        iframe = soup.select_one('article iframe#subject-data') or soup.select_one('article iframe')
        src = iframe.get('src') if iframe else None
        if not src:
            return out
        r2 = polite_get(src)
        s2 = BeautifulSoup(r2.text, 'lxml')
        data = {}
        for tr in s2.select('tr.table-subtype-row'):
            tds = tr.find_all('td')
            if len(tds) >= 2:
                label = tds[0].get_text(' ', strip=True)
                if label and label not in data:        # first occurrence wins
                    data[label] = tds[1].get_text(' ', strip=True)
        out['reg_no'] = data.get('Commercial Registry Number', '')
        out['Phone'] = data.get('Phone', '')
        out['Email'] = data.get('E-mail', '')
        out['Website'] = data.get('Web Address', '')
        out.update(parse_address(data.get('Address', '')))
    except Exception as e:
        print(f"    detail fetch failed for {href}: {e}")
    return out

#------------------------------------------------ Begin_Variable ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': []}

# Authoritative per-list category URLs (from the prior scraper's regdict). The ticket skips
# ListNr 3 ("Representative offices of foreign credit institutions"). Some paths 301/meta-refresh
# to a deeper current path; both are handled. Active set (no ?closed=1) per project decision.
# Per-entity address/registry-number/phone/email/website come from the subjektid.fi.ee iframe
# embedded in each detail page (see fetch_entity_details). Domestic entities expose the full set;
# cross-border foreign providers expose only Corporate Name + a country-level Address. fi.ee
# publishes no LEI, so LEI Code is left blank.
REG = {
 1:  ("/en/banking-and-credit/banking-and-credit/credit-institutions/licensed-credit-institutions-estonia", "Licensed Credit Institutions in Estonia"),
 2:  ("/en/banking-and-credit/credit-institutions/affiliated-branches-foreign-credit-institutions", "Affiliated Branches of Foreign Credit Institutions"),
 4:  ("/en/banking-and-credit/banking-and-credit/credit-institutions/providers-cross-border-banking-services", "Providers of cross-border banking services"),
 5:  ("/en/insurance-0/insurance/insurance-companies/licenced-life-insurance-companies-estonia", "Licenced Life Insurance Companies in Estonia"),
 6:  ("/en/insurance-0/insurance/insurance-companies/licenced-non-life-insurance-companies-estonia", "Licenced Non-Life Insurance Companies in Estonia"),
 7:  ("/en/insurance-0/insurance/insurance-companies/affiliated-branches-foreign-life-insurance-institutions", "Affiliated Branches of Foreign Life Insurance Institutions"),
 8:  ("/en/insurance-0/insurance/insurance-companies/affiliated-branches-foreign-non-life-insurance-institutions", "Affiliated branches of foreign non-life insurance institutions"),
 9:  ("/en/insurance/insurance-companies/insurance-0/providers-cross-border-life-insurance-services", "Providers of cross-border life insurance services"),
 10: ("/en/insurance/insurance-companies/insurance-0/providers-cross-border-non-life-insurance-services", "Providers of cross-border non-life insurance services"),
 11: ("/en/investment-market/licenced-fund-management-companies", "List of Fund Management Companies"),
 12: ("/en/investment-market/cross-border-fund-management-companies", "Cross-border Fund Management Companies"),
 13: ("/en/investment-market/licenced-investment-firms-estonia", "Investment Firms"),
 14: ("/en/investment-market/providers-cross-border-investment-services", "Providers of cross-border investment services"),
 15: ("/en/payment-services/e-money-institutions/providers-cross-border-e-money-services", "Providers of Cross-border E-money Services"),
 16: ("/en/payment-services/payment-institutions/estonian-payment-institutions", "Estonian payment institutions"),
 17: ("/en/payment-services/payment-institutions/payment-services/providers-cross-border-payment-sevices", "Providers of Cross-border Payment Services"),
}

#------------------------------------------------ Begin_Main ----------------------------------------
session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

for nr, (path, list_name) in REG.items():
    base = "https://www.fi.ee" + path
    seen = set()
    entities = []
    page = 0
    while True:
        resp = polite_get(f"{base}?page={page}")
        resp = follow_meta_refresh(session, resp)
        if resp.status_code == 404:
            break   # fi.ee returns 404 for a page index past the last page = end of list
        if resp.status_code != 200:
            print(f"  list {nr} page {page}: unexpected HTTP {resp.status_code}, stopping")
            break
        soup = BeautifulSoup(resp.text, "lxml")
        got = 0
        for a in soup.select(".views-field-title a"):
            got += 1
            name = a.get_text(strip=True)
            href = a.get("href") or ""
            key = (name, href)
            if name and key not in seen:
                seen.add(key)
                entities.append((name, href))
        if got == 0:
            break
        page += 1
        sleep(0.15)
        if page > 50:   # backstop; no list approaches this
            print(f"  list {nr}: page backstop hit")
            break
    print(f"list {nr:>2}: {len(entities):>4} entities | {list_name}")

    # Visit each entity's detail-page iframe to pull address / registry no / phone / email / website.
    entities = sorted(entities, key=lambda nh: nh[0].casefold())
    with ThreadPoolExecutor(max_workers=4) as ex:
        details = list(ex.map(lambda nh: fetch_entity_details(nh[1]), entities))
    enriched = sum(1 for d in details if d.get('Address_1') or d.get('Cntry'))
    print(f"         enriched {enriched}/{len(entities)}")

    for (name, _href), d in zip(entities, details):
        sqldict['ListProcessDate'].append(processdate)
        sqldict['Name'].append(name)
        sqldict['ListCode'].append(str(nr))
        sqldict['ListName'].append(list_name)
        sqldict['ListLanguage'].append('EN')
        sqldict['RegulationType'].append('Regulated')
        sqldict['RegCtry'].append('EE')
        sqldict['RegCode'].append('FSAEE')
        sqldict['InternalID_1'].append(d.get('reg_no', ''))
        sqldict['InternalID_1_type'].append('Commercial Registry Number' if d.get('reg_no') else '')
        sqldict['Address_1'].append(d.get('Address_1', ''))
        sqldict['City'].append(d.get('City', ''))
        sqldict['Zip'].append(d.get('Zip', ''))
        sqldict['Cntry'].append(d.get('Cntry', ''))
        sqldict['Phone'].append(d.get('Phone', ''))
        sqldict['Email'].append(d.get('Email', ''))
        sqldict['Website'].append(d.get('Website', ''))
        sqldict = bourange_same_length_array(sqldict)

#------------------------------------------------ Begin_writer and save df to excel ----------------------------------------
df = pd.DataFrame(sqldict)
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)
print(f"\nSaved {len(df)} rows -> {filename}")
