# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

import datetime

import pandas as pd

from pandas import ExcelWriter

from selenium import webdriver

from time import sleep

import os

from selenium.webdriver.common.by import By

from bs4 import BeautifulSoup



from selenium.webdriver.support.ui import Select



from selenium.webdriver.support import expected_conditions

from webdriver_manager.chrome import ChromeDriverManager



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'PT ISPT' ## change to current controller name



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

#------------------------------------------------ Begin_chromedriver ----------------------------------------

#Starting Chrome driver, set to download files in tempfolder

chromeOptions = webdriver.ChromeOptions()

prefs = {"plugins.always_open_pdf_externally": True,

		 "download.prompt_for_download": False,

		 "download.default_directory" : tempfolder}

chromeOptions.add_experimental_option("prefs",prefs)

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={

        'PT ISPT 1': 'https://www.asf.com.pt/NR/exeres/22DBA125-6663-4DDB-94AF-760C69847A19.htm?ORIGINALGUID=%7bC7E2E644-C8DC-4F8A-947B-FB7B9F64D6B9%7d&search=239187191000194149000194147005195159007194145009194149003195160084194147194148194151004194145009194144112&list=1&titCriPesq=Empresas%20de%20seguros%20nacionais%20a%20operar%20em%20Portugal',

        'PT ISPT 2': 'https://www.asf.com.pt/NR/exeres/22DBA125-6663-4DDB-94AF-760C69847A19.htm?ORIGINALGUID=%7bC7E2E644-C8DC-4F8A-947B-FB7B9F64D6B9%7d&search=239187191001194149001194147004195159006194145009194149003195160084194147194148194151004194145009194144112&list=1&titCriPesq=Empresas%20de%20seguros%20nacionais%20a%20operar%20no%20estrangeiro',

        'PT ISPT 5.1': 'https://www.asf.com.pt/NR/exeres/22DBA125-6663-4DDB-94AF-760C69847A19.htm?ORIGINALGUID=%7bC7E2E644-C8DC-4F8A-947B-FB7B9F64D6B9%7d&search=239187191001194149000194147005195159007194145008194149003195160084194147194148194151004194145009194144112&list=1&titCriPesq=Empresas%20de%20seguros%20estrangeiras%20a%20operar%20em%20Portugal%20atrav%C3%A9s%20de%20uma%20sucursal',

        'PT ISPT 5.2': 'https://www.asf.com.pt/NR/exeres/22DBA125-6663-4DDB-94AF-760C69847A19.htm?ORIGINALGUID=%7bC7E2E644-C8DC-4F8A-947B-FB7B9F64D6B9%7d&search=239187191001194149000194147005195159007194145009194149002195160085194147194148194151004194145009194144112194150002&list=1&titCriPesq=Empresas%20de%20seguros%20estrangeiras%20com%20atividade',

        'PT ISPT 5.3': 'https://www.asf.com.pt/NR/exeres/22DBA125-6663-4DDB-94AF-760C69847A19.htm?ORIGINALGUID=%7bC7E2E644-C8DC-4F8A-947B-FB7B9F64D6B9%7d&search=239187191001194149000194147005195159007194145009194149002195160085194147194148194151004194145009194144112194150003&list=1&titCriPesq=Empresas%20de%20seguros%20estrangeiras%20sem%20atividade',

        'PT ISPT 8': 'https://www.asf.com.pt/NR/exeres/BA715C18-1D62-4448-84E0-8C80B64C8691.htm',

        'PT ISPT 9': 'https://www.asf.com.pt/NR/exeres/3DCB6032-0C4A-4F1E-95CA-1502D724C4C8.htm'

        }



Typology={

        'PT ISPT 1': 'Portuguese Insurance Undertakings',

        'PT ISPT 2': 'Portuguese Insurance Undertakings abroad',

        'PT ISPT 5.1': 'Foreign Undertakings in Portugal',

        'PT ISPT 5.2': 'Foreign Undertakings in Portugal',

        'PT ISPT 5.3': 'Foreign Undertakings in Portugal',

        'PT ISPT 8': 'Pension Funds Management Societies',

        'PT ISPT 9': 'Fundos de Pensões'

        }



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

          'Phone - Mother company': [], 'Check': []}



contactData = ['Name', 'Address', 'Phone', 'E-Mail', 'Website', 'Registration number', 'Commercial Register No.']

processdate = now.strftime('%Y-%m-%d')



# %%

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



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")



    driver.get(regdict[reg])

    BLANK_HTML = '<html><head></head><body></body></html>'

    if driver.page_source == BLANK_HTML:  # If a blank page is shown, break the loop

        print("Blank page displayed for {}".format(reg))

    else:

        if reg in ['PT ISPT 1', 'PT ISPT 2', 'PT ISPT 5.1', 'PT ISPT 5.2']:

            link_results = driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr > td > a")

            links = [elem.get_attribute("href") for elem in link_results]

            names = [elem.text for elem in link_results]

            codes = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(1)")]

            auth_types = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(3)")]

            home_ctries = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(4)")]



            for i, link in enumerate(links):

                print(f"[INFO] : -- webPage {i+1}/{len(links)} | {reg} ")



                driver.get(link)

                tries = 0

                while driver.page_source == BLANK_HTML and tries <= 10:

                    # Try reloading page for 10 times if page is blank (sometimes page is blank)

                    tries += 1

                    driver.get(link)



                try:

                    activity = driver.find_element(By.ID, "lblActuacao").text



                    if reg in ['PT ISPT 1', 'PT ISPT 2']:

                        addr = driver.find_element(By.ID, "lblSede").text



                    elif reg == 'PT ISPT 5.1':

                        addr = driver.find_element(By.ID, "lblEscritorio").text



                    else:  # reg == 'PT ISPT 5.2'

                        addr = driver.find_element(By.ID, "lblPaisProveniencia").text



                except:

                    print(" || Blank page")

                    activity = "NA"

                    addr = "NA"



                sqldict['Name'].append(names[i])

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(codes[i])

                sqldict['Address_1'].append(addr)

                sqldict['Cntry'].append(home_ctries[i])

                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

            sqldict = bourange_same_length_array(sqldict)



        elif reg in ['PT ISPT 5.3']:



            link_results = driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr > td > a")

            links = [elem.get_attribute("href") for elem in link_results]

            names = [elem.text for elem in link_results]

            auth_types = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(2)")]

            home_ctries = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(3)")]



            for i, link in enumerate(links):

                print(f"[INFO] : -- webPage {i+1}/{len(links)} | {reg} ")



                if names[i] == "":

                    continue



                driver.get(link)

                tries = 0

                while driver.page_source == BLANK_HTML and tries <= 10:

                    # Try reloading page for 10 times if page is blank (sometimes page is blank)

                    driver.get(link)

                    tries += 1

                

                try:

                    activity = driver.find_element(By.ID, "lblActuacao").text

                except:

                    print(" || Blank page")

                    activity = "NA"

                

                sqldict['Name'].append(names[i])

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(codes[i])

                #sqldict['Address_1'].append(addr)

                sqldict['Cntry'].append(home_ctries[i])

                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

            sqldict = bourange_same_length_array(sqldict)



        elif reg == 'PT ISPT 8':

            # Sociedades Gestoras de Fundos de Pensões

            sgfp_codes = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#dgSGFP > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(1)")]

            sgfp_names = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#dgSGFP > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(2)")]

            sgfp_addrs = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#dgSGFP > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(3)")]



            for i in range(len(sgfp_codes)):

                print(f"[INFO] : -- webPage {i+1}/{len(sgfp_codes)} | {reg} ")

                entity_type = "Sociedades Gestoras de Fundos de Pensões"



                sqldict['Name'].append(sgfp_names[i])

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(sgfp_codes[i])

                sqldict['Address_1'].append(sgfp_addrs[i])

                #sqldict['Typology'].append(Typology[reg])

                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

            sqldict = bourange_same_length_array(sqldict)



            # Empresas Seguradoras

            es_codes = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#dgSeguradoras > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(1)")]

            es_names = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR, "table#dgSeguradoras > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(2)")]

            es_addrs = [elem.text for elem in driver.find_elements(By.CSS_SELECTOR,"table#dgSeguradoras > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(3)")]



            for i in range(len(es_codes)):

                print(f"[INFO] : -- webPage {i+1}/{len(es_codes)} | {reg} ")

                #entity_type = "Empresas Seguradoras"

                

                sqldict['Name'].append(es_names[i])

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(es_codes[i])

                sqldict['Address_1'].append(es_addrs[i])

                #sqldict['Typology'].append(Typology[reg])

                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

            sqldict = bourange_same_length_array(sqldict)



        else:  # reg == "PT ISPT 9"

            links = []

            names = []

            # Click search button

            driver.find_element(By.ID, "btnPesquisar").click()



            # Select 100 results per page

            Select(driver.find_element(By.ID, "ResultsPerPageDropDown")).select_by_visible_text("100")

            total_pages_count = int(driver.find_element(By.ID, "PageStatusLabel").text.split(" ")[-1])



            for page_num in range(total_pages_count):

                print(f"[INFO] : - Scrapping page {page_num+1}/{total_pages_count} | {reg}")

                link_results = driver.find_elements(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr > td > a")

                links += [elem.get_attribute("href") for elem in link_results]

                names += [elem.text for elem in link_results]



                if page_num < total_pages_count - 1:

                    # Go to next page

                    driver.find_element(By.ID, "GridPagerHeader_btnProximaPagina").click()



            for i, link in enumerate(links):

                print(f"[INFO] : -- webPage {i+1}/{len(links)} | {reg} ")

                driver.get(link)

                tries = 0

                while driver.page_source == BLANK_HTML and tries <= 10:

                    # Try reloading page for 10 times if page is blank (sometimes page is blank)

                    tries += 1

                    driver.get(link)

                name = names[i]



                try:

                    code = driver.find_element(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(1)").text

                    entity_mgr = driver.find_element(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(2)").text

                    addr = driver.find_element(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(3)").text

                    entity_type = driver.find_element(By.CSS_SELECTOR, "table#SearchResultsGrid > tbody > tr[style='font-family:Arial;font-size:10pt;'] > td:nth-child(4)").text

                except:

                    print(" || Blank page")

                    code = "NA"

                    entity_mgr = "NA"

                    addr = "NA"

                    entity_type = "NA"

                    

                sqldict['Name'].append(names[i])

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(code)

                sqldict['Address_1'].append(addr)

                sqldict['Typology'].append(entity_type)

                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                sqldict['RegCtry'].append(reg.split(' ')[0])

                sqldict['RegCode'].append(reg.split(' ')[1])

                sqldict['ListCode'].append(reg.split(' ')[-1])

            sqldict = bourange_same_length_array(sqldict)

            



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)


    