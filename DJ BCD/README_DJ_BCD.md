# DJ BCD Regulatory Lists

Banque Centrale de Djibouti (BCD) — Djibouti central bank. All licensed
establishments are published on one French-language page as **7 TablePress
tables** (`<table class="tablepress">`), each headed by its category name. The
page is fully server-rendered (no Cloudflare / JS), so a plain
`requests` + BeautifulSoup parse is enough.

The 7 category tables roll up into the 4 Jira lists. Columns are mapped by
header **name** (two header schemas exist), not position. French is kept as-is
(Latin script, proper nouns / place names); `Cntry` is set to `DJ` directly.

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| DJ | BCD | 1 | Etablissements Bancaires | https://banque-centrale.dj/les-etablissements-agrees/ | Banques conventionnelles + Émetteurs de monnaie électronique + Fenêtres islamiques + Banques islamiques |
| DJ | BCD | 2 | Micro Finance | https://banque-centrale.dj/les-etablissements-agrees/ | Les Institutions de Microfinance |
| DJ | BCD | 3 | Institutions Financières Spécialisées | https://banque-centrale.dj/les-etablissements-agrees/ | Les Institutions Financières Spécialisées |
| DJ | BCD | 4 | Auxiliaires Financiers | https://banque-centrale.dj/les-etablissements-agrees/ | Les Auxiliaires Financiers |

Field mapping: `Nom`/`Raison sociale` → Name, `Sigle` → InternalID_1 (type
"Sigle"), `Adresse`/`Siège social` → Address_1, `Téléphone` → Phone,
`Agrément BCD` → RegulationDate, category heading → Typology.

## Run

```
py -3 "DJ BCD\DJ_BCD_v1.py"
```

Output into the `DJ BCD` folder: `DJ BCD SQL Ready <timestamp>.xlsx`
(sheet `SQL Ready`, fixed 43-column schema).

## Jira

DECD-4395 (epic DECD-3438, Regulators 2026 — Crawlers).
