# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# List PDF Generator
#
# Standalone utility. Drop one or more "SQL Ready" .xlsx workbooks in THIS folder
# and run the script; it writes one PDF per (RegCtry, ListCode) pair into
# ./pdf_output/. Each PDF is a one-column dump of the entities' Name values
# (32 names per page, header line "Name").
#
# Helpers (safe_filename / draw_header / export_list_to_pdf) extracted from
# CW CBCSCW_v2.py so the PDF layout matches the existing regulator scripts.
# ------------------------------------------------------------------
import os
import re
import glob
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ------ workspace path (production .py or notebook) ------
try:
    scriptfolder = os.path.dirname(os.path.abspath(__file__))
except NameError:
    scriptfolder = os.getcwd()
os.chdir(scriptfolder)

outfolder = os.path.join(scriptfolder, 'pdf_output')
os.makedirs(outfolder, exist_ok=True)

# ------ font: prefer a Unicode TTF (Arial), fall back to Helvetica ------
FONT_NAME = 'Helvetica'
for _p in (r"C:\Windows\Fonts\arial.ttf",                    # Windows control server
           "/System/Library/Fonts/Supplemental/Arial.ttf",  # macOS
           "/Library/Fonts/Arial.ttf"):
    if os.path.exists(_p):
        pdfmetrics.registerFont(TTFont('ArialUni', _p))
        FONT_NAME = 'ArialUni'
        break
if FONT_NAME == 'Helvetica':
    print("WARNING: Arial TTF not found; using Helvetica (some non-Latin chars may not render).")


def safe_filename(name):
    name = str(name).strip()
    return re.sub(r'[\\/:*?"<>|]+', '_', name) or "UNKNOWN"


def draw_header(c, y):
    c.setFont(FONT_NAME, 14)
    c.drawString(72, y, "Name")
    c.line(72, y - 4, 540, y - 4)
    c.setFont(FONT_NAME, 12)
    return y - 24


def export_list_to_pdf(data_list, pdf_filename):
    c = canvas.Canvas(pdf_filename, pagesize=letter)
    c.setFont(FONT_NAME, 12)

    x = 72
    y = draw_header(c, 740)
    max_lines_per_page = 32
    line_count = 0

    for item in data_list:
        c.drawString(x, y, str(item))
        y -= 20
        line_count += 1

        if line_count >= max_lines_per_page:
            c.showPage()
            c.setFont(FONT_NAME, 12)
            y = draw_header(c, 740)
            line_count = 0

    c.save()


# ------ process every SQL-Ready .xlsx in this folder ------
xlsx_files = [f for f in glob.glob(os.path.join(scriptfolder, "*.xlsx"))
              if not os.path.basename(f).startswith("~$")]   # skip Excel lock files
if not xlsx_files:
    raise SystemExit("No .xlsx found in {}. Put a SQL Ready workbook here and re-run."
                     .format(scriptfolder))

for xlsx in xlsx_files:
    filename = os.path.basename(xlsx)
    df_pdf = pd.read_excel(xlsx)
    missing = [col for col in ('Name', 'RegCtry', 'ListCode') if col not in df_pdf.columns]
    if missing:
        print(f"[SKIP] {filename}: missing column(s) {missing}")
        continue

    base_name = os.path.splitext(filename)[0]
    made = 0
    # One PDF per unique (RegCtry, ListCode) pair: e.g. "...- CW-1.pdf", "...- SX-1.pdf".
    for (regctry, list_code), group in df_pdf.groupby(['RegCtry', 'ListCode'], dropna=False):
        items = group['Name'].dropna().astype(str).tolist()
        if not items:
            continue
        regctry_safe = safe_filename(regctry)
        list_code_safe = safe_filename(list_code)
        pdf_path = os.path.join(outfolder, f"{base_name} - {regctry_safe}-{list_code_safe}.pdf")
        export_list_to_pdf(items, pdf_path)
        made += 1
        print(f"[INFO] wrote {len(items)} names -> {os.path.relpath(pdf_path, scriptfolder)}")
    print(f"[OK] {filename}: {made} PDF(s)")
