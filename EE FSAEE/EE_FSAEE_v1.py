#------------------------------------------------ Begin_Librairie ----------------------------------------
from bs4 import BeautifulSoup
import datetime, os, re
from time import sleep
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
# NB: the current site's entity detail pages no longer carry per-entity address/registry/phone
# tables (they show only the regulator's own contact block), so only Name + list membership is
# extractable today. RegCtry/Cntry left as EE / blank accordingly.
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
        resp = session.get(f"{base}?page={page}", timeout=30, allow_redirects=True)
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
                entities.append(name)
        if got == 0:
            break
        page += 1
        sleep(0.15)
        if page > 50:   # backstop; no list approaches this
            print(f"  list {nr}: page backstop hit")
            break
    print(f"list {nr:>2}: {len(entities):>4} entities | {list_name}")

    for name in sorted(entities, key=str.casefold):
        sqldict['ListProcessDate'].append(processdate)
        sqldict['Name'].append(name)
        sqldict['ListCode'].append(str(nr))
        sqldict['ListName'].append(list_name)
        sqldict['RegulationType'].append('Regulated')
        sqldict['RegCtry'].append('EE')
        sqldict['RegCode'].append('FSAEE')
        sqldict = bourange_same_length_array(sqldict)

#------------------------------------------------ Begin_writer and save df to excel ----------------------------------------
df = pd.DataFrame(sqldict)
df.to_excel(os.path.join(scriptfolder, filename), sheet_name='SQL Ready', index=False)

    