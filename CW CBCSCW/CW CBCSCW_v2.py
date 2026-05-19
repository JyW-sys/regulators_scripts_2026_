import os
import re
import datetime
import pandas as pd
import pdfplumber
from time import sleep
from bs4 import BeautifulSoup
from DrissionPage import ChromiumPage, ChromiumOptions

regulatorName = 'CW CBCSCW'
print(f'Running {regulatorName} Web Scraping Tool v.1.1')

now = datetime.datetime.now()
processdate = now.strftime('%Y-%m-%d')
filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(':', '.')[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - Moody's\\Desktop\\Regulator\\{regulatorName}"
os.chdir(scriptfolder)

tempfolder = os.path.join(scriptfolder, 'tempfolder')
os.makedirs(tempfolder, exist_ok=True)
cleanup_tempfolder_after_export = False  # Keep PDFs while tuning parser validation.

options = ChromiumOptions()
options.set_download_path(tempfolder)

options.set_pref("plugins.always_open_pdf_externally", True)
options.set_pref("download.prompt_for_download", False)
options.set_pref("download.default_directory", tempfolder)

driver = ChromiumPage(options)
regdict = {regulatorName + ' 1': 'https://www.centralbank.cw/functions/supervision/supervised-institutions'}
Typology = {regulatorName + ' 1': 'Supervised Institutions'}

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],
           'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],
           'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],
           'RegCtry': [], 'RegCode': [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
           'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],
           'Phone - Mother company': [], 'Check': []}

PDF_MAJOR_HEADINGS = {
    'Banks & Non Banks',
    'Insurers & Pension Funds',
    'Securities, Stock Exchange & Trust',

 
}
PDF_MINOR_HEADINGS = {
    'Local General Bank', 'Subsidiary of Foreign Bank', 'Branch of Foreign Bank', 'Credit Union',
    'Specialized Credit Institution', 'Savings Bank', 'Savings and Credit Fund', 'Consolidated International Bank',
    'Non-Consolidated International Bank', 'Appendix I: Coupon Credit article 45',
    'Appendix II: Savings and Thrift Fund article 45',
    'Appendix III: Other institutions or persons in the possession of a dispensation to extend credits directly or indirectly article 45',
    'Money Transfer Company', 'Life Insurance Company', 'Branch of foreign insurance company', 'Independent Company',
    'Subsidiary of foreign insurance company', 'Funeral Services Insurance Company', 'Indemnity Insurance Company',
    'Professional Indemnity Reinsurance Company', 'Captive', 'Indemnity Insurance Captive', 'Life Insurance Captive',
    'Broker', 'Indemnity and Life Insurance Broker', 'Indemnity Insurance Broker', 'Life Insurance Broker',
    'Pension Fund', 'Corporate Pension Fund', 'General Pension Fund', 'Administrator', 'Local Administrator',
    'Asset Management Company', 'Dispensation Asset Manager', 'License Asset Management', 'Investment Institutions',
    'Foreign Investment Fund', 'Securities Exchange', 'Securities Intermediary', 'License Securities Intermediary',
    'Registration Securities Intermediary', 'Trust Service Providers', 'Dispensation Legal Person',
    'Dispensation Natural Person', 'License Legal Person', 'License Natural Person'
}
PDF_GROUP_HEADINGS = {
    'Life Insurance Company', 'Indemnity Insurance Company', 'Captive', 'Broker', 'Pension Fund',
    'Administrator', 'Asset Management Company', 'Investment Institutions', 'Securities Intermediary',
    'Trust Service Providers'
}
PDF_NATURAL_PERSON_SECTIONS = {'Dispensation Natural Person', 'License Natural Person'}
PDF_COUNTRY_CODES = {
    'Curaçao': 'CW', 'Curacao': 'CW', 'Sint Maarten': 'SX', 'United States of America': 'US',
    'Saint Lucia': 'LC', 'Barbados': 'BB', 'Antigua': 'AG', 'Trinidad and Tobago': 'TT',
    'India': 'IN', 'England': 'GB', 'Luxembourg': 'LU'
}
PDF_CITY_DEFAULT_COUNTRY = {
    'Willemstad': 'Curaçao', 'Parrera': 'Curaçao', 'Philipsburg': 'Sint Maarten',
    'Phillipsburg': 'Sint Maarten', 'Philipsbrug': 'Sint Maarten', 'Cole Bay': 'Sint Maarten',
    'Simpson Bay': 'Sint Maarten', 'Cul de Sac': 'Sint Maarten', 'Castries': 'Saint Lucia',
    'Bridgetown': 'Barbados', "St. John's": 'Antigua', 'Port of Spain': 'Trinidad and Tobago',
    'Mumbai': 'India', 'London': 'England', 'Madison': 'United States of America',
    'Florida': 'United States of America', 'St. Michael': 'Barbados'
}
PDF_ADDRESS_WORDS = (
    'box', 'road', 'street', 'straat', 'weg', 'kaya', 'avenue', 'boulevard', 'plein', 'plaza',
    'center', 'centre', 'building', 'complex', 'office', 'park', 'tower', 'mall', 'suite',
    'unit', 'floor', 'landhuis', 'handelskade', 'watersteeg', 'frontstreet', 'corner of', 'c/o'
)
PDF_ENTITY_WORDS = (
    'n.v.', 'b.v.', 's.a.', 'inc', 'limited', 'ltd', 'company', 'bank', 'foundation',
    'stichting', 'fundashon', 'fund', 'insurance', 'trust', 'management', 'services',
    'broker', 'union', 'pension', 'corporation', 'coöperatieve', 'cooperatieve',
    'kooperativa', 'exchange', 'securities', 'capital', 'finance', 'financial', 'asset',
    'group', 'institution', 'reinsurance'
)


# 2. Open fresh browser with correct prefs
options = ChromiumOptions()
options.set_download_path(tempfolder)
options.set_pref('plugins.always_open_pdf_externally', True)
options.set_pref('download.prompt_for_download', False)
options.set_pref('download.default_directory', tempfolder)

driver = ChromiumPage(options)

# 3. Visit the page first to pass Cloudflare, then click the PDF link
driver.get("https://www.centralbank.cw/functions/supervision/supervised-institutions")
sleep(60)

pdf_link = driver.ele('xpath://a[contains(@href, "registry_of_supervised_institutions")]')

mission = pdf_link.click.to_download(
    tempfolder,
    "20260211_registry_of_supervised_institutions_as_per_december_31_2025.pdf"
)
mission.wait()

print(mission.final_path)
print(os.listdir(tempfolder))


registry_pdf_files = [
    os.path.join(tempfolder, file)
    for file in sorted(os.listdir(tempfolder))

]

if registry_pdf_files:
    print(f'[INFO] : found {len(registry_pdf_files)} registry PDF file(s) in tempfolder')
        
    records = []
    current_record = None
    pdf_headings = set().union(
        globals().get('PDF_MAJOR_HEADINGS', set()),
        globals().get('PDF_MINOR_HEADINGS', set()),
        globals().get('PDF_GROUP_HEADINGS', set()),
    )


    def clean_chars(line_chars):
        line_chars = sorted(line_chars, key=lambda item: item.get('x0', 0))
        parts = []
        previous_x1 = None
        previous_size = 9

        for char in line_chars:
            if previous_x1 is not None and char.get('x0', 0) - previous_x1 > max(1.5, previous_size * 0.25):
                parts.append(' ')
            parts.append(char.get('text', ''))
            previous_x1 = char.get('x1', char.get('x0', 0))
            previous_size = char.get('size', previous_size)

        return re.sub(r'\s+', ' ', ''.join(parts)).strip()


    with pdfplumber.open(registry_pdf_files[0]) as pdf:
        for page in pdf.pages:
            page_lines = {}
            for char in page.chars:
                if char.get('object_type') != 'char' or 'BKSWEM+MuseoSans-300' not in char.get('fontname', ''):
                    continue
                if char.get('size', 0) <= 9:
                    continue
                page_lines.setdefault(round(char.get('top', 0), 1), []).append(char)

            for top in sorted(page_lines):
                line_chars = page_lines[top]
                name_text = clean_chars([char for char in line_chars if char.get('stroking_color') == (0.0,)])
                info_text = clean_chars([char for char in line_chars if char.get('stroking_color') == (1.0,)])

                if info_text and re.sub(r'\s+\d+(?:\.\d+)?$', '', info_text).strip() in pdf_headings:
                    info_text = ''

                if name_text:
                    current_record = {'name': name_text, 'info': []}
                    records.append(current_record)

                if info_text and current_record is not None:
                    current_record['info'].append(info_text)

    name = []
    info_blocks = []

    for record in records:
        clean_name = re.sub(r'\s+', ' ', record['name']).strip()
        if not clean_name or clean_name.isdigit() or not re.search(r'[A-Za-zÀ-ÿ]', clean_name):
            continue

        info_block = re.sub(r'\s+', ' ', ' '.join(record['info'])).strip()

        # Remove bracket notes like [Sint Maarten branch]
        info_block = re.sub(r'\[[^\]]*\]\s*', '', info_block)

        # Remove Exhibit A/B and everything after
        info_block = re.sub(r'\bExhibit\s+[AB]\b.*$', '', info_block)

        # Remove Broker status and Actual leader info
        info_block = re.sub(r'\bBroker status:\s*.*?(?=\bActual leader:|$)', '', info_block)
        info_block = re.sub(r'\bActual leader:\s*.*$', '', info_block)

        info_block = re.sub(r'\s+', ' ', info_block).strip()

        name.append(clean_name)
        info_blocks.append(info_block)
        
    info_blocks = [
        re.sub(r'\bExhibit\s+[AB]\b.*$', '', re.sub(r'\[[^\]]*\]\s*', '', item)).strip()
        for item in info_blocks
    ]




    for na, info in list(zip(name, info_blocks)):
        # print('Name: ->',na)
        sqldict['Name'].append(na)
        sqldict['ListProcessDate'].append(processdate)
        sqldict['RegCtry'].append('CW')
        sqldict['RegCode'].append('CBCSCW')
        sqldict['ListCode'].append('1')
        sqldict['RegulationType'].append('Regulated')
        sqldict['ListName'].append('Supervised Institutions')
               

        index_web = info.find('http')
        
        if index_web != -1:
            email_ = info[index_web:]
            sqldict['Website'].append(info[index_web:])
            address_1 = re.sub(r'\[[^\]]*\]\s*', '', info[:index_web]).strip()
            sqldict['Address_1'].append(address_1)
        else:
            
            clean_text = re.sub(r'\[[^\]]*\]\s*', '', info).strip()
            # print(clean_text)
            sqldict['Address_1'].append(clean_text)
#------------------------------------------------ Begin_Fouction ----------------------------------------
def bourange_same_length_array(sqldict) :
    maxlen = len(sqldict['ListProcessDate'])
    for key, val in sqldict.items():
        if len(sqldict[key]) != maxlen:
            empty = []
            total_empty = maxlen - len(sqldict[key])
            for i in range(total_empty):
                empty.append('')
            sqldict[key]=sqldict[key]+empty
    return sqldict
sqldict = bourange_same_length_array(sqldict)
#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------
os.chdir(scriptfolder)
df=pd.DataFrame(sqldict)


df_copy = df.copy()

df_copy['RegCode'] = 'CBCSSX'
df_copy['RegCtry'] = 'SX'

df_total = pd.concat([df, df_copy], ignore_index=True)

df_total.to_excel(filename, index=False)
driver.quit()
sleep(3)

for rem in os.listdir(tempfolder):
    os.remove(os.path.join(tempfolder, rem))

import os
import re
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

os.chdir(scriptfolder)
tempfolder = os.path.join(scriptfolder, 'tempfolder')

if os.path.exists(tempfolder):
    for rem in os.listdir(tempfolder):
        os.remove(os.path.join(tempfolder, rem))
else:
    os.mkdir(tempfolder)

df_pdf = pd.read_excel(filename)

arial_path = r"C:\Windows\Fonts\arial.ttf"
if os.path.exists(arial_path):
    pdfmetrics.registerFont(TTFont('ArialUni', arial_path))
    FONT_NAME = 'ArialUni'
else:
    FONT_NAME = 'Helvetica'
    print("WARNING: arial.ttf not found, Hungarian characters may not render correctly.")

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

    x = 72
    y = draw_header(c, 740)
    max_lines_per_page = 32
    line_count = 0

    for item in data_list:
        c.drawString(x, y, str(item))
        y -= 20
        line_count += 1

        if line_count >= max_lines_per_page:
            c.showPage()
            c.setFont(FONT_NAME, 12)
            y = draw_header(c, 740)
            line_count = 0

    c.save()

os.makedirs(tempfolder, exist_ok=True)

for list_code, group in df_pdf.groupby('ListCode', dropna=False):
    code = safe_filename(list_code)
    items = group['Name'].dropna().astype(str).tolist()
    if not items:
        continue
    pdf_path = os.path.join(tempfolder, f"HU CBH data 2026-04-03 18.56.00- {code}.pdf")
    export_list_to_pdf(items, pdf_path)
