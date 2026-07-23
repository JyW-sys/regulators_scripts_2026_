# %%

#Developed by Anicet on 12/01/2023

#updated by __ on --/--/2023



#------------------------------------------------ Begin_Librairie ----------------------------------------

from selenium import webdriver

import pandas as pd

from time import sleep

import datetime

from selenium import webdriver

from selenium.webdriver import ActionChains

from selenium.webdriver.common.by import By

from selenium.webdriver.support.ui import WebDriverWait

from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup

from pandas import ExcelWriter

import os



from selenium.webdriver.chrome.service import Service as ChromeService

from webdriver_manager.chrome import ChromeDriverManager



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------



print("Running ES BES Web Scraping Tool v.1.1")

now=datetime.datetime.now()

filename= 'ES BES data {}.xlsx'.format(str(now).replace(":",".")[:-7])

#scriptfolder = "C:\\Users\\siewekoa\\OneDrive - moodys.com\\Desktop\\my_scripts\\ES BES"

scriptfolder=os.path.dirname(os.path.abspath(__file__))

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



# %%

regdict={	'ES BES 1': 'BP', 

			'ES BES 2': 'CA', 

			'ES BES 3': 'CC', 

			'ES BES 4': 'CO', 

			'ES BES 5': 'EDE', 

			'ES BES 6': 'EP', 

			'ES BES 7': 'EFC', 

			'ES BES 8': 'OR', 

			'ES BES 10': 'SGR', 

			'ES BES 11': 'SR', 

			'ES BES 12': 'ST', 

			'ES BES 14': 'SECC', 

			'ES BES 15': 'SECE', 

			'ES BES 16': 'SEDC', 

			'ES BES 17': 'SEPC', 

			'ES BES 18': 'ECVM',

			'ES BES 19': '21', 

			'ES BES 20': '11.2', 

			'ES BES 22': '19'}



sqldict={'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [], 

		  'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [], 

		  'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [], 

		  'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

		  'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [], 

		  'Phone - Mother company': [], 'Check': []} 

		

processdate=now.strftime('%Y-%m-%d') 



# %%

#------------------------------------------------ Begin_Fouction ----------------------------------------



def page_has_loaded(driver, timeout, POLL_FREQUENCY, XPATH):

    sleep(1)



    for time in range(10):

        try:

            element_present = EC.presence_of_element_located((By.XPATH, XPATH))

            #element_present = EC.element_to_be_clickable((By.XPATH, XPATH))

            wait=WebDriverWait(driver, timeout, POLL_FREQUENCY).until(element_present)

            break



        except:

            sleep(2)

            raise Exception('Failed to get information for entity, url:')



    return driver.find_element(By.XPATH, XPATH)





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





def gotoreg(regcode):

    if regcode[0].isdigit():

        catxpath=f'//*[@id="CBTipoEntidad"]/option[@value="{regcode}"]'

        Entities = 0 # Entities without establishment

    else:

        catxpath=f'//*[@id="CBTipoEntidad"]/option[@value="{regcode}"]'

        Entities  = 1 # Entities with establishment

    

    driver.find_element(By.XPATH, catxpath).click()

    sleep(1)

    driver.find_element(By.XPATH, '//*[@id="btnBuscar"]').click()

    sleep(1)



    return Entities 



# %%

#------------------------------------------------ Begin_Main ----------------------------------------



driver.get('http://app.bde.es/ren_www/ren_wwwias/xml/Arranque.html')

sleep(1)

establecimiento=driver.find_element(By.XPATH, '//*[@id="AreaDeNavegacioncolMapa_0"]/ul/li[1]/ul/li[1]').click()

sleep(3)



for Numreg, reg in enumerate(regdict):

	

	print('Working with {}.'.format(reg))



	if reg == 'ES BES 19':

		driver.get('http://app.bde.es/ren_www/ren_wwwias/xml/Arranque.html')

		sleep(1)

		establecimiento=driver.find_element(By.XPATH, '//*[@id="AreaDeNavegacioncolMapa_0"]/ul/li[1]/ul/li[2]').click()

		sleep(3)

		

	try:

		Entities = gotoreg(regdict[reg])

	except:

		print('failed go to reg', reg)

		continue



	soup=BeautifulSoup(driver.page_source, 'html.parser')

	totalpages = soup.find('label', {'class':'iasLabel iasWidget paginationNumber'})



	if len(totalpages.text)!=0:



		totalpages = int( (totalpages.text).split('/')[-1])

		# if (totalpages != None) and (len(totalpages.text)!=0):

		# 	totalpages = int( (totalpages.text).split('/')[-1])

		# else:

		# 	totalpages=1



		for page in range(totalpages):



			sleep(2)

			soup2=BeautifulSoup(driver.page_source, ('html.parser'))

			table=soup2.find("table", {"id":"TableDataRejillaConPaginacionEnServidor"})

			trs = table.find_all("tr", {"tabindex":"-1"})



			for Numtr, tr in enumerate(trs):



				print(f'Typology {Numreg+1}/{len(regdict.keys())} | Page: {page+1}/{totalpages} | Item : {Numtr+1}/{len(trs)} ')



				id=tr['id']

				select_element=page_has_loaded(driver, 1, 5, f'//*[@id="{id}"]').click()

				Detail_btn= page_has_loaded(driver, 1, 5, '//*[@id="btnDetalle"]').click()

				sleep(2)



				if Entities == 1 : # Entities with establishment

					sqldict['Name'].append(driver.find_element(By.XPATH, '//*[@id="cdtNombre"]').get_attribute('value'))

					sqldict['InternalID_1'].append(driver.find_element(By.XPATH, '//*[@id="cdtCodigoBE"]').get_attribute('value'))

					sqldict['InternalID_1_type'].append('BE Code')

					sqldict['InternalID_2'].append(driver.find_element(By.XPATH, '//*[@id="cdtCodigoLei"]').get_attribute('value'))

					sqldict['InternalID_2_type'].append('LEI Code')

					sqldict['InternalID_3'].append(driver.find_element(By.XPATH, '//*[@id="codigocif"]').get_attribute('value'))

					sqldict['InternalID_3_type'].append('N.I.F')

					# sqldict['City'].append(driver.find_element(By.XPATH, '//*[@id="cdtNombre"]').get_attribute('value'))

					# sqldict['Zip'].append(driver.find_element(By.XPATH, '//*[@id="cdtNombre"]').get_attribute('value'))

					# sqldict['VALUE'].append(driver.find_element(By.XPATH, '//*[@id="PantallaDetalleEntidadesConEst_cdtFechaAlta"]').get_attribute('value')) # Fecha de alta:

					# sqldict['VALUE'].append(driver.find_element(By.XPATH, '//*[@id="PantallaDetalleEntidadesConEst_cdtFechaBaja"]').get_attribute('value')) # Fecha de baja:

					sqldict['Address_1'].append(driver.find_element(By.XPATH, '//*[@id="cdtDomicilio"]').get_attribute('value'))

					sqldict['Typology'].append(driver.find_element(By.XPATH, '//*[@id="cdtNomtipo"]').get_attribute('value'))

					sqldict['Phone'].append(driver.find_element(By.XPATH, '//*[@id="cdtTelefono"]').get_attribute('value'))

					sqldict['Fax'].append(driver.find_element(By.XPATH, '//*[@id="cdtFax"]').get_attribute('value'))

					sqldict['Name - Mother Company'].append(driver.find_element(By.XPATH, '//*[@id="cdtEntidadMatriz"]').get_attribute('value'))

					sqldict['Address_1 - Mother company'].append(driver.find_element(By.XPATH, '//*[@id="cdtDireccionMatriz"]').get_attribute('value'))

					sqldict['RegulationDate'].append(driver.find_element(By.XPATH, '//*[@id="PantallaDetalleEntidadesConEst_cdtFechaActualizacion"]').get_attribute('value')) # Fecha de actualización



					Website = driver.find_element(By.XPATH, '//*[@id="linkDomDirInternet"]').get_attribute('href')

					if len(Website)!=0 :

						sqldict['Website'].append(Website.split('//')[1])

					else:

						sqldict['Website'].append('')

					

				elif Entities == 0 : # Entities without establishment

					sqldict['Name'].append(driver.find_element(By.XPATH, '//*[@id="cdtNombre1"]').get_attribute('value'))

					sqldict['Typology'].append(driver.find_element(By.XPATH, '//*[@id="cdtNomtipoent"]').get_attribute('value'))

					sqldict['Cntry'].append(driver.find_element(By.XPATH, '//*[@id="cdtPaisOrigen"]').get_attribute('value'))

					sqldict['RegulationDate'].append(driver.find_element(By.XPATH, '//*[@id="PantallaDetalleEntidadesSinEst_cdtFechaActualizacion"]').get_attribute('value')) # Fecha de actualización



				sqldict['ListProcessDate'].append(processdate)

				sqldict['RegCtry'].append(reg.split(' ')[0]) 

				sqldict['RegCode'].append(reg.split(' ')[1])

				sqldict['ListCode'].append(reg.split(' ')[-1])

				sqldict['RegulationType'].append('Regulated')

				#sqldict = bourange_same_length_array(sqldict)



				preview_btn2= page_has_loaded(driver, 1, 5, '//*[@id="btnVolver"]')

				driver.execute_script("arguments[0].click();",preview_btn2)



			sqldict = bourange_same_length_array(sqldict)



			if page+1 < totalpages:

				print(f'Click Next page. Go to page -> {page+2}')

				sleep(2)

				Next_btn = page_has_loaded(driver, 1, 5, '//*[@id="RejillaConPaginacionEnServidorpaginador"]/button[3]').click()

			



		sqldict = bourange_same_length_array(sqldict)



	preview_btn= page_has_loaded(driver, 1, 5, '//*[@id="btnVolver"]')

	driver.execute_script("arguments[0].click();",preview_btn)

	sleep(2)





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


    
    