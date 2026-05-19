import os
import re
import string
import requests
import pandas as pd 
from time import sleep
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from pandas import ExcelWriter
from selenium.webdriver.chrome.options import Options
from urllib.request import urlparse, urljoin
import numpy as np


'''
Specify the options of the webdriver to enable it to open the files in the browser and allow download when necessary,
at the end, we specify that the web driver should open the windows to its maximum size to allow us to see the computation on the web browser.
'''
now = datetime.now()

current_date = datetime.today().strftime('_%Y-%b-%d_')
current_time_1 = now.strftime("_%H-%M-%S")

if not os.path.exists('download_folder' + current_date + current_time_1): os.mkdir('download_folder' + current_date + current_time_1)

download_dir = os.getcwd() + '\download_folder' + current_date + current_time_1

options = Options()
options.add_experimental_option("prefs", {
  "download.default_directory": download_dir,
  "download.prompt_for_download": False,
  "download.directory_upgrade": True,
  "safebrowsing.enabled": True,
    "plugins.always_open_pdf_externally": True
})
options.add_argument("--start-maximized")#maximize the size of the browser's windows
driver = webdriver.Chrome(options=chromeOptions)


# In[3]:


'''
Create a dictionary with the name of the regulator and the link to its a web page as value
Create an excel sheet through ExcelWriter that has as name a unique string created on the base of time and the regulator's identifier
'''

regCodes = ['AU_APRA_1', 'AU_APRA_2', 'AU_APRA_3', 'AU_APRA_4', 'AU_APRA_5', 'AU_APRA_6', 'AU_APRA_7', 'AU_APRA_11']
regDict = {'AU_APRA_1':'https://www.apra.gov.au/register-authorised-deposit-taking-institutions', 'AU_APRA_2':'https://www.apra.gov.au/register-general-insurance', 'AU_APRA_3':'https://www.apra.gov.au/register-general-insurance', 'AU_APRA_4':'https://www.apra.gov.au/register-general-insurance', 'AU_APRA_5':'https://www.apra.gov.au/register-non-operating-holding-companies', 'AU_APRA_6':'https://www.apra.gov.au/registers-of-life-insurance-companies-and-friendly-societies', 'AU_APRA_7':'https://www.apra.gov.au/registers-of-life-insurance-companies-and-friendly-societies', 'AU_APRA_11':'https://www.apra.gov.au/list-institutions-offering-retirement-savings-accounts'}

print('Running AU_APRA Web scrapping tool')

now = datetime.now()
filename = 'AU APRA data {}.xlsx'.format(str(now).replace(':','.')[:-7])

os.chdir(os.getcwd()) #first this to create the excel file

writer = ExcelWriter(filename)

os.chdir(download_dir) #second this to work on the download folder
# In[4]:


def init_dict(dict_headers):
    dict_container = {}
    #dict_headers = ['Name','category','link']
    for header in dict_headers: dict_container[header] = {}
    return dict_container
def getHeaders(ths):
    headers = [th.text for th in ths.children if th.name == "th"]
    return headers


# In[7]:


'''
Use the webdriver to access the web page of the regulator through the link stored in the dictionary earlier
Use the BeautifulSoup library to retrieve the html tree with a parser and use the resulting bs4_object to access element with the "li" tag
'''
#regind = 'AU_APRA_1'
k = 0
kk = 0
for regind in regCodes:
    print('Working with {}.'.format(regind))
    driver.get(regDict[regind])
    sleep(1)
    htmlCode = driver.page_source
    soup = BeautifulSoup(htmlCode, "html.parser")
    # get the right section from the html tree parser
    section_container = soup.find("section",{"class":"section"})
    main_container = section_container.find("div",{"class":"section__content"})
    
    # initialize the dictionary that will store the institutions, their category and the eventual links to files
    #dict_container = {}
    dict_headers = ['Name','category','link']
    #for header in dict_headers: dict_container[header] = {}
    dict_container = init_dict(dict_headers)
    
    childs = main_container.children
    sub_container = [child for child in childs if (child.name == "div")]
    # print("length subcontainer: ", len(sub_container))
    main_section = sub_container[0]
    # print(main_section)
    # till here all the reg are the same; 6&7 differ from the rest from this point
    
    main_section_divs = [child for child in main_section.children if child.name == 'div']
    # print(len(main_section_divs))
    
    # integer that keeps track of the row of the entered field
    integCount = 0

    if len(main_section_divs) < 1:
        main_section_ul = [child for child in main_section.children if child.name == 'ul']
        main_section_h2 = [child for child in main_section.children if child.name == 'h2']
        category = main_section_h2[0+k].text
        content = main_section_ul[0+k]
        li_list = content.find_all("li")
        for li in li_list:
            link = ""
            Name = li.text.split("\n")[0]
            if (li.find("a")):
                a = li.find("a")
                link = a.get('href')
                #the link is retrieved so you can put the download sequence here
                #---------------------------------------------------------------
            dict_container['Name'][str(integCount)] = Name
            dict_container['category'][str(integCount)] = category
            dict_container['link'][str(integCount)] = link
            integCount += 1
        k += 1
    else:
        if (regind not in ['AU_APRA_11','AU_APRA_3','AU_APRA_4']):
            #exception of AU_APRA_3,4&11 that where the information from this point are stored in a table
            for div in main_section_divs:
                #childs = [child for child in div.children if child.name == 'div']
                toggle = div.find("button",{"class":"accordion__toggle"})
                
                category = toggle.p.text
                #print (category)
                content = div.find("div",{"class":"accordion__content"})
                li_list = content.find_all("li")
                for li in li_list:
                    link = ""
                    p_tags = [child for child in li.children if child.name == "p"]
                    if len(p_tags)<1:
                        Name = li.text.split("\n")[0]
                    else:
                        Name = p_tags[0].text
                    if (li.find("a")):
                        a = li.find("a")
                        link = a.get('href')
                        #the link is retrieved so you can put the download sequence here
                        #---------------------------------------------------------------
                    dict_container['Name'][str(integCount)] = Name
                    dict_container['category'][str(integCount)] = category
                    dict_container['link'][str(integCount)] = link
                    integCount += 1
                if regind == 'AU_APRA_2': break
            #the end of except
        else:
            tables = main_section.find_all("table")
            all_trs = tables[(0+kk)%2].find_all("tr")
            ths = all_trs[0] #[tr for tr in all_trs if tr.parent.name == "thead"]
            #print("number of header rows: ", len(ths))
            trs = all_trs[1:] #[tr for tr in all_trs if tr.parent.name == "tbody"]
            headers = getHeaders(ths)
            #We've retrieved the headers of the table as a list of string
            dict_container = init_dict(headers)
            #We've initialized the dictionary with key,value pairs where keys are the headers and the corresponding values are empty dictionaries
            for tr in trs:
                tds = tr.find_all("td")
                for td in tds:
                    dict_container[headers[tds.index(td)]][str(integCount)] = td.text
                integCount += 1
            kk += 1
    # We go through the list of excel files and extract their content as pandas dataframe and add them as a spreadsheet in our final excel sheet
    df = pd.DataFrame(dict_container)
    #print(df)
    #df = pd.read_excel(file_listing_xls[2])
    sheet_name = regind
    df.to_excel(writer,sheet_name)


writer.save()
writer.close()
driver.quit()

sleep(3)


    
    