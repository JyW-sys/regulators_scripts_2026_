"""
Offline re-run of BI BRB list 2 (Microfinance Supervision) OCR.

www.brb.bi has been unreachable since ~12:13 today (TCP blackhole, WinError 10060
on the control server / proxy 502 + connect timeout here), so the page cannot be
fetched. The 12 source PNGs were downloaded live at 11:53 today and are still in
tempfolder/, and download_list2_images() only fetches when the local file is
absent -- so the OCR half of the pipeline is testable without the network.

Only the fetch is stubbed. split_pages -> page_headings -> page_tables ->
map_columns -> add_row all run exactly as parse_list2 calls them.

Not a permanent part of the scraper. Delete after the check.
"""
import glob
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import BI_BRB_v3 as B     # main() is guarded by __name__, so this does not run the scrape

# The page lists the images in document order and split_pages/OCR results are
# concatenated in that order, so sort numerically, not lexically (image_10 < image_2).
originals = sorted(
    glob.glob(os.path.join(B.tempfolder, 'image_*.png')),
    key=lambda p: int(re.search(r'image_(\d+)\.png$', os.path.basename(p)).group(1)))

print('[TEST] reusing {} cached PNGs: {}'.format(
    len(originals), ', '.join(os.path.basename(p) for p in originals)), flush=True)

B.download_list2_images = lambda soup, session: originals

# The node/120 HTML is not cached, so there is no text to read the validity date
# out of. This morning's live run also produced an empty ListValidityDate for
# list 2, so passing an empty soup changes nothing about the comparison.
soup = BeautifulSoup('', 'html.parser')

kept = B.parse_list2(soup, '2', B.REGLIST['2'], None)
print('[TEST] parse_list2 returned {} rows'.format(kept), flush=True)

import pandas as pd
df = pd.DataFrame(B.sqldict)
df.to_excel(os.path.join(B.scriptfolder, '_offline_ocr_test_list2.xlsx'),
            sheet_name='SQL Ready', index=False)
print('[TEST] wrote _offline_ocr_test_list2.xlsx ({} rows)'.format(len(df)), flush=True)
