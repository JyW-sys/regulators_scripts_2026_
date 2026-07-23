"""Dry-run parser validation for DZ BAL.

Mirrors the notebook's parsing functions but runs without Selenium/Chrome.
Prints per-category counts and a sample of fields so we can sanity-check selectors
before running the full notebook.
"""
import io
import re
import sys
import urllib.request
from bs4 import BeautifulSoup

# Force stdout to UTF-8 so French characters render in Windows consoles.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CATEGORY_PAGES = [
    ('https://www.bank-of-algeria.dz/banques-commerciales-2/',                                    'Commercial Bank'),
    ('https://www.bank-of-algeria.dz/etablissement-financiers-a-vocation-generale/',              'Financial Establishment - General Purpose'),
    ('https://www.bank-of-algeria.dz/etablissements-financiers-a-vocation-specifique/',           'Financial Establishment - Specific Purpose'),
    ('https://www.bank-of-algeria.dz/bureaux-de-representation/',                                 'Representation Office'),
    ('https://www.bank-of-algeria.dz/association-des-banques-et-des-etablissements-financiers-abef/', 'Banking Association'),
]

LABEL_RE = re.compile(
    r'(Si[èe]ge\s*Social|Adresse|'
    r'T[ée]l[ée]phone|DGA|Agence[^:–\n]{0,40}|'
    r'Fax|'
    r'Pr[ée]sident\s*Directeur\s*G[ée]n[ée]ral|Directeur\s*G[ée]n[ée]ral|Directrice\s*G[ée]n[ée]rale|'
    r'Pr[ée]sident\s*du\s*Directoire|Directeur\s*Ex[ée]cutif|Repr[ée]sentante?)'
    r'\s*[:–]\s*',
    re.IGNORECASE,
)
LABEL_FIELD = (
    ('address',  re.compile(r'^(Si[èe]ge\s*Social|Adresse)$', re.IGNORECASE)),
    ('phone',    re.compile(r'^(T[ée]l[ée]phone|DGA|Agence)', re.IGNORECASE)),
    ('fax',      re.compile(r'^Fax$', re.IGNORECASE)),
    ('director', re.compile(r'^(Directeur|Directrice|Pr[ée]sident|Repr[ée]sentante?)', re.IGNORECASE)),
)
ENTITY_TEXT_MARKERS = ('Téléphone', 'Telephone', 'Siège Social', 'Siege Social', 'Adresse', 'Fax')


def _classify(label):
    label = label.strip()
    for field, pat in LABEL_FIELD:
        if pat.match(label):
            return field
    return None


def parse_detail_block(p_text):
    text = p_text.replace('\xa0', ' ')
    parsed = {'address': '', 'phone': [], 'fax': [], 'director': ''}
    matches = list(LABEL_RE.finditer(text))
    if not matches:
        return {'address': '', 'phone': '', 'fax': '', 'director': ''}
    for i, m in enumerate(matches):
        label = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[start:end].strip(' \t\n\r–-,;')
        value = re.sub(r'\s+', ' ', value)
        if not value:
            continue
        field = _classify(label)
        if field == 'address':
            if not parsed['address']:
                parsed['address'] = value
        elif field == 'phone':
            parsed['phone'].append(value)
        elif field == 'fax':
            parsed['fax'].append(value)
        elif field == 'director' and not parsed['director']:
            parsed['director'] = value
    parsed['phone'] = ' / '.join(parsed['phone'])
    parsed['fax'] = ' / '.join(parsed['fax'])
    return parsed


def extract_entities_from_page(html):
    soup = BeautifulSoup(html, 'html.parser')
    results = []
    for heading in soup.select('h2.elementor-heading-title'):
        wrap = heading.find_parent(class_='elementor-widget-wrap')
        if wrap is None:
            wrap = heading.find_parent(class_=re.compile(r'elementor-(column|widget-wrap|element-populated)'))
        if wrap is None:
            continue
        text_widget = wrap.find(class_='elementor-widget-text-editor')
        if text_widget is None:
            continue
        p_el = text_widget.find('p')
        if p_el is None:
            continue
        block_text = p_el.get_text('\n').strip()
        if not any(marker.lower() in block_text.lower() for marker in ENTITY_TEXT_MARKERS):
            continue
        name = heading.get_text(' ', strip=True).replace('“', '"').replace('”', '"').strip()
        if not name:
            continue
        results.append((name, parse_detail_block(block_text)))
    return results


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', errors='replace')


def main():
    grand_total = 0
    missing_director = 0
    missing_phone = 0
    missing_address = 0
    for url, cotype in CATEGORY_PAGES:
        print(f'\n=== {cotype}  ({url}) ===')
        try:
            html = fetch(url)
        except Exception as e:
            print(f'  FETCH FAILED: {e}')
            continue
        entities = extract_entities_from_page(html)
        print(f'  parsed entities: {len(entities)}')
        grand_total += len(entities)
        for name, parsed in entities:
            if not parsed['director']:
                missing_director += 1
            if not parsed['phone']:
                missing_phone += 1
            if not parsed['address']:
                missing_address += 1
        for name, parsed in entities[:3]:
            print(f'  - {name}')
            print(f'      addr    : {parsed["address"][:160]}')
            print(f'      phone   : {parsed["phone"][:160]}')
            print(f'      fax     : {parsed["fax"][:160]}')
            print(f'      director: {parsed["director"][:80]}')
        if len(entities) > 3:
            print(f'  ... +{len(entities) - 3} more')
    print(f'\nGRAND TOTAL: {grand_total}')
    print(f'missing director : {missing_director}/{grand_total}')
    print(f'missing phone    : {missing_phone}/{grand_total}')
    print(f'missing address  : {missing_address}/{grand_total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
