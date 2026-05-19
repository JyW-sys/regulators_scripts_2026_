from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
from pandas import ExcelWriter
import datetime
from time import sleep
import os

print("Running SM BCSM Web Scraping Tool v.1.0")
now=datetime.datetime.now()
scriptfolder=os.path.dirname(os.path.abspath(__file__))
os.chdir(scriptfolder)
tempfolder=os.path.join(scriptfolder, 'tempfolder') #if files are downloaded during the process

filename= 'SM BCSM data {}.xlsx'.format(str(now).replace(":",".")[:-7])
writer = ExcelWriter(filename)

regdict={'SM BCSM 1':'https://www.bcsm.sm/site/home/funzioni/registri-e-albi/soggetti-autorizzati.html' , 
		 'SM BCSM 3': 'https://www.bcsm.sm/site/home/funzioni/registri-e-albi/intermediari-assicurativi-e-riassicurativi.html', 
		 'SM BCSM 5': 'https://www.bcsm.sm/site/home/funzioni/registri-e-albi/promotori-finanziari.html', 
		 'SM BCSM 6': 'https://www.bcsm.sm/site/home/funzioni/registri-e-albi/trustee-autorizzati.html'}

driver = webdriver.Chrome()
driver.maximize_window()

for reg in regdict:
	print('Working with {}.'.format(reg))

	clinks=[]
	xname=[]

	xruolo=[]
	xstato=[]

	xdataauto=[]
	xrut=[]
	xnote=[]

	xdiscrizione=[]
	xniscrizione=[]
	xdcancellazione=[]
	xdenominzione=[]
	xformagiu=[]
	xcoe=[]
	xabi=[]
	xcapoiscrizione=[]
	xcapocodice=[]
	xprocestra=[]
	xsedeleg=[]
	xsedelegloc=[]
	xsedelegcap=[]
	xsedelegcas=[]
	xsedelegstat=[]
	xsedeamm=[]
	xsedeammloc=[]
	xsedeammcap=[]
	xsedeammcas=[]
	xsedeammstat=[]
	xrsdiscri=[]
	xrsniscri=[]
	xsdrdeno=[]
	xsdrstrada=[]
	xsdrloc=[]
	xsdrcap=[]
	xsdrcas=[]
	xsdrstat=[]

	if reg=='SM BCSM 1':
		driver.get(regdict[reg])
		sleep(2)
		iframe=driver.find_element(By.XPATH, "//iframe[@id='myIframe']")
		driver.switch_to.frame(iframe)
		sleep(2)
		soup=BeautifulSoup(driver.page_source, 'html.parser')
		asx=soup.find_all("a", href=True)[1:]
		for a in asx:
			xname.append(a.text.strip())

			clinks.append('https://www.bcsm.sm'+a['href'])
		for link in range(len(clinks)):
			print('Working with entity {} out of {}. (Reg: {})'.format(link+1, len(clinks), reg))
			driver.get(clinks[link])
			sleep(0.25)
			soup2=BeautifulSoup(driver.page_source, 'html.parser')
			
			xdiscrizione.append(soup2.find("input", {"id":"schvalore000"}, value=True)['value'])
			xniscrizione.append(soup2.find("input", {"id":"schvalore001"}, value=True)['value'])
			xdcancellazione.append(soup2.find("input", {"id":"schvalore002"}, value=True)['value'])
			xdenominzione.append(soup2.find("input", {"id":"schvalore003"}, value=True)['value'])
			xformagiu.append(soup2.find("input", {"id":"schvalore004"}, value=True)['value'])
			xcoe.append(soup2.find("input", {"id":"schvalore250"}, value=True)['value'])
			abi=soup2.find("input", {"id":"schvalore257"}, value=True)
			if abi is not None:
				xabi.append(abi['value'])
			else:
				xabi.append('')
			xcapoiscrizione.append(soup2.find_all("label", {"style":"font-size:11px;color:#000;margin-left:5px;"})[0].text.strip())
			xcapocodice.append(soup2.find_all("label", {"style":"font-size:11px;color:#000;margin-left:5px;"})[1].text.strip())
			xprocestra.append(soup2.find("td", {"colspan":"3", "align":"center", "valign":"middle", "style":"height:20px"}).text.strip())
			xsedeleg.append(soup2.find("input", {"id":"schvalore005"}, value=True)['value'])
			xsedelegloc.append(soup2.find("input", {"id":"schvalore006"}, value=True)['value'])
			xsedelegcap.append(soup2.find("input", {"id":"schvalore007"}, value=True)['value'])
			xsedelegcas.append(soup2.find("input", {"id":"schvalore008"}, value=True)['value'])
			xsedelegstat.append(soup2.find("input", {"id":"schvalore009"}, value=True)['value'])
			xsedeamm.append(soup2.find("input", {"id":"schvalore010"}, value=True)['value'])
			xsedeammloc.append(soup2.find("input", {"id":"schvalore011"}, value=True)['value'])
			xsedeammcap.append(soup2.find("input", {"id":"schvalore012"}, value=True)['value'])
			xsedeammcas.append(soup2.find("input", {"id":"schvalore013"}, value=True)['value'])
			xsedeammstat.append(soup2.find("input", {"id":"schvalore014"}, value=True)['value'])
			xrsdiscri.append(soup2.find("input", {"id":"schvalore015"}, value=True)['value'])
			xrsniscri.append(soup2.find("input", {"id":"schvalore016"}, value=True)['value'])
			xsdrdeno.append(soup2.find("input", {"id":"schvalore017"}, value=True)['value'])
			xsdrstrada.append(soup2.find("input", {"id":"schvalore018"}, value=True)['value'])
			xsdrloc.append(soup2.find("input", {"id":"schvalore019"}, value=True)['value'])
			xsdrcap.append(soup2.find("input", {"id":"schvalore020"}, value=True)['value'])
			xsdrcas.append(soup2.find("input", {"id":"schvalore021"}, value=True)['value'])
			xsdrstat.append(soup2.find("input", {"id":"schvalore022"}, value=True)['value'])
			xdataauto.append('')
			xrut.append('')
			xnote.append('')
			xruolo.append('')
			xstato.append('')
	else:
		driver.get(regdict[reg])
		sleep(3)
		soup=BeautifulSoup(driver.page_source, 'html.parser')
		for tr in soup.find_all("tr"):
			tds=tr.find_all("td")
			if 'ATTIVO' in tr.text or "/" in tr.text or 'SOSPESO' in tr.text or 'INOPERATIVO' in tr.text:
				if reg=='SM BCSM 3':
					xname.append(tds[0].text.strip())
					xruolo.append(tds[1].text.strip())
					xniscrizione.append(tds[2].text.strip())
					xstato.append(tds[3].text.strip())
					xdataauto.append('')
					xrut.append('')
					xnote.append('')

					xdiscrizione.append('')
					xdcancellazione.append('')
					xdenominzione.append('')
					xformagiu.append('')
					xcoe.append('')
					xabi.append('')
					xcapoiscrizione.append('')
					xcapocodice.append('')
					xprocestra.append('')
					xsedeleg.append('')
					xsedelegloc.append('')
					xsedelegcap.append('')
					xsedelegcas.append('')
					xsedelegstat.append('')
					xsedeamm.append('')
					xsedeammloc.append('')
					xsedeammcap.append('')
					xsedeammcas.append('')
					xsedeammstat.append('')
					xrsdiscri.append('')
					xrsniscri.append('')
					xsdrdeno.append('')
					xsdrstrada.append('')
					xsdrloc.append('')
					xsdrcap.append('')
					xsdrcas.append('')
					xsdrstat.append('')

				if reg=='SM BCSM 5':
					xname.append(tds[0].text.strip())
					xniscrizione.append(tds[1].text.strip())
					xstato.append(tds[0].text.strip())

					xdiscrizione.append('')
					xdcancellazione.append('')
					xdenominzione.append('')
					xformagiu.append('')
					xcoe.append('')
					xabi.append('')
					xcapoiscrizione.append('')
					xcapocodice.append('')
					xprocestra.append('')
					xsedeleg.append('')
					xsedelegloc.append('')
					xsedelegcap.append('')
					xsedelegcas.append('')
					xsedelegstat.append('')
					xsedeamm.append('')
					xsedeammloc.append('')
					xsedeammcap.append('')
					xsedeammcas.append('')
					xsedeammstat.append('')
					xrsdiscri.append('')
					xrsniscri.append('')
					xsdrdeno.append('')
					xsdrstrada.append('')
					xsdrloc.append('')
					xsdrcap.append('')
					xsdrcas.append('')
					xsdrstat.append('')

					xdataauto.append('')
					xrut.append('')
					xnote.append('')
					xruolo.append('')
				if reg=='SM BCSM 6':
					if len(tds)>0:
						xruolo.append('')
						xstato.append('')
						xniscrizione.append(tds[0].text.strip())
						xname.append(tds[1].text.strip())
						xsedeleg.append(tds[2].text.strip())
						xformagiu.append(tds[3].text.strip())
						xcoe.append(tds[4].text.strip())
						xdataauto.append(tds[5].text.strip())
						xrut.append(tds[6].text.strip())
						xnote.append(tds[7].text.strip())
						xdiscrizione.append('')
						xdcancellazione.append('')
						xdenominzione.append('')
						xabi.append('')
						xcapoiscrizione.append('')
						xcapocodice.append('')
						xprocestra.append('')
						xsedelegloc.append('')
						xsedelegcap.append('')
						xsedelegcas.append('')
						xsedelegstat.append('')
						xsedeamm.append('')
						xsedeammloc.append('')
						xsedeammcap.append('')
						xsedeammcas.append('')
						xsedeammstat.append('')
						xrsdiscri.append('')
						xrsniscri.append('')
						xsdrdeno.append('')
						xsdrstrada.append('')
						xsdrloc.append('')
						xsdrcap.append('')
						xsdrcas.append('')
						xsdrstat.append('')

	#print(len(xstato))				
	#print(len(xname))
	#print(len(xruolo))
	#print(len(xniscrizione))
	#print(len(xsedeleg))
	#print(len(xformagiu))
	#print(len(xcoe))
	#print(len(xdataauto))
	#print(len(xrut))
	#print(len(xnote))
	#print(len(xdiscrizione))
	#print(len(xdcancellazione))
	#print(len(xdenominzione))
	#print(len(xabi))
	#print(len(xcapoiscrizione))
	#print(len(xcapocodice))
	#print(len(xprocestra))
	#print(len(xsedelegloc))
	#print(len(xsedelegcap))
	#print(len(xsedelegcas))
	#print(len(xsedelegstat))
	#print(len(xsedeamm))
	#print(len(xsedeammloc))
	#print(len(xsedeammcap))
	#print(len(xsedeammcas))
	#print(len(xsedeammstat))
	#print(len(xrsdiscri))
	#print(len(xrsniscri))
	#print(len(xsdrdeno))
	#print(len(xsdrstrada))
	#print(len(xsdrloc))
	#print(len(xsdrcap))
	#print(len(xsdrcas))
	#print(len(xsdrstat))
		

	df=pd.DataFrame({'Name': xname, 'Data Iscrizione (Registro Soggetti Autorizzati)': xdiscrizione, 
					 'N. iscrizione (Registro Soggetti Autorizzati)': xniscrizione, 'Data Cancellazione': xdcancellazione, 
					 'Ruolo professionale': xruolo, 'Stato': xstato, 'Data autorizzazione': xdataauto,  'Nominativo R.U.T.': xrut, 'Note': xnote,
					 'Forma giuridica': xformagiu, 'Codice Operatore Economico': xcoe, 'ABI': xabi, 
					 'REGISTRO DELLE IMPRESE CAPOGRUPPO Iscrizione': xcapoiscrizione, 'Codice impresa Capogruppo': xcapocodice, 
					 'PROCEDIMENTI STRAORDINARI': xprocestra, 'Sede Legale': xsedeleg, 'Sede Legale Località': xsedelegloc, 
					 'Sede Legale CAP':xsedelegcap , 'Sede Legale Castello': xsedelegcas, 'Sede Legale Stato': xsedelegstat, 
				 	 'Sede Amministrativa (se diversa)': xsedeamm, 'Sede Amministrativa Località': xsedeammloc, 
				 	 'Sede Amministrativa CAP': xsedeammcap, 'Sede Amministrativa Castello': xsedeammcas, 'Sede Amministrativa Stato': xsedeammstat, 
				 	 'Registro società - Data Iscrizione': xrsdiscri, 'Registro società - N. iscrizione': xrsniscri, 
				 	 'Società di Revisione - Denominazione': xsdrdeno, 'Società di Revisione - Strada': xsdrstrada, 
				 	 'Società di Revisione - Località': xsdrloc, 'Società di Revisione - CAP': xsdrcap, 'Società di Revisione - Castello/Città': xsdrcas, 
				 	 'Società di Revisione - Stato':xsdrstat})
	df.to_excel(writer, reg)

writer.save()
writer.close()
sleep(3)

driver.quit()
    
    