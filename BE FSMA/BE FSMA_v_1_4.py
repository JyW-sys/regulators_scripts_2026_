# by NL
# re-done by LLZ on 12.05.2022
# updated by Jingyi on 01/10/2024


#------------------------------------------------ Begin_Librairie ----------------------------------------

import pandas as pd 

from time import sleep

import datetime

from pandas import ExcelWriter

import re

import pdfplumber

import os

from bs4 import BeautifulSoup

from selenium import webdriver

from selenium.webdriver.common.by import By

from webdriver_manager.chrome import ChromeDriverManager

from selenium.webdriver.chrome.options import Options

# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'BE FSMA'

print(f"Running {regulatorName} Web Scraping Tool v.1.4")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

#scriptfolder=os.path.dirname(os.path.abspath(__file__))

os.chdir(scriptfolder)

writer = ExcelWriter(filename)

tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process



if os.path.exists(tempfolder):

    for rem in os.listdir(tempfolder):

        os.remove(os.path.join(tempfolder, rem))

else:

    os.mkdir(tempfolder)

# %%

#------------------------------------------------ Begin_chromedriver ----------------------------------------



#Starting Chrome driver, set to download files in tempfolder

chromeOptions = webdriver.ChromeOptions()

prefs = {"plugins.always_open_pdf_externally": True,

		 "download.prompt_for_download": False,

		 "download.default_directory" : tempfolder,

		 "selectedDestinationId": tempfolder,

    	 "version": 2}

chromeOptions.add_experimental_option("prefs",prefs)

driver = webdriver.Chrome(options=chromeOptions)

#driver = webdriver.Chrome(executable_path="..\\chromedriver.exe",options=chromeOptions)

driver.maximize_window()

#------------------------------------------------ Begin_Fouction ----------------------------------------

ref_dict = {'Allemagne':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Autriche':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Belgique':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Bulgarie':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Chypre':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Croatie':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Danemark':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Espagne':{'reg_zip' : '[0-9]{5}', '' : ''}, 'France':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Estonie':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Finlande':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Gibraltar':{'reg_zip' : '[A-Z0-9]{4}\s[a-zA-Z0-9]{3}\s', '' : ''}, 'Grèce':{'reg_zip' : '[0-9]{3}\s[0-9]{2}|[0-9]{4,5}', '' : ''}, 'Hongrie':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Irlande':{'reg_zip' : '[A-Z0-9]{3}\s[A-Z0-9]{4}', '' : ''}, 'Islande':{'reg_zip' : '[0-9]{3}', '' : ''}, 'Italie':{'reg_zip' : '[0-9]{5}', '' : ''}, 'Lettonie':{'reg_zip' : '[a-zA-Z]{2}\s[0-9]{4}|[a-zA-Z-]{3}[0-9]{4}|[0-9]{4}', '' : ''}, 'Liechtenstein':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Lituanie':{'reg_zip' : '[0-9]{5}|[0-9]{2}\s[0-9]{3}|[A-Z]{2}-[0-9]{5}', '' : ''}, 'Luxembourg':{'reg_zip' : '[0-9]{4}|[A-Z]-[0-9]{4}', '' : ''}, 'Malte':{'reg_zip' : '[A-Z]{3}\s[0-9]{4}|[A-Z]{3}\s[0-9]{4}', '' : ''}, 'Norvège':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Pays-Bas':{'reg_zip' : '[0-9]{4}\s[A-Z]{2}', '' : ''}, 'Pologne':{'reg_zip' : '[0-9]{2}-[0-9]{3}', '' : ''}, 'Portugal':{'reg_zip' : '[0-9]{4}-[0-9]{3}|[0-9]{4}', '' : ''}, 'Roumanie':{'reg_zip' : '[0-9]{6}', '' : ''}, 'Royaume-Uni':{'reg_zip' : '[A-Z0-9]{4}\s[A-Z0-9]{3}|[A-Z0-9]{3}\s[A-Z0-9]{3}|[A-Z0-9]{5,7}\sLondon', '' : ''}, 'Slovénie':{'reg_zip' : '[0-9]{4}', '' : ''}, 'Suède':{'reg_zip' : '[0-9]{3}\s[0-9]{2}', '' : ''}, 'Slovaquie':{'reg_zip' : '[0-9]{3}\s[0-9]{2}', '' : ''}, 'Tchéquie':{'reg_zip' : '[0-9]{3}\s[0-9]{2}', '' : ''}}

countries = {   'Allemagne': 'DE', 'France': 'FR', 'Finlande': 'FI', 'Grèce': 'GR', 'Hongrie': 'HU', 'Irlande': 'IE', 
                'Luxembourg': 'LU', 'Norvège': 'NO',  'Malte': '', 'Singapour':'', 'Royaume-Uni': 'GB', 'Israël': 'IL', 
                'Italie': 'IT', 'Australie': 'AU', 'Autriche': 'AT', 'Bulgarie': 'BG', 'Canada': 'CA', 'Chypre': 'CY','Danemark': 'DK',
                'Espagne': 'ES', 'Etats-Unis': 'US', 'Guernsey': 'GG', 'Islande': 'IS', 'Liechtenstein': 'LI', 'Lituanie': 'LT', 'Suède': 'SE',
                'Suisse': 'CH', 'Pays-Bas':'NL', 'Tchequie': 'CZ'}


def remove_numbers(company_name):
    company_name = company_name.replace('■', '').strip()
    for i_char in range(len(company_name)-1,-1,-1):
        if company_name[i_char].isdigit():
            company_name = company_name[:i_char]#.strip() will cause indexerror
        elif company_name.endswith(' '):
            company_name = company_name[:i_char]
        elif i_char > 1 and company_name[i_char].isalpha() and ' ' == company_name[i_char-1] and company_name[i_char] == company_name[i_char].lower():  #deleting ' a b c ' at the en of the names
            company_name = company_name[:i_char]
        elif company_name[i_char].isalpha():
            break
    return company_name.strip()


def parse_addr(addr, ctry):
    ctry = str(ctry).strip()
    addr = re.sub(r'\s', ' ', addr)
    addr = str(addr).strip()
    # check if the country is known
    if ctry not in list(ref_dict.keys()) or len(addr) < 2:
        #print(ctry)
        #print("Addr: ", addr)
        return addr, '', ''
    regexp_zip = ref_dict[ctry]['reg_zip']
    regexp_zip_out = re.findall(regexp_zip, addr)
    if regexp_zip_out:
        zipx = regexp_zip_out[0]
        city = addr.split(zipx)[1]
        # print(zipx)
        if 'London' in zipx:
            zipx = zipx.replace('London', '')
            city = 'London'
        #
    else:
        city = addr.split(' ')[-1] if not addr[-1].isdigit() else ''
        zipx = ''
    addrx = addr.replace(zipx, '')
    addrx = addrx.replace(city, '')
    return addrx.strip(), zipx.strip(), city.strip()

# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict = { 'BE FSMA 6': 'https://www.fsma.be/sites/default/files/legacy/content/Lijsten/beleggingsondernemingen/FR/eboeee.pdf',
            'BE FSMA 7': 'https://www.fsma.be/sites/default/files/legacy/content/Lijsten/beleggingsondernemingen/FR/lps_eibo_cee.pdf',
            'BE FSMA 8': 'https://www.fsma.be/sites/default/files/legacy/content/Lijsten/beleggingsondernemingen/FR/lps_eibo_no_cee.pdf',
            'BE FSMA 10': 'https://www.fsma.be/sites/default/files/public/ucits_iii_agr.pdf',
            'BE FSMA 12': 'https://www.fsma.be/sites/default/files/public/ucits_iv_eec.pdf',
            'BE FSMA 14': 'https://www.fsma.be/sites/default/files/public/ucits_iv_lps.pdf',
            'BE FSMA 20': 'https://www.fsma.be/sites/default/files/public/aifm_be_1.pdf',
            'BE FSMA 21': 'https://www.fsma.be/sites/default/files/public/aifm_eee.pdf',
            'BE FSMA 22': 'https://www.fsma.be/sites/default/files/legacy/aifm_lps_1.pdf'}

#'BE FSMA 9': 'https://www.fsma.be/fr/list/bureaux-de-change-enregistres-en-belgique', no pdf

sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 
         'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 
         'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 
         'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
         'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 
         'Phone - Mother company': [], 'Check': []}
         
RegulationType = {1 : "Authorised", 2 : "Authorised", 3 : "EEA Authorised", 4 : "EEA Authorised", 5 : "Registered", 6 : "Licensed", 7 : "EEA Authorised", 8 : "EEA Authorised", 9 : "Licensed", 10 : "Authorised", 11 : "Authorised", 12 : "Authorised", 13 : "Licensed", 14 : "Registered", 15 : "EEA Authorised", 16 : "Licensed", 17 : "Registered", 18 : "EEA Authorised"}

processdate = now.strftime('%Y-%m-%d')

# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for reg in regdict:
    print(f'Working with list {reg}')
    driver.get(regdict[reg])
    for times in range(50):
        dl_files = [os.path.join(tempfolder, f) for f in os.listdir(tempfolder)]
        if len(dl_files)>0 and not dl_files[0].endswith('.tmp') and not dl_files[0].endswith('.crdownload'):
            break
        sleep(1)
    else:
        raise Exception('BE FMSA - Failed to download file - '+reg)
    pages_text = list()
    bold_lines = list()
    with pdfplumber.open(dl_files[0]) as pdf:
        for page in pdf.pages:
            bold_text = page.filter(lambda obj: obj["object_type"] == "char" and "Bold" in obj["fontname"]).extract_text()
            if bold_text is not None:
                bold_lines.extend([ele.strip() for ele in bold_text.split('\n') if len(ele) > 0])            
            pages_text.append(page.extract_text().strip())
    os.remove(dl_files[0])
    all_text = '\n'.join(pages_text)
    lines = [ele.strip() for ele in all_text.split('\n') if len(ele.strip()) > 0]
    country_found = ''
    company_found = False
    for i, line in enumerate(lines):
        #if i>4 and '■' not in ''.join(lines[i:]): #no remaning companies no need to check for Modifications or anything else
        #    print('No companies ', )
        #    break
        if 'Modifications' in line and '■' not in ''.join(lines[i:]):
            break#print('breaking after finding:', line)
        #if '■' not  in ''.join(lines[:i]):
        #    continue
        if 'o' in line and line.replace('o', '').strip() in bold_lines:
            if len(sqldict['Name']) > len(sqldict['Address_1']):
                sqldict['Address_1'].append(', '.join(address))
                sqldict['RegCtry'].append('BE')
                sqldict['RegCode'].append('FSMA')
                sqldict['ListCode'].append(reg.split()[-1])
                sqldict['ListProcessDate'].append(processdate)
                sqldict['Cntry'].append(country_found)
                for key in sqldict:
                    if len(sqldict['Name']) > len(sqldict[key]):
                        sqldict[key].append('')
            country_found = line.replace('o', '').strip()
            if country_found in countries:
                country_found = countries[country_found]
            continue#if country found; nothind else to do in the current loop/iteration
        elif '■' in line: #company found
            company_found = True
            if len(sqldict['Name']) > len(sqldict['Address_1']):
                sqldict['Address_1'].append(', '.join(address))
                sqldict['RegCtry'].append('BE')
                sqldict['RegCode'].append('FSMA')
                sqldict['ListCode'].append(reg.split()[-1])
                sqldict['ListProcessDate'].append(processdate)
                sqldict['Cntry'].append(country_found)
                for key in sqldict:
                    if len(sqldict['Name']) > len(sqldict[key]):
                        sqldict[key].append('')
            name = remove_numbers(line)
            sqldict['Name'].append(name)
            address = list()
            #print(remove_numbers(line))
        elif company_found:
            if line in bold_lines:
                line = remove_numbers(line)
                sqldict['Name'][-1] = sqldict['Name'][-1] + f' {line}'
            elif line.startswith('Société') or line.startswith('Not applicable') or line == 'Limited':
                continue
            else:
                address.append(line.strip())
        #else:
        #    print('Else:', i, line)
    sqldict['Address_1'].append(', '.join(address))
    sqldict['Cntry'].append(country_found)
    sqldict['RegCtry'].append('BE')
    sqldict['RegCode'].append('FSMA')
    sqldict['ListCode'].append(reg.split()[-1])
    sqldict['ListProcessDate'].append(processdate)
    for key in sqldict:
        if len(sqldict['Name']) > len(sqldict[key]):
            sqldict[key].append('')

# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)
    