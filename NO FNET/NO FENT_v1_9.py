# %%



#------------------------------------------------ Begin_Librairie ----------------------------------------



from selenium import webdriver



from selenium.webdriver import ActionChains



from selenium.webdriver.common.by import By



from selenium.webdriver.support.ui import WebDriverWait



from selenium.webdriver.support import expected_conditions as EC



from selenium.webdriver.common.action_chains import ActionChains



from selenium.webdriver.common.keys import Keys



from bs4 import BeautifulSoup



import pandas as pd



from time import sleep



import datetime



from pandas import ExcelWriter



import os



# %%



#------------------------------------------------ Begin_ fileName ----------------------------------------



regulatorName = 'NO FNET' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.9.0")



now=datetime.datetime.now()



filename= '{} data {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])



#scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment



scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment



os.chdir(scriptfolder)



writer = ExcelWriter(filename, engine='openpyxl')



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







def scrollinAndClick(xpath,key_press=False):



    if len(xpath) != 0 :



        for times in range(60):



            try:



                driver.find_element(By.XPATH, xpath).click()



                sleep(5)



                break



            except:



                # print(f"[ERROR] : trying {times+1}/10 to key press 'DOWN' (scrolling)")



                sleep(5)



                if key_press:                    



                    driver.find_element(By.TAG_NAME, 'body').send_keys(key_press)



        else:   



            raise Exception(f'[ERROR] : Failed scrollin Or Click on xpath element : {xpath}')

        

        

# Define a function to scroll to the bottom of the page

def scroll_to_bottom(driver):

    # Get scroll height

    last_height = driver.execute_script("return document.body.scrollHeight")



    while True:

        # Scroll down to the bottom

        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")



        # Wait to load the page

        sleep(1)



        # Calculate new scroll height and compare with last scroll height

        new_height = driver.execute_script("return document.body.scrollHeight")

        if new_height == last_height:

            break

        last_height = new_height



def wait_for_pagination_update(driver, old_page_num):

    while True:

        # Wait for a short period to allow the page to update

        sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        pagination = soup.find('div', {'aria-label': 'Load more'})

        if pagination:

            new_page_num = pagination.find('div').text.split('of')[0]

            if new_page_num != old_page_num:

                break

# Define a function to click an element by xpath

def click_element_by_xpath(driver, xpath):

    # Find the element and click

    element = driver.find_element(By.XPATH, xpath)

    element.click()

    

    

    

# Define a function to scroll the page until the specified element is visible

def scroll_until_element_visible(driver, element_xpath):

    # Wait for the specified element to be present in the DOM

    element = WebDriverWait(driver, 15).until(

        EC.presence_of_element_located((By.XPATH, element_xpath))

    )

    

    # Scroll the page until the specified element is in view

    driver.execute_script("arguments[0].scrollIntoView();", element)



# %%



# %%

#------------------------------------------------ Begin_Variable ----------------------------------------



Reports = {"Banking and finance":"https://www.finanstilsynet.no/en/finanstilsynets-registry/user-defined-report/?group=11",



           "Debt collection":"https://www.finanstilsynet.no/en/finanstilsynets-registry/user-defined-report/?group=5",



           "Insurance and pensions":"https://www.finanstilsynet.no/en/finanstilsynets-registry/user-defined-report/?group=2",



           "Insurance mediation":"https://www.finanstilsynet.no/en/finanstilsynets-registry/user-defined-report/?group=1",



           }







regdict = {"Banking and finance"       : {'Bank'                   : ['NO FNET 8', '//*[@id="BANK_chkbx"]'], 



                                           'Payment institution'     : ['NO FNET 7', '//*[@id="BETF_chkbx"]'], 



                                           'E-money institution'     : ['NO FNET 4', '//*[@id="EPENGEF_chkbx"]'], 



                                           'Holding company'         : ['NO FNET 6', '//*[@id="FINANSKONS_chkbx"]'], 



                                           'Finance company'         : ['NO FNET 5', '//*[@id="FINF_chkbx"]'], 



                                           'Trust'                   : ['NO FNET 10', '//*[@id="FINSTIFT_chkbx"]'], 



                                           'Savings bank foundation' : ['NO FNET 9', '//*[@id="SPBAST_chkbx"]'],



                                           },



            "Debt collection"           : {'Agency debt collection on behalf of others'        : ['NO FNET 11', '//*[@id="FREMINKASO_chkbx"]'],



                                            'Debt collection agency - purchase and collection' : ['NO FNET 13', '//*[@id="OPPEGENINF_chkbx"]'],



                                          },



            "Insurance and pensions"    : {'Municipal pension fund'       : ['NO FNET 19', '//*[@id="KOMMPENKAS_chkbx"]'], 



                                           'Life insurance company'       : ['NO FNET 17', '//*[@id="LIVSFORSIK_chkbx"]'], 



                                           'Pension foundation'           : ['NO FNET 21', '//*[@id="PENFOND_chkbx"]'], 



                                           'Marine insurance association' : ['NO FNET 18', '//*[@id="SJØTRYGDEL_chkbx"]'], 



                                           'Non-life insurance company'   : ['NO FNET 20', '//*[@id="SKADEFORSI_chkbx"]'], 



                                           'Private pension fund'         : ['NO FNET 22', '//*[@id="PRIVPENKAS_chkbx"]'],



                                           },



            "Insurance mediation"       :{'Ancillary agent activities' : ['NO FNET 23', '//*[@id="AKSFORAGV_chkbx"]'], 



                                          'Insurance agency'           : ['NO FNET 24', '//*[@id="FORAGNTFTK_chkbx"]'], 



                                          'Insurance brokerage firm'   : ['NO FNET 26', '//*[@id="FORMGLFTK_chkbx"]'], 



                                          'Reinsurance brokerage firm' : ['NO FNET 27', '//*[@id="GFORMGLFTK_chkbx"]'],



                                         }



            }







regdict__={   #'NO FNET 1':['Agent of payment institution (company)], 



            ##'NO FNET 14':['Estate agency, Act adopted on 29 June 2007'],



            #'NO FNET 25':['Insurance agent register'],



            #'NO FNET 30':['Infrastructure firm'],



            ##'NO FNET 31':['Investment firm']



        }







operation_type = {'Finanstilsynet':'//*[@id="virksomhet-type-norway"]',



                  'Cross-border':'//*[@id="virksomhet-type-gov"]'}       







sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],



          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],



          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],



          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],



          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],



          'Phone - Mother company': [], 'Check': []}







processdate = now.strftime('%Y-%m-%d')



# %%



#------------------------------------------------ Begin_Main ----------------------------------------



for i, category in enumerate(Reports):



    links = []



    print(f'[INFO] : Working with category {i+1}/{len(Reports)} : {category} ')



    driver.get(Reports[category])



    sleep(1)







    for k, typology in enumerate(regdict[category]):



        reg = regdict[category][typology][0]



        xpath = regdict[category][typology][1]



        scrollinAndClick(xpath,key_press=Keys.DOWN)







    print(f'[INFO] : Select {len(regdict[category])} checkbox [x] ')



    sleep(3)



    scrollinAndClick('//button[@aria-label="Include license provider types"]',key_press=Keys.DOWN)



    scrollinAndClick('//*[@id="Licensed"]',key_press=Keys.DOWN)



    sleep(3)







    LastPage = False



    while True:



        soup = BeautifulSoup(driver.page_source, "html.parser")



        sleep(3)

        scroll_until_element_visible(driver, "//div[@role='region' and @aria-label='Load more']")



        try:

            pagination = soup.find('div', {'aria-label': 'Load more'})

        except:

            sleep(3)

            scroll_until_element_visible(driver, "//div[@role='region' and @aria-label='Load more']")

            pagination = soup.find('div', {'aria-label': 'Load more'})

        

        try:

            total_pages=pagination.find('div').text.split('of')[1]

        except:

            sleep(3)

            scroll_until_element_visible(driver, "//div[@role='region' and @aria-label='Load more']")

            pagination = soup.find('div', {'aria-label': 'Load more'})

            total_pages=pagination.find('div').text.split('of')[1]

        try:

            Num_page = pagination.find('div').text.split('of')[0]

        except:

            sleep(3)

            scroll_until_element_visible(driver, "//div[@role='region' and @aria-label='Load more']")

            pagination = soup.find('div', {'aria-label': 'Load more'})

            total_pages=pagination.find('div').text.split('of')[1]

            Num_page = pagination.find('div').text.split('of')[0]



        print(f"[INFO] : - Scrapping web {Num_page}/{total_pages}")



        #------



        div = soup.find_all('div', {'class': 'p-6 bg-white-400 mb-3'})



        links = links +  ['https://www.finanstilsynet.no/'+item.find('a')['href'] for item in div]



        #------



        NextPage = pagination.find_all('button')[1]



        if "btn--disabled" in NextPage.attrs['class'] :



            print("Bouton desactivr")



            LastPage = True



            break



        elif "btn--secondary" in NextPage.attrs['class'] :



            scrollinAndClick("//span[contains(text(),'Next')]",key_press=Keys.DOWN)



            sleep(2)



    



        # if LastPage or Num_page == 'Page 3 ':



        #     break







    for j, link in enumerate(links) :



        print(f"[INFO] : -- Company {j+1}/{len(links)} | category {i+1}/{len(Reports)}  : {category} ")



        driver.get(link)



        sleep(1)







        labels = ['Organisation number', 'Lei code', 'Address', 'Links']



        values = ['', '', '', '']



        soup = BeautifulSoup(driver.page_source, "html.parser")



        mainData = soup.find('div', {'class':'bg-white-400 p-6 mb-6'})



        data1 = mainData.find_all('li')



        data2 = mainData.find_all('div', {'class':'py-3 lg:px-6'})







        for n, item in enumerate(data2):



            try :



                label = item.find('h2').text



            except:



                label = item.find('h3').text



            if label in labels :



                if label == 'Links' :



                    values[3] = item.find('a')['href']



                else:



                    values[labels.index(label)] = item.find('p').text





     

        

        if len(data1)==4:

            try:

                typo = data1[1].find_all('span')[1].text

                regdict[category][typo][0].split(' ')[-1]

                for li in data1:

                    spans = li.find_all('span')

                    for span in spans:

                        if ('location_pin' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("city: ",next_span.text)

                                sqldict["City"].append(next_span.text)

                        if ('public' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("county:",next_span.text)

                                sqldict["Cntry"].append(next_span.text)

                    

            except:

                sections =  soup.find_all('section', {'class':'bg-white-400 p-6 lg:px-12 lg:py-9 border border-l-8 border-bluegreen-200 mb-6 relative'})

                

                for i in range(len(sections)):

                    

                    typo = sections[i].find('h2').text

                    

                    

                    if (typo in regdict[category]):

                        print(typo)

                        print(regdict[category][typo][0].split(' ')[-1])

                        break

                    

                

                for li in data1:

                    spans = li.find_all('span')

                    for span in spans:

                        if ('location_pin' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("city: ",next_span.text)

                                sqldict["City"].append(next_span.text)

                        if ('public' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("county:",next_span.text)

                                sqldict["Cntry"].append(next_span.text)

           

        

        

        

        

        elif len(data1)==5:

            sections =  soup.find_all('section', {'class':'bg-white-400 p-6 lg:px-12 lg:py-9 border border-l-8 border-bluegreen-200 mb-6 relative'}) 

            try: 

                for i in range(len(sections)):

                    

                    typo = sections[i].find('h2').text

                    

                    

                    if (typo in regdict[category]):

                        print(typo)

                        print(regdict[category][typo][0].split(' ')[-1])

                        break

            

            except:

                typo = sections[1].find('h2').text 

            

            for li in data1:

                    spans = li.find_all('span')

                    for span in spans:

                        if ('location_pin' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("city: ",next_span.text)

                                sqldict["City"].append(next_span.text)

                        if ('public' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("county:",next_span.text)

                                sqldict["Cntry"].append(next_span.text)

                                

        elif len(data1)==3:

            sections =  soup.find_all('section', {'class':'bg-white-400 p-6 lg:px-12 lg:py-9 border border-l-8 border-bluegreen-200 mb-6 relative'})

            try:

                typo = sections[0].find('h2').text

                if (typo in regdict[category]):

                    print(typo)

                    print(regdict[category][typo][0].split(' ')[-1])

                else:

                    for i in range(1,len(sections)):

                        typo = sections[i].find('h2').text

                        if (typo in regdict[category]):

                            print(typo)

                            print(regdict[category][typo][0].split(' ')[-1])

                            break

            except:

                for i in range(1,len(sections)):

                

                    typo = sections[i].find('h2').text

                    

                    if (typo in regdict[category]):

                        print(typo)

                        print(regdict[category][typo][0].split(' ')[-1])

                        break

                

            for li in data1:

                    spans = li.find_all('span')

                    for span in spans:

                        if ('location_pin' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("city: ",next_span.text)

                                sqldict["City"].append(next_span.text)

                        if ('public' in span):

                            print(span.text)

                            next_span = span.find_next_sibling('span')

                            if next_span:

                                print("county:",next_span.text)

                                sqldict["Cntry"].append(next_span.text)

            







        sqldict["Name"].append(mainData.find('h1').text)



        sqldict["EntryType"].append(data1[0].find_all('span')[1].text)



        sqldict["License_Type"].append(data1[0].find_all('span')[1].text)



        sqldict["Typology"].append(typo)



        # sqldict["City"].append(data1[2].find_all('span')[1].text)



        # sqldict["Cntry"].append(data1[3].find_all('span')[1].text)



        sqldict['InternalID_1'].append(values[0])



        sqldict['InternalID_1_type'].append('Organisation no.')



        sqldict['InternalID_3'].append(values[1])



        sqldict['InternalID_3_type'].append('LEI number')



        sqldict['ListProcessDate'].append(processdate)



        sqldict['RegulationType'].append('Licensed')



        sqldict['RegCtry'].append('NO')



        sqldict['RegCode'].append('FNET')



        sqldict['ListCode'].append(regdict[category][typo][0].split(' ')[-1])



        sqldict['Website'].append(values[3])



        sqldict['LEI Code'].append(values[1])



        sqldict['Address_1'].append(values[2].split('\n')[0].strip())



        sqldict['Zip'].append(values[2].split('\n')[-1].split(',')[0].strip())







        # if j == 2 :



        #     break







    sqldict = bourange_same_length_array(sqldict)



    # if i == 0:



    #     break



# %%



#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------



os.chdir(scriptfolder)



df=pd.DataFrame(sqldict)



df.to_excel(writer, 'SQL Ready', index=False)



writer.save()



writer.close()



driver.quit()



sleep(3)








    
    