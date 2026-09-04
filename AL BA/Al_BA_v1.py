# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from bs4 import BeautifulSoup

import datetime

import pandas as pd

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support import expected_conditions as EC

from selenium.webdriver.common.by import By

from time import sleep

import os

import re

import pdfplumber

import tabula 

from selenium.webdriver.chrome.service import Service as ChromeService



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'AL BA' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.1")

now=datetime.datetime.now()

filename = '{} data {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

#scriptfolder = f"C:\\Users\\siewekoa\\OneDrive - moodys.com\\Desktop\\My_data\\Project_work\\scripts_regulator\\{regulatorName}" ## to comment for the production environment

scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

os.chdir(scriptfolder)

writer = ExcelWriter(filename)

tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process

if os.path.exists(tempfolder):

    for rem in os.listdir(tempfolder):

        os.remove(os.path.join(tempfolder, rem))

else:

    os.mkdir(tempfolder)



# %%

#Starting Chrome driver, set to download files in tempfolder

chromeOptions = webdriver.ChromeOptions()

prefs = {"plugins.always_open_pdf_externally": True,

		 "download.prompt_for_download": False,

		 "download.default_directory" : tempfolder,

         'profile.default_content_setting_values.automatic_downloads': 1 # Desable a Multiplefile download alert

         }

chromeOptions.add_argument("--disable-search-engine-choice-screen")

chromeOptions.add_experimental_option("prefs",prefs)

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={

    'AL BA 1': 'https://www.bankofalbania.org/Supervision/Licensed_institutions/Banks/', 

	'AL BA 2': 'https://www.bankofalbania.org/Mbikeqyrja/Subjekte_te_licencuara/Zyra_te_kembimit_valutor/', 

	'AL BA 3': 'https://www.bankofalbania.org/Mbikeqyrja/Subjekte_te_licencuara/Subjekte_Financiare_jobanka/', 

	'AL BA 4': 'https://www.bankofalbania.org/Mbikeqyrja/Subjekte_te_licencuara/Shoqeri_te_kursim_kreditit_dhe_unionet_e_SHKK-ve/',

    'AL BA 5': 'https://www.bankofalbania.org/Supervision/Licensed_institutions/Payment_Institutions/',

    'AL BA 6': 'https://www.bankofalbania.org/Supervision/Licensed_institutions/Electronic_Money_Institutions/', 

    }



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

		  'Phone - Mother company': [], 'Check': []}



pattern = re.compile('^([0-9]+\.)')

patternLicense = re.compile('(Licenca:|Licenca)')

patternTel = re.compile('(Telefon:|Telefon;|Mobile|Tel.)')

patternFax = re.compile('(Tel\/fax:|Tel\./fax:|Tel.\ /fax:|Fax:|Fax\.|Fax)')

patternAddress = re.compile('(Adresa:|Adresa)')

patternEmail = re.compile('(E-mail:|E - mail:)')

patternNUIS = re.compile('(NUIS:)')



processdate = now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def bourange_same_length_array(sqldict) :

    len_value=[]

    for key, value in sqldict.items():

        len_value.append(len(value))

    maxlen = max(len_value)

    for key, val in sqldict.items():

        if len(sqldict[key]) != maxlen:

            empty = []

            total_empty = maxlen - len(sqldict[key])

            for i in range(total_empty):

                empty.append('')

            sqldict[key]=sqldict[key]+empty

    return sqldict



def check_dowload_files(tempfolder, fileType, wait_time=10):

    sleep(2)

    for time in range(wait_time):

        if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

            print(f"[INFO] : - {fileType} file = {os.listdir(tempfolder)})")

            break

        else:

            print(f"[INFO] : - Download {fileType} file ... (wait {time*2}/20 s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : Failed to Download {fileType} file. Run Script again' )

    return  os.listdir(tempfolder)[0]







# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    

    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")

    driver.get(regdict[reg])

    sleep(3)

    

    if reg == 'AL BA 1':

        soup = BeautifulSoup(driver.page_source, "html.parser")

        h4_s = soup.find("div",{"class":"fq-list"}).find_all("h4") #find_all

        for h4 in h4_s :

            div = h4.find_parent('div')

            address = div.find('p').text.replace('Address:', '').strip()

            tr_s = div.find("tbody").find_all('tr')



            sqldict['Name'].append(h4.text.strip())

            sqldict['InternalID_1'].append(tr_s[1].find_all('td')[-1].text)

            sqldict['InternalID_1_type'].append('NUIS/NIPT')

            sqldict['Phone'].append(tr_s[2].find_all('td')[-1].text)

            sqldict['Fax'].append(tr_s[3].find_all('td')[-1].text)

            sqldict['Website'].append(tr_s[4].find_all('td')[-1].text)

            sqldict['Email'].append(tr_s[5].find_all('td')[-1].text)

            # sqldict['Cntry'].append('AL')

            sqldict['ListProcessDate'].append(processdate)

            sqldict['RegCtry'].append(reg.split()[0])

            sqldict['RegCode'].append(reg.split()[1])

            sqldict['ListCode'].append(reg.split()[2])

            sqldict['RegulationType'].append('Regulated')

     

        sqldict = bourange_same_length_array(sqldict)

        

    else : 

        soup = BeautifulSoup(driver.page_source, "html.parser")

        table = soup.find("ul",{"class":"block-list"})

        li_s = table.find_all("li")



        driver.find_element(By.XPATH, f'//*[@id="middleColumn"]/div[2]/ul/li[1]').find_element(By.TAG_NAME, 'a' ).click()

        file =  check_dowload_files(tempfolder, "pdf" )

        filePath = os.path.join(tempfolder, file)

        extention = file.split('.')[-1]



        if extention == 'xlsx' :

            df = pd.read_excel(io=filePath, sheet_name=0, header=1)

            df.columns = ['col_'+str(i) for i in range(len(df.columns))]

            df = df.fillna("")



            for i in range (len(df)):

                val_ref = ['NUIS:', 'Tel.:', 'Fax:', 'www:', 'e-mail:']

                key_ref = ['InternalID_1', 'Phone', 'Fax', 'Website', 'Email' ]



                df_sheet = pd.read_excel(io=filePath, sheet_name=i+1)

                df_sheet.columns = ['col_'+str(i) for i in range(len(df_sheet.columns))]

                df_sheet = df_sheet.fillna("")



                sqldict['Name'].append(df['col_2'][i])

                sqldict['Address_1'].append(df_sheet['col_1'][1].split(':')[-1].strip())

                sqldict['RegulationType'].append('Regulated')

                sqldict['Typology'].append('Financial Entity')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])



                for j, val in enumerate(val_ref):

                    try:

                        sqldict[key_ref[j]].append( df_sheet.iloc[list(df_sheet['col_1']).index(val),2].strip() )

                        if val == 'NUIS:' and len(df_sheet.iloc[list(df_sheet['col_1']).index(val),2].strip())!= 0:

                            sqldict['InternalID_1_type'].append('NUIS/NIPT') 

                    except:

                        sqldict[key_ref[j]].append('')    

            sqldict = bourange_same_length_array(sqldict)



        else:



            entreprise = 0

            with pdfplumber.open(filePath) as pdf:

                company ={}

                Telefon = []

                for p, page in enumerate(pdf.pages):

                    text = page.extract_text()

                    if p==0:

                        RegulationType = 'Revoked' if 'REVOKED' in text else 'Regulated'

                        count_data = [1,2] if 'REVOKED' in text else [3,4,5]

                        Revoked = True if 'REVOKED' in text else False

                    for line in text.splitlines():

                        line = line.strip()

                        check_stop= ''

                        va = patternTel.findall(line)

                        

                        if len(pattern.findall(line)) > 0 :

                            company = {'Name' : line.replace(pattern.findall(line)[0],'').strip()}

                            Telefon = []                

                        elif len(patternAddress.findall(line)) > 0 : 

                            company['Address_1'] = line.replace(patternAddress.findall(line)[0],'').strip()

                        elif len(va) > 0 and len(line.replace(va[0],'').strip()) > 0 : 

                            a = line.replace(va[0],'').strip()

                            if len(a)>2:

                                b = a[1:].strip() if a[0] ==':' else a.strip()

                                c = b[:-1] if b[-1] =='.' else b

                                Telefon.append(c)

                                company['Phone'] = Telefon

                            check_stop = va[0] if reg == 'AL BA 2' else ''

                        elif len(patternFax.findall(line)) > 0 :   

                            company['Fax'] = line.replace(patternFax.findall(line)[0],'').strip()

                        elif len(patternNUIS.findall(line)) > 0 :

                            company['InternalID_1'] = line.replace(patternNUIS.findall(line)[0],'').strip()

                        elif len(patternEmail.findall(line)) > 0 : 

                            company['Email'] = line.split(':')[-1].strip()

                            check_stop = 'Mobile'



                        if (len(company) in count_data and check_stop=='Mobile' and Revoked==False) or (len(company) in count_data and Revoked==True) :

                            entreprise+=1

                            company['Phone'] = ", ".join(company["Phone"]) if 'Phone' in company else ""

                            for keys, value in company.items():

                                sqldict[keys].append(value)

                                

                            sqldict['InternalID_1_type'].append('NUIS') if 'InternalID_1' in company else ""  

                            # sqldict['Cntry'].append('AL')

                            sqldict['ListProcessDate'].append(processdate)

                            sqldict['RegCtry'].append(reg.split()[0])

                            sqldict['RegCode'].append(reg.split()[1])

                            sqldict['ListCode'].append(reg.split()[2])

                            sqldict['RegulationType'].append(RegulationType)

                            company = {}    

                            sqldict = bourange_same_length_array(sqldict)                

                      

        os.remove(filePath)



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

#Moving the file to the output folder (this way it will be displayed in the Control Room)

sleep(3)
    
    
    