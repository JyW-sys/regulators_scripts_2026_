# PE SBS — Superintendencia de Banca, Seguros y AFP (Peru)

- **Source:** https://www.sbs.gob.pe/supervisados-y-registros/empresas-supervisadas
- **Jira:** DECD-4818 (epic DECD-3438, Regulators 2026 - Crawlers)
- **Script:** `PE_SBS_v1.py` (requests + BeautifulSoup + pandas + pdfplumber; no Selenium)
- **Output:** `tempfolder/PE SBS SQL Ready <timestamp>.xlsx`, sheet `SQL Ready`

## Three source mechanisms

**GROUP A — 15 "directorio" lists (table).**
Each list page embeds an `<iframe id="iframeSBS">` whose `src` is a data endpoint:
`/app/sadel/Paginas/Redir/ListarFuncionarios.aspx?codTpEntidad=<CODE>`. The endpoint
returns a plain HTML table (`Entidad | Cargo | Funcionario | Direccion | Telefono |
Fax | Fecha`). There is one row per officer, so we de-dup by `Entidad`, taking the
first non-empty value of each field. `codTpEntidad` codes are hard-coded in `regdict`.

**LIST 17 — Representantes de Empresas del Exterior (text).**
Free-text HTML, not a table: `<span class="subsubtitulo">` is the entity name and the
following `<span class="JERF_texto1">` holds `<br>`-separated `Domicilio:` / `Telf:` /
`E-mail:` / `Res. SBS N°` lines, which we parse line-by-line.

**LIST 19 — Cooperativas de Ahorro y Credito / COOPAC (pdf).**
The page links to a monthly PDF (`documentos.aspx?cod=COOPAC002` → 302 → `*.PDF`).
We download it and parse the ruled table with `pdfplumber.extract_tables()`
(columns: N° | Name | RUC | Nivel | N° Registro | Fecha | Nivel Ops | Region |
Provincia). pdfplumber detects overlapping table regions, so each COOPAC comes out
twice — we de-dup on RUC.

## Lists (from the Jira description)

| ListNr | ListName | codTpEntidad / handler |
|---|---|---|
| 1  | Empresas Bancarias | B |
| 2  | Empresas De Seguros | S |
| 3  | Administradoras De Fondos De Pensiones | FP |
| 4  | Empresas Financieras | F |
| 6  | Cajas Rurales De Ahorro Y Credito | R |
| 7  | Cajas Municipales | C |
| 8  | Empresas De Creditos | E |
| 9  | Cajas Y Derramas | DE |
| 10 | Empresa De Transferencia De Fondos | TF |
| 11 | Empresas Afianzadoras Y De Garantias | G |
| 12 | Almacenes Generales De Deposito | AG |
| 13 | Empresa De Transporte, Custodia Y Administracion De Numerario | TC |
| 14 | Empresa De Servicios Fiduciarios | FD |
| 15 | Fondo De Cajas Municipales | FF |
| 17 | Representantes De Empresas Del Exterior | text handler |
| 18 | Empresas Administradoras Hipotecarias | AH |
| 19 | Cooperativas De Ahorro Y Credito | pdf handler |

## Notes

- The site is served as **cp1252** despite declaring UTF-8 (`r.encoding = "cp1252"`).
  The Representantes page additionally mixes latin-1 and UTF-8 bytes, so a small
  `fix_mojibake()` pass re-decodes only the `Ã`/`Â` lead-byte sequences (e.g.
  `PerÃº` → `Perú`) while leaving already-correct chars (`ó`, `Ñ`) untouched.
- `RegCtry = PE`, `RegCode = SBS`, `RegulationType = Regulated`, `ListLanguage = ES`.
- `Phone` / `Fax` / `Email` non-empty rates are low — those columns are simply
  sparse at the source (the directory only lists them for some entities; the COOPAC
  PDF carries none).
