# %%

#------------------------------------------------ Begin_Librairie ----------------------------------------

from bs4 import BeautifulSoup

import datetime

import pandas as pd

from pandas import ExcelWriter

from selenium import webdriver

from selenium.webdriver.common.by import By

from time import sleep

import os



# %%

#------------------------------------------------ Begin_ fileName ----------------------------------------

regulatorName = 'MX CNBV' ## change to current controller name



print(f"Running {regulatorName} Web Scraping Tool v.1.2")

now=datetime.datetime.now()

filename = '{} SQL Read {}.xlsx'.format(regulatorName, str(now).replace(":",".")[:-7])

scriptfolder = f"C:\\Users\\wuj1\\OneDrive - moodys.com\\Desktop\\Regulator\\{regulatorName}" ## to comment for the local environment

#scriptfolder=os.path.dirname(os.path.abspath(__file__)) ## to decomment for the production environment

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

#------------------------------------------------ Begin_variable----------------------------------------

regdict={

'UNIONES DE CRÉDITO'                                                                            :'1',

'SOCIEDADES FINANCIERAS POPULARES'                                                              :'3',

'FONDOS DE INVERSIÓN DE CAPITALES'                                                              :'4',

'FONDOS DE INVERSIÓN DE RENTA VARIABLE'                                                         :'4',

'FONDOS DE INVERSIÓN EN INSTRUMENTOS DE DEUDA'                                                  :'4',

'ENTIDADES DISTRIBUIDORAS INTEGRALES'                                                           :'4',

'ENTIDADES DISTRIBUIDORAS REFERENCIADORAS'                                                      :'4',

'SOCIEDADES DISTRIBUIDORAS INTEGRALES'                                                          :'4',

'MECANISMOS ELECTRÓNICOS DE DIVULGACIÓN DE INFORMACIÓN'                                         :'4',

'SOCIEDADES OPERADORAS LIMITADAS DE FONDOS DE INVERSIÓN'                                        :'4',

'SOCIEDADES VALUADORAS DE ACCIONES DE FONDOS DE INVERSIÓN'                                      :'4',

'MECANISMOS ELECTRÓNICOS DE NEGOCIACIÓN DE ACCIONES DE FONDOS DE INVERSIÓN'                     :'4',

'SOCIEDADES OPERADORAS DE FONDOS DE INVERSIÓN DE CAPITALES'                                     :'4',

'SOCIEDADES OPERADORAS DE FONDOS DE INVERSIÓN EN INSTRUMENTOS DE DEUDA Y DE RENTA VARIABLE'     :'4',



'INSTITUCIONES DE BANCA DE DESARROLLO'                                                          :'11',

'ORGANISMOS DE FOMENTO'                                                                         :'11',

'FIDEICOMISOS PÚBLICOS DE FOMENTO ECONÓMICO FINANCIERO'                                         :'11',



'BOLSA DE CONTRATOS DE DERIVADOS'                                                               :'12',

'BOLSAS DE VALORES'                                                                             :'12',

'INSTITUCIONES CALIFICADORAS DE VALORES'                                                        :'12',

'OPERADORES PARTICIPANTES DEL MERCADO DE CONTRATOS DE DERIVADOS'                                :'12',

'CASAS DE BOLSA'                                                                                :'12',

'CÁMARAS DE COMPENSACIÓN DEL MERCADO DE CONTRATOS DE DERIVADOS'                                 :'12',

'ORGANISMOS AUTORREGULATORIOS DEL MERCADO DE VALORES'                                           :'12',

'SOCIOS LIQUIDADORES PARTICIPANTES DEL MERCADO DE CONTRATOS DE DERIVADOS'                       :'12',

'CONTRAPARTES CENTRALES DE VALORES'                                                             :'12',

'INSTITUCIONES PARA EL DEPÓSITO DE VALORES'                                                     :'12',



'SOCIEDADES COOPERATIVAS DE AHORRO Y PRÉSTAMO'                                                  :'13',



'INSTITUCIONES DE BANCA MÚLTIPLE'                                                               :'17',

'EMISORAS'                                                                                      :'18',



'SOCIEDADES OPERADORAS DE SOCIEDADES DE INVERSIÓN DE CAPITAL'                                   :'20',

'SOCIEDADES DE INVERSIÓN EN INSTRUMENTOS DE DEUDA'                                              :'20',



'ASESORES EN INVERSIÓN PERSONAS FISICAS'                                                        :'21',

'ASESORES EN INVERSIÓN PERSONAS MORALES'                                                        :'21',

'ASESORES EN INVERSIÓN PERSONAS MORALES NO INDEPENDIENTES'                                      :'21',



'SOCIEDADES FINANCIERAS DE OBJETO MÚLTIPLE, ENTIDADES NO REGULADAS'                             :'22',

'TRANSMISORES DE DINERO'                                                                        :'22',

'PARTICIPANTES EN REDES DE MEDIOS DE DISPOSICIÓN RELEVANTES'                                    :'22',

'CENTROS CAMBIARIOS'                                                                            :'22',

'OFICINAS DE REPRESENTACIÓN Y AGENCIAS DE BANCOS EXTRANJEROS'                                   :'22',

'EMPRESAS DE SERVICIOS COMPLEMENTARIOS O CONEXOS DE BANCA'                                      :'22',

'SOCIEDADES CONTROLADORAS DE GRUPOS FINANCIEROS'                                                :'22',

'ALMACENES GENERALES DE DEPÓSITO'                                                               :'22',

'EMPRESAS DE SERVICIOS COMPLEMENTARIOS O CONEXOS DE ORGANIZACIONES AUXILIARES'                  :'22',

'EMPRESAS DE SERVICIOS COMPLEMENTARIOS O CONEXOS DE GRUPOS FINANCIEROS'                         :'22',

'CASAS DE CAMBIO'                                                                               :'22',

'SUBCONTROLADORAS'                                                                              :'22',

'SOCIEDADES QUE ADMINISTREN SISTEMAS PARA FACILITAR OPERACIONES CON VALORES'                    :'22',

'SOCIEDADES DE INFORMACIÓN CREDITICIA'                                                          :'22',

'INMOBILIARIAS BANCARIAS'                                                                       :'22',

'INMOBILIARIAS DE CASAS DE BOLSA'                                                               :'22',

'OFICINAS DE REPRESENTACIÓN DE CASAS DE BOLSA'                                                  :'22',

'PROVEEDORES DE PRECIOS'                                                                        :'22',



# 'SOCIEDADES FINANCIERAS DE OBJETO MÚLTIPLE'                                                     :'0',

# 'FONDO DE PROTECCIÓN DE SOCIEDADES FINANCIERAS POPULARES Y DE PROTECCIÓN A SUS AHORRADORES'     :'0',

# 'FEDERACIONES DE ENTIDADES DE AHORRO Y CRÉDITO POPULAR'                                         :'0',

# 'FONDO DE SUPERVISIÓN AUXILIAR DE SOCIEDADES COOPERATIVAS DE AHORRO Y PRÉSTAMO'                 :'0',

# 'INSTITUCIONES DE FONDOS DE PAGO ELECTRÓNICO'                                                   :'0',

}



sqldict = {'bvdid': [], 'priority': [], 'ListLabel': [], 'Typology': [], 'EntryType': [], 'Name': [], 'InternalID_1': [], 'InternalID_1_type': [], 'InternalID_2': [],

          'InternalID_2_type': [], 'InternalID_3': [], 'InternalID_3_type': [], 'CoType': [], 'License_Type': [], 'Address_1': [], 'Address_2': [], 'City': [],

          'Zip': [], 'Cntry': [], 'Phone': [], 'Fax': [], 'Website': [], 'Email': [], 'RegulationType': [], 'RegulationTypeCode': [], 'RegulationDate': [], 'CancellationDate': [],

          'RegCtry': [], 'RegCode' : [], 'ListCode': [], 'ListLanguage': [], 'ListValidityDate': [], 'ListName': [], 'ListProcessDate': [], 'LEI Code': [], 'BIC SWIFT Code': [], 'Name - Mother Company': [],

          'Address_1 - Mother company': [], 'Address_2 -  Mother company': [], 'City - Mother company': [], 'Zip - Mother company': [], 'Cntry - Mother company': [],

          'Phone - Mother company': [], 'Check': []}



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



def xpath_retry(xpath,key_press=False):

    for times in range(40):

            try:

                driver.find_element(By.XPATH, xpath).click()

                break

            except:

                sleep(1)

                if key_press:                    

                    driver.find_element(By.XPATH, '//body').send_keys(key_press)        

    else:   

        raise Exception(f'Error, {xpath} not found.')



# %%

#------------------------------------------------ Begin_Main ----------------------------------------

driver.get('https://www.cnbv.gob.mx/Paginas/BusquedaEntidades.aspx')

sleep(2)

driver.switch_to.frame(driver.find_element(By.TAG_NAME, 'iframe'))

sleep(1)

xpath_retry('//button[@class="btn btn-primary"]')

sleep(10)

soup=BeautifulSoup(driver.page_source,"html.parser")

div=soup.find('div',{'id':'infoSector'})

table=div.find('table')

first_row=table.find('tr',{'id':'GridViewEntidad_DXDataRow0'})

trs=table.find_all('tr',{'class':'dxgvDataRow_Office2010Silver'})  



urls   = [] 

casfim = []

names  = []

sector = []

passurl = 0



tds=first_row.find_all("td")

casfim.append(tds[0].text.strip())

names.append(tds[1].text.strip()) 

sector.append(tds[3].text.strip())

urls.append('https://pes.cnbv.gob.mx'+ tds[4].find("a",href=True)["href"])



for tr in trs:      

    tds=tr.find_all("td")

    if len(tds)<4:

        continue



    casfim.append(tds[0].text.strip())

    names.append(tds[1].text.strip()) 

    sector.append(tds[3].text.strip())

    urls.append('https://pes.cnbv.gob.mx'+ tds[4].find("a",href=True)["href"])

   

for i, url in enumerate(urls):

    if sector[i] in regdict:

        print(f"[INFO] : url= {i+1}/{len(urls)}")

        driver.get(url)

        sleep(0.5)

        soup=BeautifulSoup(driver.page_source,'html.parser')

        details=soup.find('div',{'id':'tabDetails'}).find('table',{'align':'center'})

        tab=soup.find('ul',{'class':'nav-tabs'})

        all_adress = ''



        if 'DIRECCIONES' in tab.text :

            adress=soup.find('div',{'id':'tabAdresses'}).find('table').find('table')

            tradress=adress.find_all('tr',{'id':"GridViewDireccion_DXDataRow0"})

            for tr in tradress:      

                tdaddress=tr.find_all("td")

                all_adress = tdaddress[1].text.strip()

                break

            print(f"[INFO] : {casfim[i]} | adress = {all_adress}")

        

        sqldict["Name"].append(names[i])

        sqldict["Address_1"].append(all_adress.strip())

        sqldict["ListProcessDate"].append(processdate)  

        sqldict["RegulationType"].append('Supervised')                

        sqldict["RegCtry"].append("MX")

        sqldict["Cntry"].append('MX')                 

        sqldict["RegCode"].append("CNBV")

        sqldict["ListCode"].append(regdict[sector[i]])

        

        if len(casfim[i])>0:

            sqldict['InternalID_1'].append(casfim[i])

            sqldict['InternalID_1_type'].append('CASFIM')

        else:

            sqldict['InternalID_1'].append("")

            sqldict['InternalID_1_type'].append("")



        if sector[i] == "PARTICIPANTES EN REDES DE MEDIOS DE DISPOSICIÓN RELEVANTES":

            for item in sqldict:

                if item == "ListCode":

                    sqldict[item].append('16')

                else:

                    sqldict[item].append(sqldict[item][-1])





    else:

        passurl+=1



print(f"[INFO] : number url not processed = {passurl}")

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
    