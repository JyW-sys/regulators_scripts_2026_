# DO SSDO Regulatory Lists

Superintendencia de Seguros de la Republica Dominicana (SSDO) - Dominican Republic insurance regulator. The public register lists all authorized insurance and reinsurance companies on a single Spanish-language page. The page sits behind a **Cloudflare "Just a moment…" challenge**, so plain `requests` returns 403 — the scraper uses **DrissionPage** (real Chrome) to pass Cloudflare, then parses the rendered HTML with BeautifulSoup (same approach as `CW CBCSCW`).

Layout: one `<table>` with **2 companies per row** (each `<td>` is a full company block). Within a cell the fields are `<br>`-separated:

```
<strong>Name</strong><br>
address line<br> address line<br>
Tel.: (809) … · Fax: (809) …<br>
Email: <a href="mailto:…">…</a>[<br> www.site]
```

Name comes from `<strong>`, email from the `mailto:` link, phone/fax via number regex on the `Tel.`/`Fax` line, website from a `www.`/`http` line, and City is the comma-segment before the `R.D.`/`D.N.` marker. `Cntry` is set to `DO` directly (no translation — Spanish entries are proper nouns / place names).

| RegCtry | RegCode | ListNr | ListName | URL | Comments |
|---------|---------|--------|----------|-----|----------|
| DO | SSDO | 1 | Compañías Aseguradoras | https://sis.gob.do/companias-aseguradoras-y-reaseguradoras/ | Cloudflare-protected (use DrissionPage). Single static table, ~35 entities, 2 per row, no pagination. Extract every entity. |

## Run

```
py -3 "DO SSDO\DO_SSDO_v1.py"
```

Output: `DO SSDO/DO SSDO SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`, fixed 43-column project schema).

## Jira

DECD-4396 (epic DECD-3438, Regulators 2026 — Crawlers).
