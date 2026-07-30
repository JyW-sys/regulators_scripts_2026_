# -*- coding: utf-8 -*-
# ------------------------------------------------------------------
# List PDF Generator — Streamlit app (Databricks Apps)
#
# Upload one or more "SQL Ready" .xlsx workbooks; get back one PDF per
# (RegCtry, RegCode, ListCode) combination, named
# "RegCtry RegCode SQL Ready <date-time from the file's own name>- ListCode.pdf",
# same list layout as the standalone list_pdf_generator.py (32 names/page, "Name" header).
#
# Helpers (safe_filename / draw_header / export_list_to_pdf) ported from
# list_pdf_generator.py; export_list_to_pdf now returns bytes instead of
# writing to disk, since Databricks Apps has no persistent local filesystem.
# ------------------------------------------------------------------
import io
import os
import re
import zipfile
from datetime import date

import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

REQUIRED_COLUMNS = ('Name', 'RegCtry', 'RegCode', 'ListCode')

# Matches "... SQL Ready <anything>" and captures the <anything> -- the workbook's
# own filename carries its date/time after "SQL Ready ", e.g.
# "XX BCEAO SQL Ready 2026-07-10 12.32.59.xlsx" -> "2026-07-10 12.32.59".
SQL_READY_DATETIME_RE = re.compile(r'SQL Ready\s+(.+)$', re.IGNORECASE)


def extract_source_datetime(base_name):
    m = SQL_READY_DATETIME_RE.search(base_name)
    return m.group(1).strip() if m else None

# ------ font: bundled DejaVu Sans (Unicode), fall back to Helvetica ------
scriptdir = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(scriptdir, 'fonts', 'DejaVuSans.ttf')
FONT_NAME = 'Helvetica'
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('ArialUni', FONT_PATH))
    FONT_NAME = 'ArialUni'


def safe_filename(name):
    name = str(name).strip()
    return re.sub(r'[\\/:*?"<>|]+', '_', name) or "UNKNOWN"


def draw_header(c, y):
    c.setFont(FONT_NAME, 14)
    c.drawString(72, y, "Name")
    c.line(72, y - 4, 540, y - 4)
    c.setFont(FONT_NAME, 12)
    return y - 24


def export_list_to_pdf(data_list):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
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
    return buf.getvalue()


def process_workbook(filename, raw_bytes):
    """Returns (rows, warning) where rows is a list of
    (pdf_filename, pdf_bytes, name_count) and warning is None or a message."""
    df = pd.read_excel(io.BytesIO(raw_bytes))
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        return [], f"missing column(s) {missing}"

    base_name = os.path.splitext(filename)[0]
    source_datetime = extract_source_datetime(base_name)
    if source_datetime is None:
        return [], f'filename must contain "SQL Ready <date-time>" (got "{filename}")'

    rows = []
    for (regctry, regcode, list_code), group in df.groupby(
        ['RegCtry', 'RegCode', 'ListCode'], dropna=False
    ):
        items = group['Name'].dropna().astype(str).tolist()
        if not items:
            continue
        regctry_safe = safe_filename(regctry)
        regcode_safe = safe_filename(regcode)
        list_code_safe = safe_filename(list_code)
        pdf_filename = (
            f"{regctry_safe} {regcode_safe} SQL Ready {source_datetime}- {list_code_safe}.pdf"
        )
        pdf_bytes = export_list_to_pdf(items)
        rows.append((pdf_filename, pdf_bytes, len(items)))
    return rows, None


# ------------------------------ UI ------------------------------
st.set_page_config(page_title="List PDF Generator", page_icon="📄")
st.title("📄 List PDF Generator")
st.caption(
    "Upload one or more “SQL Ready” .xlsx workbooks. "
    "You'll get one PDF per (RegCtry, RegCode, ListCode) combination — a single-column "
    "list of Names, 32 per page — named "
    "“RegCtry RegCode SQL Ready <date-time from the file's own name>- ListCode.pdf”."
)
if FONT_NAME == 'Helvetica':
    st.warning(
        "Bundled font not found — using Helvetica. Non-Latin names may not render correctly."
    )

uploaded_files = st.file_uploader(
    "SQL Ready workbook(s)", type=["xlsx"], accept_multiple_files=True
)

if uploaded_files:
    all_pdfs = []  # (pdf_filename, pdf_bytes)
    summary_rows = []  # (workbook, pdf_filename, name_count)

    for f in uploaded_files:
        rows, warning = process_workbook(f.name, f.getvalue())
        if warning:
            st.warning(f"Skipped **{f.name}**: {warning}")
            continue
        if not rows:
            st.info(f"**{f.name}**: no rows to export.")
            continue
        for pdf_filename, pdf_bytes, name_count in rows:
            all_pdfs.append((pdf_filename, pdf_bytes))
            summary_rows.append({"Workbook": f.name, "PDF": pdf_filename, "Names": name_count})

    if all_pdfs:
        st.subheader(f"Generated {len(all_pdfs)} PDF(s)")
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for pdf_filename, pdf_bytes in all_pdfs:
                zf.writestr(pdf_filename, pdf_bytes)

        st.download_button(
            "⬇️ Download all as ZIP",
            data=zip_buf.getvalue(),
            file_name=f"list_pdfs_{date.today().isoformat()}.zip",
            mime="application/zip",
            type="primary",
        )

        with st.expander("Download individual PDFs"):
            for pdf_filename, pdf_bytes in all_pdfs:
                st.download_button(
                    pdf_filename,
                    data=pdf_bytes,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    key=pdf_filename,
                )
else:
    st.info("Waiting for a workbook upload.")
