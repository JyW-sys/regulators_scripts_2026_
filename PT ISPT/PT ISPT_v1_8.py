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

from selenium.webdriver.common.keys import Keys

from selenium.webdriver.support.ui import Select

from selenium.webdriver.support import expected_conditions

from webdriver_manager.chrome import ChromeDriverManager

# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'PT ISPT' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.8")

now=datetime.datetime.now()

filename = '{} data {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])
#scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

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

        'PT ISPT 1': 'https://www.asf.com.pt/autoriza%C3%A7%C3%B5es-e-registos/empresas-de-seguros',

        'PT ISPT 2': 'https://www.asf.com.pt/autoriza%C3%A7%C3%B5es-e-registos/empresas-de-seguros',

        'PT ISPT 5': 'https://www.asf.com.pt/autoriza%C3%A7%C3%B5es-e-registos/empresas-de-seguros',

        'PT ISPT 8': 'https://www.asf.com.pt/entidadesgestoras',

        'PT ISPT 9': 'https://www.asf.com.pt/autoriza%C3%A7%C3%B5es-e-registos/fundos-de-pens%C3%B5es/entidades-autorizadas'

        }



Typology={

        'PT ISPT 1': 'Portuguese Insurance Undertakings',

        'PT ISPT 2': 'Portuguese Insurance Undertakings abroad',

        'PT ISPT 5': 'Foreign Undertakings in Portugal',

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
    
    
def click_on_cookies(web_driver):

    try:

        web_driver.find_element(By.XPATH,f'//*[@id="asfCookiesBtn"]').click()
        print('[Success] : Success to Click Cookie')

    except Exception as err:

        print('[ERROR] : Failed to click "I Accept" button on the cookies banner:', err)
        
      
def click_element_by_xpath(driver, xpath):

    # Find the element and click

    element = driver.find_element(By.XPATH, xpath)

    element.click()


# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):

    print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")



    driver.get(regdict[reg])
    
    data_dict = {'Número':[], 'Nome':[], 'Tipo de Autorização':[], 'País Sede':[]}

    BLANK_HTML = '<html><head></head><body></body></html>'
    
    address_link = []
    
    if k == 0:
        soup = BeautifulSoup(driver.page_source,'html.parser')
        
        if soup.find('button', {'id':'asfCookiesBtn'}):
        
            click_on_cookies(driver)

    if driver.page_source == BLANK_HTML:  # If a blank page is shown, break the loop

        print("Blank page displayed for {}".format(reg))

    else:
        
        sleep(3)

        if reg == 'PT ISPT 1':
            
            click_element_by_xpath(driver, '//*[@id="EmpresasNacOperarEst"]')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[3]/div[1]/label')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[3]/div[2]/label')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[3]/div[3]/label')
            sleep(2)
            
            click_element_by_xpath(driver, '//*[@id="EmpresasEstOperarPT"]')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[5]/div[1]/label')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[5]/div[2]/label')
            # click_element_by_xpath(driver, '//*[@id="filterForm"]/div[5]/div[3]/label')
            sleep(2)
        
        elif reg == 'PT ISPT 2':
            driver.maximize_window()
            soup = BeautifulSoup(driver.page_source,'html.parser')
            #click_element_by_xpath(driver,'//*[@id="clear-inputs"]')
            click_element_by_xpath(driver,'//*[@id="iNacPortugal"]')
            click_element_by_xpath(driver,'//*[@id="EmpresasEstOperarPT"]')
            
        elif reg == 'PT ISPT 5':
            soup = BeautifulSoup(driver.page_source,'html.parser')
            #click_element_by_xpath(driver,'//*[@id="clear-inputs"]')
            click_element_by_xpath(driver,'//*[@id="iNacPortugal"]')
            click_element_by_xpath(driver,'//*[@id="EmpresasNacOperarEst"]')
            
        elif reg == 'PT ISPT 8':
            soup = BeautifulSoup(driver.page_source,'html.parser')
        elif reg == 'PT ISPT 9':
            driver.maximize_window()
            soup = BeautifulSoup(driver.page_source,'html.parser')
        
        MultiPage = True

        pages =[]

        pagination = soup.find('div', {'class': 'dataTables_paginate paging_full_numbers'})

        sleep(3)
        
        if len(pagination)>0:

            for span in pagination.find_all('span'):
                a = span.find_all('a')
                if a != []:
                    a_txt = a[-1].text
            total_pages = a_txt

        else:

            MultiPage = False

            total_pages=1
            
        for page in range(int(total_pages)):
            
            soup = BeautifulSoup(driver.page_source,'html.parser')
        
            if reg == 'PT ISPT 8':
                table = soup.find_all('table')[1].find('tbody')
            else:
                table = soup.find('tbody')

            trs = table.find_all('tr', {'class':'odd'}) + table.find_all('tr', {'class':'even'})

            for tr in trs :
                
                if reg == "PT ISPT 1" or reg == "PT ISPT 2" or reg == "PT ISPT 5": 
                        
                    address_link.append('https://www.asf.com.pt/entidade-gestora?seguradora='+tr.find('td').text)
                    
                elif reg == "PT ISPT 9":
                    
                    address_link.append('https://www.asf.com.pt/web/site-asf/fundo?cf='+tr.find('td').text+'&tipoPesquisa=1')

                #InternalID_1 =  data_dict['Número'].append( tr.find('td').text)

                #Name = data_dict['Nome'].append( tr.find_all('td')[1].text)

                #TypeOfAuto = data_dict['Tipo de Autorização'].append( tr.find_all('td')[2].text)

                #Cntry = data_dict['País Sede'].append(tr.find_all('td')[3].text)
                
                sqldict['Name'].append(tr.find_all('td')[1].text)

                sqldict['InternalID_1_type'].append('Entity Code')

                sqldict['InternalID_1'].append(tr.find('td').text)

                #sqldict['Address_1'].append(addr)      
                
                if reg == 'PT ISPT 8':
                    sqldict['Address_1'].append(tr.find_all('td')[2].text)
                    sqldict['City'].append(tr.find_all('td')[2].text.split(' ')[-1])
                    sqldict['Typology'].append('')
                elif reg =='PT ISPT 9':
                    sqldict['Typology'].append(tr.find_all('td')[5].text)
                else:
                    sqldict['Typology'].append(tr.find_all('td')[2].text)
                    sqldict['Cntry'].append(tr.find_all('td')[3].text)
                
                sqldict['RegulationType'].append('Authorised')

                sqldict['ListProcessDate'].append(processdate)

                #sqldict['RegCtry'].append(reg.split(' ')[0])

                #sqldict['RegCode'].append(reg.split(' ')[1])

                #sqldict['ListCode'].append(reg.split(' ')[-1])
                sqldict['RegCtry'].append('PT')

                sqldict['RegCode'].append('ISPT')

                sqldict['ListCode'].append(reg.split(' ')[-1])
                

            if soup.find('a', {'class':'paginate_button next disabled'}):
                print("--INFO-- SCRAPING " + str(page+1))
                print("Last page scrapping done")
                break
            else:
                print("--INFO-- SCRAPING " + str(page+1))
                paginate = soup.find('div',{'empresas-seguros_paginate'})
                
                # try:
                #     click_element_by_xpath(driver,'//*[@class="paginate_button next"]')
                # except:
                #     sleep(1)
                #     click_element_by_xpath(driver,'//*[@id="empresas-seguros_next"]')
                try:
                    sleep(2)
                    driver.minimize_window()
                    # NextPages = driver.find_element(By.XPATH, f'//*[@class="dataTables_paginate paging_full_numbers"]//*/a[contains(text(),"{page+1}")]')
                    # NextPage = NextPages.find_element(By.XPATH, "following-sibling::*[1]")
                    # NextPage.click()
                    click_element_by_xpath(driver,'//*[@class="paginate_button next"]')

                    sleep(0.5)

                except:
                    driver.maximize_window()
                    
                    element = driver.find_element(By.XPATH, '//*[@id="empresas-seguros"]/tbody')
                    driver.execute_script("arguments[0].scrollIntoView();", element)
                    print('Try to Scoll Screen ')
                    click_element_by_xpath(driver,'//*[@class="paginate_button next"]')
                    print('Try to Click Next Page ')
                    sleep(0.5)
                    #driver.minimize_window()
                    # NextPages = driver.find_element(By.XPATH, f'//*[@class="dataTables_paginate paging_full_numbers"]//*/a[contains(text(),"{page+1}")]')
                    # NextPage = NextPages.find_element(By.XPATH, "following-sibling::*[1]")
                    # NextPage.click()
                    print('Success to fix ')
                    
        if reg == "PT ISPT 1" or reg == "PT ISPT 2" or reg == "PT ISPT 5":        
            driver_inner = webdriver.Chrome(options=chromeOptions)
            driver_inner.maximize_window()
            
            i = 0
            for link in address_link:
                
                i+=1
                print(f"[INFO] : -- Adress info | {reg} | {i}/{len(address_link)} |{link[-4:0]} ")
                
                driver_inner.get(link)
                try:
                    click_on_cookies(driver_inner)
                except:
                    print('Failed to Click to Cookies')
                
                sleep(5)
                
                try:
                    soup_inner = BeautifulSoup(driver_inner.page_source,'html.parser')
                    Address = soup_inner.find('p', {'class':'asf-entidade__info_address'}).text
                   
                    if Address == '':
                        Address = soup_inner.find('p', {'class':'asf-entidade__info_representation'}).text
                    
                    sqldict['Address_1'].append(Address)
                    sqldict['City'].append(Address.split(' ')[-1])
                    
                
                except:
                    driver_inner.refresh()
                    sleep(10)
                    soup_inner = BeautifulSoup(driver_inner.page_source,'html.parser')
                    Address = soup_inner.find('p', {'class':'asf-entidade__info_address'}).text
                    
                    if Address == '':
                        try:
                            Address = soup_inner.find('p', {'class':'asf-entidade__info_representation'}).text
                        except:
                            Address = ''
                    
                    sqldict['Address_1'].append(Address)
                    sqldict['City'].append(Address.split(' ')[-1])
                    
                    
            driver_inner.quit()
                    
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


    
    
    
    
    
    