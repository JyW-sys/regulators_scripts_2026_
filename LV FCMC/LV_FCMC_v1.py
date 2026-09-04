from bs4 import BeautifulSoup
from time import sleep
import pandas as pd
from pandas import ExcelWriter
import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import os


print("Running LV FCMC Web Scraping Tool v.1.0")
now=datetime.datetime.now()
scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)
tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process

filename= 'LV FCMC data {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)

regdict={'LV FCMC 1': 'https://www.fktk.lv/en/market/credit-institutions/Banks/?l=', 
		 'LV FCMC 2': 'https://www.fktk.lv/en/market/credit-institutions/Service-providers-from-the-EEA/Freedom-of-establishment/?l=',
		 'LV FCMC 3': 'https://www.fktk.lv/en/market/credit-institutions/Service-providers-from-the-EEA/Freedom-to-provide-services/?l=',
		 'LV FCMC 4': 'https://www.fktk.lv/en/market/credit-institutions/Credit-Institutions-in-Liquidation/?l=',
		 'LV FCMC 5': 'https://www.fktk.lv/en/market/credit-institutions/Representative-offices-of-foreign-financial-institutions/?l=',
		 'LV FCMC 6': 'https://www.fktk.lv/en/market/co-operative-credit-unions/Service-providers-from-the-EEA/?l=',
		 'LV FCMC 6': 'https://www.fktk.lv/en/market/payment-service-providers/Co-operative-Credit-Unions/?l=',
		 'LV FCMC 7.1': 'https://www.fktk.lv/en/market/insurance-companies/Life-insurance-companies/?l=',
		 'LV FCMC 7.2': 'https://www.fktk.lv/en/market/insurance-companies/Non-life-insurance-companies/?l=',
		 'LV FCMC 8.1': 'https://www.fktk.lv/en/market/insurance-companies/service-providers-from-the-eea/freedom-of-establishment/branches-of-member-state-life-insurers/?l=',
		 'LV FCMC 8.2': 'https://www.fktk.lv/en/market/insurance-companies/service-providers-from-the-eea/freedom-of-establishment/branches-of-member-state-non-life-insurers/?l=',
		 'LV FCMC 9.1': 'https://www.fktk.lv/en/market/insurance-companies/Service-Providers-from-the-EEA/Freedom-to-provide-services/?l=',
		 'LV FCMC 9.2': 'https://www.fktk.lv/en/market/insurance-companies/service-providers-from-the-eea/freedom-to-provide-services/member-state-life-insurers/?l=',
		 'LV FCMC 9.3': 'https://www.fktk.lv/en/market/insurance-companies/service-providers-from-the-eea/freedom-to-provide-services/member-state-non-life-insurers/?l=',
		 'LV FCMC 10': 'https://www.fktk.lv/en/market/insurance-intermediaries/Insurance-merchant-who-keeps-a-register-of-tied-insurance-agents/?l=',
		 'LV FCMC 11': 'https://www.fktk.lv/en/market/insurance-intermediaries/agents/legal-entity/?l=',
		 'LV FCMC 12': 'https://www.fktk.lv/en/market/insurance-intermediaries/Service-providers-from-the-EEA/Freedom-of-Establishment/?l=',
		 'LV FCMC 13': 'https://www.fktk.lv/en/market/insurance-intermediaries/insurance-brokers/legal-entity/?l=',
		 'LV FCMC 14': 'https://www.fktk.lv/en/market/investment-management-companies/?l=',
		 'LV FCMC 15': 'https://www.fktk.lv/en/market/investment-management-companies/Foreign-Funds/?l=',
		 'LV FCMC 16': 'https://www.fktk.lv/en/market/investment-management-companies/Service-providers-from-the-EEA/Freedom-to-provide-services/?l=',
		 'LV FCMC 17': 'https://www.fktk.lv/en/market/payment-service-providers/Payment-institutions/Registered-payment-institutions/?l=',
		 'LV FCMC 19.1': 'https://www.fktk.lv/en/market/payment-service-providers/Payment-institutions/Service-providers-from-the-EEA/Freedom-of-Establishment/?l=',
		 'LV FCMC 19.2': 'https://www.fktk.lv/en/market/payment-service-providers/payment-institutions/service-providers-from-the-eea/freedom-of-establishment/?l=',
		 'LV FCMC 19.3': 'https://www.fktk.lv/en/market/payment-service-providers/payment-institutions/service-providers-from-the-eea/freedom-to-provide-services/?l=',
		 'LV FCMC 20': 'https://www.fktk.lv/en/market/pension-funds/Private-pension-funds/?l=',
		 'LV FCMC 21': 'https://www.fktk.lv/en/market/alternative-investment-fund-managers/Licensed-managers/?l=',
		 'LV FCMC 22': 'https://www.fktk.lv/en/market/alternative-investment-fund-managers/Registered-managers/?l=',
		 'LV FCMC 23': 'https://www.fktk.lv/en/market/alternative-investment-fund-managers/Managers-from-EEA/Freedom-to-provide-services/?l=',
		 'LV FCMC 24': 'https://www.fktk.lv/en/market/payment-service-providers/Electronic-money-institutions/Authorized-electronic-money-institutions/?l=',
		 'LV FCMC 25': 'https://www.fktk.lv/en/market/payment-service-providers/Electronic-money-institutions/Registered-electronic-money-institutions/?l=',
		 'LV FCMC 27.1': 'https://www.fktk.lv/en/market/payment-service-providers/electronic-money-institutions/service-providers-from-the-eea/?l=',
		 'LV FCMC 27.2': 'https://www.fktk.lv/en/market/payment-service-providers/electronic-money-institutions/service-providers-from-the-eea/freedom-of-establishment/?l=',
		 'LV FCMC 27.3': 'https://www.fktk.lv/en/market/payment-service-providers/electronic-money-institutions/service-providers-from-the-eea/freedom-to-provide-services/?l=',
		 'LV FCMC 28': 'https://www.fktk.lv/en/market/payment-service-providers/Payment-institutions/Authorized-payment-institutions/?l='}

driver = webdriver.Chrome()
driver.maximize_window()

sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 
		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 
		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 
		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],
		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 
		  'Phone - Mother company': [], 'Check': []}

catlist=['Registration number', 'Legal address', 'Country of origin', 'Supervisory authority', 'Market segment', 'Phone', 'E-mail', 'Website']

ISO_ENG = {'Croatia': 'HR', 'Germany': 'DE', 'Italy': 'IT', 'Poland': 'PL', 'Norway': 'NO', 'Switzerland': 'CH', 
            'Luxembourg': 'LU', 'Gibraltar': 'GI', 'Estonia': 'EW', 'Slovenia': 'SI', 'Caribbean Netherlands': 'BQ', 
            'Portugal': 'PT', 'Slovakia': 'SK', 'Ireland': 'IE', 'Netherlands': 'NL', 'Hungary': 'HU', 'Sweden': 'SE', 
            'Austria': 'AT', 'France': 'FR', 'Lithuania': 'LT', 'Bulgaria': 'BG', 'Romania': 'RO', 'Iceland': 'IS', 
            'Latvia': 'LV', 'Kyrgyzstan': 'KG', 'Czechia': 'CZ', 'Malta': 'MT', 'Spain': 'ES', 'Denmark': 'DK', 'Belgium': 'BE', 
            'Cyprus': 'CY', 'Finland': 'FI', 'Greece': 'GR', 'Liechtenstein': 'LI'}

processdate=now.strftime('%Y-%m-%d')
missing_countries = list()
for reg in regdict:
    print("Working with {} Reg Code".format(reg))
    clinks=[]
    driver.get(regdict[reg]+"1")
    sleep(2)
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    if soup.find("div",  {"class": "pagination"}):
        pagination=soup.find("div",  {"class": "pagination"}).find("ul").find_all("li")
        if len(pagination[-1].text)>0:
            totalpages=int(pagination[-1].text)
        else:
            totalpages=int(pagination[-2].text)
    else:
        totalpages=1
    for page in range(totalpages):
        print(reg,": page {} out of {}".format(page+1,totalpages))
        driver.get(regdict[reg]+str(page+1))
        sleep(1)
        soup2 = BeautifulSoup(driver.page_source, 'html.parser')
        for k in  soup2.find_all("div", {"class":"post"}):
            clinks.append(k.find('a', href=True)['href'])
    for link in range(len(clinks)):
        print(reg,": entity {} out of {}".format(link+1,len(clinks)))
        labels = list()
        values = list()
        driver.get(clinks[link])
        sleep(0.5)
        soupn=BeautifulSoup(driver.page_source,"html.parser")
        if '<!-- .info-block -->' in str(soupn):
            sqldict['Name'].append(soupn.find('h2').text.strip())
            sqldict['ListProcessDate'].append(processdate)
            sqldict['RegCtry'].append('LV')
            sqldict['RegCode'].append('FCMC')
            sqldict['ListCode'].append(reg.split()[-1].split('.')[0])
            sqldict['RegulationType'].append('Regulated')
            soupn=soupn.find("section", {'class':'market-page single'})
            info_blocks = soupn.find_all('div', {'class':'info-block'})
            for block in info_blocks:
                print(str(block)[:50])
                if 'licenses-block' not in str(block)[:50]:
                    row_div = block.find('div', {'class': 'row'})
                    data_divs = row_div.find_all('div', {'class':'market-item'})
                    for data in data_divs:
                        if 'market-item label' in str(data):
                            labels.append(data.text.strip())
                        else:
                            values.append(data.text.strip())
            for rang in range(len(labels)):
                label = labels[rang]
                value = values[rang]
                if label.lower()=='registrarion number' and len(sqldict['InternalID_1'])<len(sqldict['Name']):
                    sqldict['InternalID_1_type'].append('Registration Number')
                    sqldict['InternalID_1'].append(value)
                elif label.lower()=='legal address' and len(sqldict['Address_1'])<len(sqldict['Name']):
                    sqldict['Address_1'].append(value)
                elif label.lower()=='phone' and len(sqldict['Phone'])<len(sqldict['Name']):
                    sqldict['Phone'].append(value)
                elif label.lower()=='e-mail' and len(sqldict['Email'])<len(sqldict['Name']):
                    sqldict['Email'].append(value)
                elif label.lower()=='website' and len(sqldict['Website'])<len(sqldict['Name']):
                    sqldict['Website'].append(value)
                elif label.lower()=='country of origin' and len(sqldict['Cntry'])<len(sqldict['Name']):
                    if value in ISO_ENG:
                        sqldict['Cntry'].append(ISO_ENG[value])
                    else:
                        missing_countries.append(value)
            if len(sqldict['Cntry'])<len(sqldict['Name']):#if country not found in the site
                sqldict['Cntry'].append('LV')
            for key in sqldict:
                if len(sqldict[key])<len(sqldict['Name']):
                    sqldict[key].append('')
        else:#Prevents errors from links directing to main page like the last entity of reg code LV FCMC 3 ("Swedbank" AB)
            print(f"The link {clinks[link]} didn't load.")

print('LV FCMC MISSING COUNTRIES IN ISO LIST:', list(set(missing_countries)))
df = pd.DataFrame(sqldict)
df.to_excel(writer,'SQL', index=False)

writer.save()
writer.close()

sleep(3)

driver.quit()
    
    