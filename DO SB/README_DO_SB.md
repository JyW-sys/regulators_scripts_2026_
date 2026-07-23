# DO SB  -  Superintendencia de Bancos de la Republica Dominicana
# Source: https://www.sb.gob.do/supervisados/
# Jira:   DECD-4397  (epic DECD-3438, Regulators 2026 - Crawlers)
#
# The supervisados site is fully server-rendered, so a simple
# requests + BeautifulSoup walk is enough (no Selenium / JS needed).
#
#   Each listing page -> entity cards (a.name_container) -> detail page.
#   Each detail page exposes its fields as repeated blocks:
#       <div class="info_title_value_container">
#           <label>Registro</label><span>H-001-1-00-0101</span>
#       </div>
#   We parse those label->value pairs and map the Spanish labels to the
#   project's SQL-Ready columns.
#
# Lists (from the Jira description):
#   ListNr 1  "Entidades Autorizadas"     -> 4 sections:
#                 - Entidades de Intermediacion Financiera
#                 - Entidades de Intermediacion Cambiaria
#                 - Fiduciarias
#                 - Sociedades de Informacion Crediticia
#   ListNr 2  "Oficinas de Representacion" -> oficinas-de-representacion