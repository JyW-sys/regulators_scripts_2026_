# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from bs4 import BeautifulSoup

import datetime

import pandas as pd

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.by import By

from time import sleep

import pdfplumber

import tabula

import os



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'IE CBIRE' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.2")

now=datetime.datetime.now()

filename = '{} SQL Ready {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

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

'IE CBIRE 1': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=2%2c13&firmType=CreditInstitutions', 

'IE CBIRE 2': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=15&firmType=CreditUnions', 

'IE CBIRE 3': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=17&firmType=Insurance', 

'IE CBIRE 4': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=19&firmType=Insurance', 

'IE CBIRE 5': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=18&firmType=Insurance', 

'IE CBIRE 6': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=20&firmType=Insurance', 

'IE CBIRE 7': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=21&firmType=Insurance', 

'IE CBIRE 8': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=32%2c33%2c58%2c59&firmType=InvestmentFirms', 

'IE CBIRE 9': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=1%2c3%2c27&firmType=Intermediaries', 

'IE CBIRE 10': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=55%2c57&firmType=Intermediaries', 

'IE CBIRE 12': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=9', 

'IE CBIRE 13': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=4', 

'IE CBIRE 14': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=22%2c22', 

'IE CBIRE 15': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=26', 

'IE CBIRE 17': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=44%2c45&firmType=FundServiceProvider', 

'IE CBIRE 18': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=28', 

'IE CBIRE 19':  ['Register of UCITS Management Companies', '//*[@id="ctl00_cphRegistersMasterPage_Label76"]'], 

'IE CBIRE 20': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=14&firmType=Moneylenders', 

'IE CBIRE 21': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=30&firmType=RetailCreditHomeReversion', 

'IE CBIRE 22': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=25&firmType=Moneybrokers', 

'IE CBIRE 23': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=61&firmType=PaymentServicesFirms', 

'IE CBIRE 24': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=37&firmType=PaymentServicesFirms', 

'IE CBIRE 28': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=43&firmType=DebtManagementFirms', 

'IE CBIRE 29': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=7&firmType=Intermediaries', 

'IE CBIRE 30': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=12&firmType=BureauDeChange', 

'IE CBIRE 31': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=60&firmType=ExcludedServiceProviders', 

'IE CBIRE 32':  ['Registers of Payment Services Firms', '//*[@id="ctl00_cphRegistersMasterPage_Label61"]'], 

'IE CBIRE 33': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=62&firmType=PaymentServicesFirms', 

'IE CBIRE 34': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=24&firmType=RegulatedMarkets', 

'IE CBIRE 35':  ['Registers of E-Money Firms', '//*[@id="ctl00_cphRegistersMasterPage_Label63"]'],   

# 'IE CBIRE 36': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=40&firmType=EMoneyFirms', 

# 'IE CBIRE 37': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=41%2c39&firmType=EMoneyFirms', 

'IE CBIRE 38': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=66&firmType=EMoneyFirms', 

'IE CBIRE 39': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=63&firmType=EMoneyFirms', 

'IE CBIRE 40': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=Institution&searchType=Name&searchText=&registers=53&firmType=CreditServicingFirms', 

'IE CBIRE 41': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=FundServiceProvider&searchType=Name&searchText=&registers=6%2c29%2c44%2c45', 

'IE CBIRE 42': 'http://registers.centralbank.ie/FundSearchResultsPage.aspx?searchEntity=Fund&searchType=Name&searchText=&registers=50', 

'IE CBIRE 43': 'http://registers.centralbank.ie/FirmSearchResultsPage.aspx?searchEntity=PaymentServicesAgent&searchType=Name&searchText=&registers=36&firmType=PaymentServicesAgents&country=All', 

}



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

	  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

		  'Phone - Mother company': [], 'Check': []}



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

    for time in range(wait_time):

        if len([ele for ele in os.listdir(tempfolder) if '.crdownload' not in ele and '.tmp' not in ele]) != 0 :

            print(f"[INFO] : {fileType} file = {os.listdir(tempfolder)})")

            break

        else:

            print(f"[INFO] : Download {fileType} file ... (wait {time*2}/20 s)")

            sleep(2)

    else:

        raise Exception(f'[ERROR] : Failed to Download {fileType} file. Run Script again' )

    return  os.listdir(tempfolder)[0]



def compute_page(filePath, liste_expression1, liste_expression2=None ):

    Allpages = []

    AllIndexPages =[]

    with pdfplumber.open(filePath) as pdf:

        total_pages = len(pdf.pages)

        for i, expression1 in enumerate(liste_expression1) :

            pages = []

            IndexPages =[]

            for p, page in enumerate(pdf.pages):

                text = page.extract_text()

                if liste_expression2 != None :

                    if (expression1 in  text) or (liste_expression2[i] in  text) :

                        pages.append(p+1)

                        IndexPages.append(p+1)

                else:

                    if expression1 in  text :

                        pages.append(p+1)

                        IndexPages.append(p+1)

            Allpages.append(pages)

            AllIndexPages.append(IndexPages)

            pages = []

            IndexPages =[]

    return total_pages, Allpages, AllIndexPages



def Trandforme_date(stringDate, sep) :

    months = {

    'JANUARY'   :1, 

    'FEBRUARY'  :2, 

    'MARCH'     :3, 

    'APRIL'     :4, 

    'MAY'       :5, 

    'JUNE'      :6, 

    'JULY'      :7, 

    'AUGUST'    :8, 

    'SEPTEMBER' :9, 

    'OCTOBER'   :10, 

    'NOVEMBER'  :11, 

    'DECEMBER'  :12,

    }

    m = 0

    D = stringDate.split(sep)[0]

    M = stringDate.split(sep)[1]

    Y = stringDate.split(sep)[2]



    m = months[M.upper()]

    return Y+'-'+ str(m)+'-'+ D



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

for k, reg in enumerate(regdict):    

	print(f"[INFO] : Working {k+1}/{len(regdict)} _({reg})_ ")



	if reg=='IE CBIRE 19' or reg=='IE CBIRE 32' or reg=='IE CBIRE 35':

		driver.get('https://registers.centralbank.ie/DownloadsPage.aspx')

		dd = driver.find_element(By.XPATH,f'//div[@id="content"]//*/span[contains(text(),"{regdict[reg][0]}")]').click()

		sleep(0.3)

		driver.find_element(By.XPATH,f'{regdict[reg][1]}').click()

		file =  check_dowload_files(tempfolder, "pdf" )

		filePath = os.path.join(tempfolder, file)



		if reg=='IE CBIRE 19':

			total_pages, Allpages, AllIndexPages = compute_page(filePath, ['Reference Number'])

			tables = tabula.read_pdf(filePath, columns=[150, 290, 400, 480, 590], guess=False, pages=Allpages[0])

			date = ''

			for p, df in enumerate(tables):

				print(f"[INFO] : -- PdfPage {AllIndexPages[0][p]}/{total_pages} | {reg}")

				df.columns = ['Reference Number', 'Name', 'Entity Status', 'Entity Sub Status', 'Country', 'Date']

				if df.shape[0] != 0:

					if AllIndexPages[0][p] == 1:

						date = Trandforme_date(df.iloc[-1]['Reference Number'].split(":")[1].strip(), ' ')

						df = df[6:]

						df = df[:-1]

					elif AllIndexPages[0][p] == AllIndexPages[0][-1]:

						df = df[:-6]

					else:

						df = df[:-1]

					

					df = df.fillna("")

					df = df.reset_index(drop=True)

					

					for index, row in df.iterrows():

						ref = row['Reference Number']

						if len(ref)> 0:

							adrr = ''

							for i in range(index+1, len(df)):

								if len(df.iloc[i, 0])==0 :

									col_name = df.iloc[i, 1]

									if col_name.find('S.A.R.L')==-1 and col_name.find('S.A')==-1 and col_name.find('SA')==-1 and col_name.find('N.v')==-1 and col_name.find('AG')==-1:

										adrr = adrr + ' ' + df.iloc[i, 1]

								else:

									# print(adrr)

									break

							

							sqldict['Name'].append(row['Name'])

							sqldict['Cntry'].append(row['Country'])

							sqldict['CancellationDate'].append(Trandforme_date(row['Date'], ' '))

							sqldict['Address_1'].append(adrr.strip())

							sqldict['RegulationDate'].append(date)

							sqldict['ListProcessDate'].append(processdate)

							sqldict['RegCtry'].append(reg.split()[0])

							sqldict['RegCode'].append(reg.split()[1])

							sqldict['ListCode'].append(reg.split()[2])

							sqldict["InternalID_1"].append(ref)

							sqldict["InternalID_1_type"].append("Ref No.")

							

					sqldict = bourange_same_length_array(sqldict)

					sleep(1)



		elif reg=='IE CBIRE 35' or reg=='IE CBIRE 32':

			jj = 0



			if reg=='IE CBIRE 32':

				total_pages, Allpages, AllIndexPages = compute_page(filePath, ['Ireland'])

				tables = tabula.read_pdf(filePath, columns=[70, 210, 250, 320, 380, 460, 590, 620], guess=False, pages=Allpages[0])

				columns = ['Ref No', 'Name and Address', 'Date Authorised', 'Date Authorised Withdrawn', 'Payment Services', 'Passporting To ', 'Establishment', 'Agents', 'Branches']

				p_first= [6,-1]

				p_last = [0,-8]

				p_all  = [0,-1]

				

			elif reg=='IE CBIRE 35':

				total_pages, Allpages, AllIndexPages = compute_page(filePath, ['Name and Address'])

				tables = tabula.read_pdf(filePath, columns=[70, 240, 290, 360, 400, 480, 580, 690], guess=False, pages=Allpages[0])

				columns = ['Ref No', 'Name and Address', 'Date Authorised', 'Date Authorised Withdrawn', 'Payment Services', 'Agents', 'Passporting To ', 'Establishment', 'Branches']

				p_first= [0,-1]

				p_last = [0,-6]

				p_all  = [0,-1]



			date = ''

			for p, df in enumerate(tables):

				print(f"[INFO] : -- PdfPage {AllIndexPages[0][p]}/{total_pages} | {reg}")

				df.columns = columns

				if df.shape[0] != 0:

					

					date = Trandforme_date(df.iloc[-1]['Name and Address'].strip(), ' ')

					df = df[2:]

					if AllIndexPages[0][p] == AllIndexPages[0][0]:

						df = df[p_first[0]:p_first[1]]

					elif AllIndexPages[0][p] == AllIndexPages[0][-1]:

						df = df[p_last[0]:p_last[1]]

					else:

						df = df[p_all[0]:p_all[1]]

					

					df = df.fillna("")

					df = df.reset_index(drop=True)

					

					for index, row in df.iterrows():

						ref = row['Ref No']

						if len(ref)> 0:

							jj+=1

							col_name = row['Name and Address']

							adrr = ''

							for i in range(index+1, len(df)):

								if len(df.iloc[i, 1])!=0 :

									col_adrr = df.iloc[i, 1]

									if col_adrr.find('t/a')==-1 and col_adrr.find('Limited')==-1 and col_adrr.find('Payments')==-1 :

										adrr = adrr + '*' + df.iloc[i, 1]

								else:

									# print(adrr)

									break



							Ctry = adrr.split("*")[-1]

							if len(adrr.split("*")[-2].split(" ")[0]) == 3 : # Le premiere teme du Zip est un terme de 3 caracteres

								Zip = adrr.split("*")[-2].strip()

								City = adrr.split("*")[-3].strip()

								Address_1 = adrr.split("*")[-4].strip()

								Address_2 = adrr.split("*")[-5].strip()

							else:

								City = adrr.split("*")[-2].strip()

								Zip = ''

								Address_1 = adrr.split("*")[-3].strip()

								Address_2 = adrr.split("*")[-4].strip()



							# print(f'[INFO] :     {jj}) {ref} : {col_name} | {adrr}  | {len(adrr.split("*"))}')



							sqldict['Name'].append(col_name)

							sqldict['Cntry'].append(Ctry)

							sqldict['Address_1'].append(Address_1)

							sqldict['Address_2'].append(Address_2)

							sqldict['City'].append(City)

							sqldict['Zip'].append(Zip)

							sqldict['ListProcessDate'].append(processdate)

							sqldict['RegCtry'].append(reg.split()[0])

							sqldict['RegCode'].append(reg.split()[1])

							sqldict['ListCode'].append(reg.split()[2])

							sqldict["InternalID_1"].append(ref)

							sqldict["InternalID_1_type"].append("Ref No.")

					

					sqldict = bourange_same_length_array(sqldict)

					sleep(1)

		for rem in os.listdir(tempfolder):

			os.remove(os.path.join(tempfolder, rem))



	else:

		entity_data = list()

		if regdict[reg].endswith('.aspx'):

			print(reg, 'not findable... skipping....')

			continue

		driver.get(regdict[reg])

		sleep(3)

		soup=BeautifulSoup(driver.page_source, "html.parser")

		verify=soup.text.lower()

		if "sorry," in verify or 'an error has occurred' in verify:#this if condition is used to skip reg codes with errors due to no results.

			continue



		soup=soup.find("table", {"class":"searchresults"})

		pager=soup.find("tr", {"class":"searchresultspager"})

		

		if pager is not None:

			pager=pager.text.strip()

			total_pages=int(pager[pager.find("of")+3:].strip())

			total_pages = 2

		else:

			total_pages=1

		

		for page in range(total_pages):

			sleep(1)

			print(f"[INFO] : - Scrapping page {page+1}/{total_pages} | _({reg})_ ")

			soup2=BeautifulSoup(driver.page_source, "html.parser")

			if 'an error has occurred' in soup.text.lower():#pages in agents all are broken after p17

				driver.quit()

				del driver

				driver = webdriver.Chrome(options=chromeOptions)

				driver.maximize_window()

				driver.get(regdict[reg])

				sleep(1)

				for pag in range(page):

					driver.find_element(By.XPATH, '//input[@class="rightpagerbutton"]').click()

					sleep(0.25)

				sleep(1)

				soup2=BeautifulSoup(driver.page_source, "html.parser")

			if  soup2.find("table", {"class":"searchresults"}) is None:

				continue

			table=soup2.find("table", {"class":"searchresults"})

			tbody=table.find("tbody")

			trs=tbody.find_all("tr")

			header = trs[0]# Header A:  Ref No / Name / Trading Name //// Header B: CIS/AIFM/Management/Depositary

			ths=header.find_all("th")

			name_index=None

			for name_ix in range(len(ths)):

				thtext = ths[name_ix].text.lower()

				if 'name' in thtext and 'trading' not in thtext or 'cis' in thtext:

					name_index = name_ix

					break

			for tr in trs[1:]:

				tds=tr.find_all("td")

				if 'next page' in str(tr) or 'searchresultspager' in str(tr) or len(tr.find_all('option'))>0:

					pass #pager tr/row

				else:

					name = tds[name_index].text.strip()

					url=tds[name_index].find("a", href=True)['href']

					entity_data.append((name, 'http://registers.centralbank.ie/'+url))#get ref name and trading name from within the new url

					

					ref = url.split('Number=')[-1]

					ref = ref.split('=')[0]

					while ref[-1].isdigit() is False:

						ref=ref[:-1]

					

					sqldict['Name'].append(name)

					sqldict['Cntry'].append('IE')

					sqldict['ListProcessDate'].append(processdate)

					sqldict['RegCtry'].append(reg.split()[0])

					sqldict['RegCode'].append(reg.split()[1])

					sqldict['ListCode'].append(reg.split()[2])

					sqldict["InternalID_1"].append(ref)

					sqldict["InternalID_1_type"].append("Ref No.")



			sqldict = bourange_same_length_array(sqldict)

			sleep(1)



			if page<total_pages-1:

				driver.find_element(By.XPATH, '//input[@class="rightpagerbutton"]').click()



# %%

#------------------------------------------------ Begin_writer and save df to excel  ----------------------------------------

os.chdir(scriptfolder)

df=pd.DataFrame(sqldict)

df.to_excel(writer, 'SQL Ready', index=False)

writer.save()

writer.close()

driver.quit()

sleep(3)






    