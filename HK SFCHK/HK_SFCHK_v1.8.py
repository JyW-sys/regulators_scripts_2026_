# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from selenium import webdriver

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

import pandas as pd

from time import sleep

import datetime

from bs4 import BeautifulSoup

from pandas import ExcelWriter

import os



from selenium.webdriver.support import expected_conditions

#from webdriver_manager.chrome import ChromeDriverManager





# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'HK SFCHK' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.5")

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



#driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=chromeOptions )

#driver = webdriver.Chrome(executable_path="..\\chromedriver.exe",options=chromeOptions)

driver = webdriver.Chrome(options=chromeOptions)

driver.maximize_window()



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------

regdict={

         'HK SFCHK 1':'//*[@id="radiofield-1022-inputEl"]' , 

         'HK SFCHK 2': '//*[@id="radiofield-1023-inputEl"]', 

         'HK SFCHK 3': '//*[@id="radiofield-1024-inputEl"]', 

         'HK SFCHK 4': '//*[@id="radiofield-1025-inputEl"]', 

         'HK SFCHK 5': '//*[@id="radiofield-1026-inputEl"]', 

         'HK SFCHK 6': '//*[@id="radiofield-1027-inputEl"]', 

         'HK SFCHK 7': '//*[@id="radiofield-1028-inputEl"]', 

         'HK SFCHK 8': '//*[@id="radiofield-1029-inputEl"]', 

         'HK SFCHK 9': '//*[@id="radiofield-1030-inputEl"]', 

         'HK SFCHK 10': '//*[@id="radiofield-1031-inputEl"]',

         }



Typology={'HK SFCHK 1':'Dealing in securities' , 'HK SFCHK 2': 'Dealing in futures contracts', 'HK SFCHK 3': 'Leveraged foreign exchange trading', 

         'HK SFCHK 4': 'Advising on securities', 'HK SFCHK 5': 'Advising on futures contracts', 'HK SFCHK 6': 'Advising on corporate finance', 

         'HK SFCHK 7': 'Providing automated trading services', 'HK SFCHK 8': 'Securities margin financing', 'HK SFCHK 9': 'Asset management', 

         'HK SFCHK 10': 'Providing credit rating services'}





sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],

          'Phone - Mother company': [], 'Check': []}



letters = [f'//*[@id="boundlist-1074-listEl"]/ul/li[{value}]' for value in range(1, 37)]

letters2= [f'//*[@id="boundlist-1086-listEl"]/ul/li[{value}]' for value in range(1, 37)]



processdate = now.strftime('%Y-%m-%d')



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------

def wait_for_section(index_link, list_corporation, partial_url, div_id=None):

    for rang in range(1, 20):

        driver.get(list_corporation['links'][index_link].replace('details', partial_url))

        print(f"[INFO] : -- load tab '{partial_url.upper()}'. URL={list_corporation['links'][index_link].replace('details', partial_url)} ")

        sleep(rang*0.5)

        soup_ = BeautifulSoup(driver.page_source, 'html.parser')



        try:

            if (partial_url != 'details') and driver.find_element(By.XPATH, '//*[@id="gridaddress"]').is_displayed() :

                #print(f'partir a l omglet {partial_url}')

                break

        except:

            pass

       

        if div_id is not None:

            if soup_.find('div', {'id':div_id}) is not None:

                #print(f'Existe  = {div_id}')

                break

    else:

        print(f"[ERROR] : HK SFCHK - Failed. dot not find tag <div id='{div_id}'> in  URL= {list_corporation['links'][index_link].replace('details', partial_url)}")

    return soup_



def get_entities(webdriver):

    entities_soup = BeautifulSoup(driver.page_source, 'html.parser')

    entity_table=entities_soup.find('table', {'class':'x-grid-table x-grid-table-resizer'})

    entities  = entity_table.find_all('tr', {'class' : 'x-grid-row'}) #+ entity_table.find_all('tr', {'class' : 'x-grid-row x-grid-row-alt'})

    entities = [ent for ent in entities if len(ent.text.strip())>0]

    return entities





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



def click_element(driver, XPATH, Msg=None):

    for time in range(10):

        try:

            driver.find_element(By.XPATH, XPATH).click()

            if Msg==None:

                print("[INFO] : - Select letter/Number = '",  f"{driver.find_element(By.XPATH, XPATH).text}'")

            else:

                print(f"[INFO] : - {Msg}")

            break

        except:

            print(f"[ERROR] : - Retrying {time+1}/10 to click element in this page: {XPATH} ")

            sleep(1)    

    else:

        raise Exception('[ERROR] : Failed to get presence for this element in this page:')





# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")



    list_corporation = {'reference':[], 'name':[], 'officer':[], 'chname':[], 'address':[], 'active':[], 'links':[]}

    driver.get("https://www.sfc.hk/publicregWeb/searchByRa?locale=en")

    soup0=BeautifulSoup(driver.page_source, 'html.parser')

    lastupdate=soup0.find("p", {"class":"last_updated"}).text.split(":")[1].strip()

   

    for letter in range(len(letters)):

        tableispresent = ''

        click_Corporation = click_element(driver,'//*[@id="roleTypeCorporation-inputEl"]', "Select 'Corporation' in 'Type of licensee'")

        click_Active_and_inactive = click_element(driver,'//*[@id="radiofield-1016-inputEl"]', "Select 'Active and inactive' in 'Licence/Registration status'")

        click_Type= click_element(driver,regdict[reg])

        click_letter_menu = click_element(driver,'//*[@id="ext-gen1092"]', "Unroll list letter/Number")

        sleep(1)



        try:

            selcet_letter = click_element(driver,letters[letter])

            sleep(0.5)

        except:

            try :

                selcet_letter = click_element(driver,letters2[letter])

                sleep(0.5)

            except :

                Exception(f'[ERROR] : - failed to click letter/Number N*_"{letter}"')

        

        Search=click_element(driver,'//*[@id="button-1012"]', "Click 'Search' button")

        sleep(2)



        soup1 = BeautifulSoup(driver.page_source, 'html.parser')

        tableispresent = soup1.find('div', {'id': 'gridcolumn-1047'})

        displayFailMsg = driver.find_element(By.XPATH, '//*[@id="displayfield-1041-inputEl"]')

        sleep(1)



        if displayFailMsg.is_displayed():

            print(f'[INFO] : - NO DATA IN CARACTERE: {letter+1}/{len(letters)} | Regulateur: {reg} ')

        else:

            totalpages = 1

            soup2=BeautifulSoup(driver.page_source, 'html.parser')

            page_of = soup2.find('div', {'id':'tbtext-1063'})



            if page_of is not None and 'of' in page_of.text and '0' not in page_of.text:#we have 'of 0' page when the table is not fully loaded the first time

                totalpages = int(page_of.text.replace('of ',''))



            for page in range(1, totalpages+1):

                

                #print(f"[INFO] : - Scrapping page {page}/{totalpages} | Character: {letter+1}/{len(letters)} | {reg}")

                

                soupPage = BeautifulSoup(driver.page_source, 'html.parser')

                range_entities = soupPage.find('div', {'id': 'tbtext-1070'}).text.strip().split(' of')[0].split('Item ')[1]

                entities = get_entities(driver)

             

                for tr in entities:

                    tds=tr.find_all("td")

                    asx=tds[1].find("a", href=True)

                    list_corporation['links'].append('https://www.sfc.hk'+asx['href'])

                    list_corporation['reference'].append(tds[0].text.strip())

                    list_corporation['name'].append(tds[1].text.strip())

                    list_corporation['chname'].append(tds[2].text.strip())

                    list_corporation['address'].append(tds[5].text.strip())

                    list_corporation['active'].append(tds[6].text.strip())



                if page != totalpages:

                    nextpage=click_element(driver,'//*[@id="button-1065-btnIconEl"]', f"click page {page}/{totalpages} | Character: {letter+1}/{len(letters)} | {reg}")

                    

                    for rang in range(10):

                        new_range_entities = BeautifulSoup(driver.page_source, 'html.parser').find('div', {'id': 'tbtext-1070'}).text.strip().split(' of')[0].split('Item ')[1]

                        if range_entities  != new_range_entities:

                            break

                        sleep(2)



        #         if page == 1:

        #             break

        

        # if letter == 1:

        #     break

         

    for link in range(len(list_corporation['links'])):

        dateoflic=''

        xemail = ''

        xweb = ''

        

        print(f'[INFO] : -- Scrapping link {link+1}/{len(list_corporation["links"])} | _({reg})_')



        sqldict['Typology'].append(Typology[reg])

        sqldict['Name'].append(list_corporation['name'][link])

        sqldict['InternalID_1'].append(list_corporation['reference'][link])

        sqldict['InternalID_1_type'].append('CE Reference')

        sqldict['Cntry'].append('HK')

        sqldict['ListProcessDate'].append(processdate)

        sqldict['RegCtry'].append(reg.split()[0])

        sqldict['RegCode'].append(reg.split()[1])

        sqldict['ListCode'].append(reg.split()[2])



        if 'Yes' in list_corporation['active'][link]:

            sqldict['RegulationType'].append('Licensed')

        else:

            sqldict['RegulationType'].append('Inactive License')





        addr = list_corporation['address'][link]

        if len(addr.split(','))>2:

            sqldict['Address_1'].append(','.join(addr.split(',')[:-2]).strip())

            sqldict['Address_2'].append(addr.split(',')[-2].strip())

            sqldict['City'].append(addr.split(',')[-1].strip())

        elif len(addr.split(','))==2:

            sqldict['Address_1'].append(','.join(addr.split(',')[0]).strip())

            sqldict['Address_2'].append('')

            sqldict['City'].append(addr.split(',')[1].strip())

        else:

            sqldict['Address_1'].append(addr)

            sqldict['Address_2'].append('')

            sqldict['City'].append('')

        

       

        soup4 = wait_for_section(link, list_corporation, 'details', 'gridradetail-body')

        sleep(0.5)

        try:

            dateoflic=driver.find_element(By.XPATH,'//*[@id="displayfield-1020-inputEl"]').text.strip()

        except:

            pass

        

        sqldict['RegulationDate'].append(dateoflic)



        soup4 = wait_for_section(link, list_corporation, 'addresses') # searching for layoutDiv in html comments

        sleep(2)

        soup4=soup4.find('div', {'id':"mainContainer"})#if '@'' and no ' ' in string is an email, if 'www' in string is a web address

        if soup4 is not None and len(soup4.find_all('div'))>0:

            divs=soup4.find_all('div')

            for div in divs:

                if '@' in div.text and ' ' not in div.text.strip():

                    xemail = div.text.strip()

                if 'www.' in div.text and ' ' not in div.text.strip():

                    xweb = div.text.strip()



            sqldict['Website'].append(xweb)

            sqldict['Email'].append(xemail)

        else:

            sqldict['Website'].append('')

            sqldict['Email'].append('')

          

        # if link == 3:

        #     break



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
    