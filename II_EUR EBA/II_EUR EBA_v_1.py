#------------------------------------------------ Begin_Librairie ----------------------------------------
import requests
import json
import zipfile
import os
import datetime
import pandas as pd
from time import sleep

#------------------------------------------------ Begin_ fileName ----------------------------------------
regulatorName = 'II_EUR EBA'  ## change to current controller name

print(f"Running {regulatorName} Web Scraping Tool v.1.0")
now = datetime.datetime.now()
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":", ".")[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"
# scriptfolder = os.path.dirname(os.path.abspath(__file__))  ## to decomment for the production environment
os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')  # the PIR golden-copy zip is downloaded here

if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        try:
            os.remove(os.path.join(tempfolder, rem))
        except OSError:
            pass
else:
    os.mkdir(tempfolder)

#------------------------------------------------ Begin_Session ----------------------------------------
# EUCLID exposes JSON over plain HTTP, so no Selenium/browser is needed.
#   - CIR (credit institutions): POST /register/api/search/entities  (full set per EntityType, no paging)
#   - PIR (payment institutions): GET  /register/api/filemetadata -> golden-copy zip -> json
BASE = "https://euclid.eba.europa.eu/register"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
session = requests.Session()
session.headers.update({"User-Agent": UA, "Accept": "application/json, text/plain, */*"})

#------------------------------------------------ Begin_Variable ----------------------------------------
sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': [], 'Check': []}

processdate = now.strftime('%Y-%m-%d')

# ListCode 1 = Credit Institutions Register (CIR). EUCLIDMD holds exactly these three EntityTypes.
CIR_TYPES = {
    'CRD_CRE_INS': 'CRD Credit Institution',
    'CRD_EEA_BRA': 'EEA Branch',
    'CRD_NON_EEA_BRA': 'Non-EEA Branch',
}

# ListCode 2 = Payment Institutions Register (PIR / PSDMD). Branches (PSD_BR) and agents (PSD_AG)
# are excluded as in the original scraper; everything else is a kept entity type.
PIR_TYPES = {
    'PSD_PI': 'Payment Institution',
    'PSD_EPI': 'Exempted Payment Institution',
    'PSD_EMI': 'Electronic Money Institution',
    'PSD_EEMI': 'Exempted Electronic Money Institution',
    'PSD_AISP': 'Account Information Service Provider',
    'PSD_EXC': 'Service provider excluded from the scope of PSD2',
    'PSD_ENL': 'Natural or Legal Person',
}
PIR_EXCLUDE = {'PSD_BR', 'PSD_AG'}

LISTNAME = {'1': 'Credit Institutions Register (CIR)', '2': 'Payment Institutions Register (PIR)'}

#------------------------------------------------ Begin_Fouction ----------------------------------------
def bourange_same_length_array(sqldict):
    maxlen = len(sqldict['ListProcessDate'])
    for key in sqldict:
        if len(sqldict[key]) != maxlen:
            sqldict[key] = sqldict[key] + [''] * (maxlen - len(sqldict[key]))
    return sqldict


def flatten_props(properties):
    '''EUCLID Properties is a list of single-key dicts: [{'ENT_NAM': 'X'}, {'ENT_COU_RES': 'IT'}, ...].'''
    out = {}
    for p in properties:
        for k, v in p.items():
            out[k] = v
    return out


def as_text(v):
    '''Some values arrive as a 1+ element list (e.g. a non-Latin name variant). Keep the last non-empty.'''
    if isinstance(v, list):
        vals = [x for x in v if x not in (None, '')]
        return str(vals[-1]) if vals else ''
    return '' if v is None else str(v)


def flatten_dates(v):
    '''ENT_AUT is always a list of ISO dates; flatten defensively and drop blanks.'''
    if v is None:
        return []
    if not isinstance(v, list):
        v = [v]
    out = []
    for x in v:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(x)
    return [d for d in out if d not in (None, '')]


def fetch_cir(entity_type):
    '''Return the COMPLETE list of CIR entities of one EntityType (the API returns the full set, no paging).'''
    body = {"$and": [{"_messagetype": "EUCLIDMD"}, {"_payload.EntityType": entity_type}]}
    r = session.post(
        BASE + "/api/search/entities",
        data=json.dumps(body),
        headers={"Content-Type": "application/json",
                 "Origin": "https://euclid.eba.europa.eu",
                 "Referer": BASE + "/cir/search"},
        timeout=300,
    )
    r.raise_for_status()
    return [o.get("_payload", o) for o in r.json()]


#------------------------------------------------ Begin_Main : ListCode 1 (CIR) ----------------------------------------
print(f"[INFO] : Gathering ListCode 1 - {LISTNAME['1']}")
for etype, label in CIR_TYPES.items():
    rows = fetch_cir(etype)
    print(f"[INFO] :   {etype} ({label}): {len(rows)} entities")
    for e in rows:
        props = flatten_props(e.get('Properties', []))

        sqldict['ListProcessDate'].append(processdate)
        sqldict['RegCtry'].append('II_EUR')
        sqldict['RegCode'].append('EBA')
        sqldict['ListCode'].append('1')
        sqldict['ListName'].append(LISTNAME['1'])
        sqldict['Typology'].append(label)

        sqldict['Name'].append(as_text(props.get('ENT_NAM')))
        sqldict['InternalID_1'].append(e.get('EntityCode', ''))
        sqldict['InternalID_1_type'].append('EBA Entity Code')
        sqldict['InternalID_2'].append(as_text(props.get('ENT_NAT_REF_COD')))
        sqldict['InternalID_2_type'].append('National Reference Code')
        if props.get('ENT_COD_TYP') == 'LEI':
            sqldict['LEI Code'].append(as_text(props.get('ENT_COD')))
        sqldict['City'].append(as_text(props.get('ENT_TOW_CIT_RES')))
        sqldict['Cntry'].append(as_text(props.get('ENT_COU_RES')))

        dates = flatten_dates(props.get('ENT_AUT'))
        if dates:
            sqldict['RegulationDate'].append(dates[-1])
        sqldict['RegulationType'].append('Authorised')

        # Mother (head-office) company: non-EEA branches carry the name + country of the
        # establishing credit institution; EEA branches carry only its code (no name).
        if props.get('NAM_CRE_INS_EST_BRA'):
            sqldict['Name - Mother Company'].append(as_text(props.get('NAM_CRE_INS_EST_BRA')))
        if props.get('COU_CRE_INS_EST_BRA'):
            sqldict['Cntry - Mother company'].append(as_text(props.get('COU_CRE_INS_EST_BRA')))

        sqldict = bourange_same_length_array(sqldict)

#------------------------------------------------ Begin_Main : ListCode 2 (PIR) ----------------------------------------
print(f"[INFO] : Gathering ListCode 2 - {LISTNAME['2']}")
session.get(BASE + "/pir/disclaimer", timeout=60)  # warm cookies before the golden-copy metadata call
meta = session.get(BASE + "/api/filemetadata", headers={"Accept": "application/json"}, timeout=120).json()
zip_url = meta['golden_copy_path_context'] + meta['latest_version_relative_zip_path']
print(f"[INFO] :   Downloading golden copy: {zip_url}")

zpath = os.path.join(tempfolder, os.path.basename(meta['latest_version_relative_zip_path']))
with session.get(zip_url, stream=True, timeout=600) as resp:
    resp.raise_for_status()
    with open(zpath, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=1 << 20):
            f.write(chunk)

with zipfile.ZipFile(zpath) as z:
    jname = [n for n in z.namelist() if n.endswith('.json') and not n.endswith('.sha256')][0]
    z.extract(jname, tempfolder)
jpath = os.path.join(tempfolder, jname)
with open(jpath, 'r', encoding='utf-8-sig') as f:
    data = json.load(f)

entities = data[1]  # data[0] is the disclaimer block, data[1] the entity array
print(f"[INFO] :   PIR total entities: {len(entities)}")

kept = 0
for e in entities:
    etype = e.get('EntityType')
    if etype in PIR_EXCLUDE:
        continue
    props = flatten_props(e.get('Properties', []))

    sqldict['ListProcessDate'].append(processdate)
    sqldict['RegCtry'].append('II_EUR')
    sqldict['RegCode'].append('EBA')
    sqldict['ListCode'].append('2')
    sqldict['ListName'].append(LISTNAME['2'])
    sqldict['Typology'].append(PIR_TYPES.get(etype, etype))

    sqldict['Name'].append(as_text(props.get('ENT_NAM')))
    sqldict['InternalID_1'].append(e.get('EntityCode', ''))
    sqldict['InternalID_1_type'].append('EBA Entity Code')
    sqldict['InternalID_2'].append(as_text(props.get('ENT_NAT_REF_COD')))
    sqldict['InternalID_2_type'].append('National Reference Code')
    sqldict['Address_1'].append(as_text(props.get('ENT_ADD')))
    sqldict['City'].append(as_text(props.get('ENT_TOW_CIT_RES')))
    sqldict['Zip'].append(as_text(props.get('ENT_POS_COD')))
    sqldict['Cntry'].append(as_text(props.get('ENT_COU_RES')))

    dates = flatten_dates(props.get('ENT_AUT'))
    if dates:
        if len(dates) % 2 == 1:  # odd -> still authorised, last date is the authorisation date
            sqldict['RegulationDate'].append(dates[-1])
            sqldict['RegulationType'].append('Authorised')
        else:                    # even -> authorised then cancelled
            sqldict['RegulationDate'].append(dates[-2])
            sqldict['CancellationDate'].append(dates[-1])
            sqldict['RegulationType'].append('Cancelled')
    else:
        sqldict['RegulationType'].append('Authorised')

    kept += 1
    sqldict = bourange_same_length_array(sqldict)

print(f"[INFO] :   PIR kept (excl. PSD_BR / PSD_AG): {kept}")

# clean the tempfolder (do not commit scraped source files)
for rem in os.listdir(tempfolder):
    try:
        os.remove(os.path.join(tempfolder, rem))
    except OSError:
        pass

#------------------------------------------------ Save DataFrame to Excel ----------------------------------------
os.chdir(scriptfolder)
df = pd.DataFrame(sqldict)
df.to_excel(filename, 'SQL Ready', index=False)
print(f"[INFO] : Excel file '{filename}' saved successfully ({len(df)} rows)")

#------------------------------------------------ Data Integrity & Consistency Check ----------------------------------------
print("=" * 80)
print("DATA INTEGRITY & CONSISTENCY VERIFICATION")
print("=" * 80)
print(f"Total rows: {len(df)}  |  Columns: {len(df.columns)}")
print("\nRows by ListCode:")
print(df.groupby('ListCode').agg(Count=('Name', 'count'), ListName=('ListName', 'first')))
print("\nRows by ListCode + Typology:")
print(df.groupby(['ListCode', 'Typology']).size())
print(f"\nRegCtry values: {df['RegCtry'].unique()}  |  RegCode values: {df['RegCode'].unique()}")
print(f"Names filled: {(df['Name'].astype(str).str.len() > 0).sum()}/{len(df)}")
print(f"Cntry filled: {(df['Cntry'].astype(str).str.len() > 0).sum()}/{len(df)}")
print(f"RegulationType values: {df['RegulationType'].value_counts().to_dict()}")
print("=" * 80)
