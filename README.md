# Regulator Scrapers

Python scripts for scraping authorised-firm registers from financial regulators around the world. Each top-level folder is named `<ISO country code> <regulator code>` (e.g. `GB PRA`, `US FED`, `IT CONSOB`) and contains the scraper script(s) and a folder-specific README for that regulator.

## Repository layout

- `AG FSRCAG`
- `AI AFSC`
- `AL AFSA`
- `AT FMAT`
- `AU APRA`
- `BA BARS`
- `BA FBIH`
- `BA KOMVP`
- `BD BDCB`
- `BD CBBAN`
- `BD IDRABD`
- `BE BNBE`
- `BE FSMA`
- `BG FSC`
- `BI BRB`
- `BM BMA`
- `BN AMBD`
- `BO APS`
- `BO ASFI`
- `BR BCB`
- `BT RMA`
- `BZ CBBEL`
- `CA AMF`
- `CA CIRO`
- `CA FSRA`
- `CA OSFI`
- `CD BCCO`
- `CF CEMACCF`
- `CH FINMA`
- `CL CMF`
- `CN CSRC`
- `CN NFRA`
- `CO SFCO`
- `CR SUGEVAL`
- `CR SUPEN`
- `CV BCV`
- `CW CBCSCW`
- `CY CBTRNC`
- `CY ICCS`
- `CZ CNBCZ`
- `DE BAFIN`
- `DM FSU`
- `EC SIBE`
- `ECCB`
- `ES BES`
- `ES CNMV`
- `ET NBE`
- `FI FINFSA`
- `FR ACP`
- `GB FCAUK`
- `GB GFSC`
- `GB PRA`
- `GB TCIFSC`
- `GN BCRG`
- `GT SIB`
- `HK HKMA`
- `HK IAHK`
- `HK SFCHK`
- `HU CBH`
- `ID BI`
- `ID OJK`
- `IE CBIRE`
- `II_CAN BCFSA`
- `II_USA NYSBD`
- `II_USA_XXX`
- `IL BIS`
- `IN RBI`
- `IN SEBI`
- `IS CBI`
- `IT CONSOB`
- `IT IVASS`
- `JP FSAJP`
- `KR FSS`
- `KW CBKU`
- `KY CIM`
- `KZ AFSAKZ`
- `KZ ARDFM`
- `KZ NBKA`
- `LB BLI`
- `LC FSRALC`
- `LI FMAL`
- `LV CBOL`
- `MC CCAF`
- `MD CNPF`
- `MD NBMO`
- `MM CBM`
- `MN CBMONG`
- `MS MFSC`
- `MT MFSA`
- `MW RBM`
- `MX CNBV`
- `MX CNSF`
- `MY CBMAL`
- `MY LFSA`
- `NL AFM`
- `NO FNET`
- `NZ CIFSC`
- `NZ RBNZ`
- `PT BPOR`
- `PT CMVM`
- `PT ISPT`
- `QA QCB`
- `RO ASFR`
- `RO NBRO`
- `RS NBSRS`
- `SA SAMA`
- `SC SFSA`
- `SD CBOS`
- `SE FI`
- `SG MAS`
- `SM BCSM`
- `SY CBSYR`
- `TH BTHAI`
- `TL BCTL`
- `TM CBTUR`
- `TN CBTUN`
- `TT CBTT`
- `TW SFBTW`
- `UG BUG`
- `US CFPB`
- `US FCA`
- `US FDIC`
- `US FED`
- `US FFIEC`
- `US NAIC`
- `US NFA`
- `WS CBSAM`
- `YE CBYE`
- `ZA FSCA`
- `ZA JSE`
- `ZA NCR`
- `ZA SARB`

(`II_*` folders are insurance-industry regulators.)

## Requirements

- **Python 3.10+**
- **Google Chrome** + matching **ChromeDriver** (most scripts use Selenium / DrissionPage)
- **Tesseract OCR** (for scripts that read scanned PDFs / captcha images)
- **Poppler** (for `pdf2image` - PDF to image conversion)

### Install Python packages

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Install Tesseract OCR (Windows)

Download from https://github.com/UB-Mannheim/tesseract/wiki and install. Default install path is `C:\Program Files\Tesseract-OCR\`. Add it to PATH or set `pytesseract.pytesseract.tesseract_cmd` in the scripts.

### Install Poppler (Windows)

Download a release from https://github.com/oschwartz10612/poppler-windows/releases. Extract to e.g. `C:\Program Files\poppler-25.12.0\`. Add `...\Library\bin` to PATH or pass `poppler_path=` to `pdf2image.convert_from_path`.

### ChromeDriver

Either install `webdriver-manager` (already in `requirements.txt`) so Selenium downloads the right driver automatically, or download manually from https://googlechromelabs.github.io/chrome-for-testing/ and place it on PATH.

## Running a scraper

Each regulator folder is self-contained. Inside its folder run:

```powershell
python "GB PRA\GB PRA_v1_4.py"
```

Some scripts contain hard-coded absolute paths (`C:\Users\wuj1\OneDrive - Moody's\Desktop\Regulator\...`). The recommended replacement is:

```python
scriptfolder = os.path.dirname(os.path.abspath(__file__))
```

Several scripts already have this line ready, commented out.

## Notes

- This repo contains **scripts only**. The data outputs (`*.csv`, `*.xlsx`, `*.pdf`) and the per-regulator `tempfolder/` working directories are intentionally git-ignored.
- Bundled binaries (Tesseract, Poppler, ChromeDriver) are git-ignored - install separately as described above.
