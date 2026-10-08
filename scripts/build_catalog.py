#!/usr/bin/env python3
"""Builds catalog.json from sources/curated.json and eBible.org's list of translations.

    python3 scripts/build_catalog.py            # uses the cached translations.csv and sizes
    python3 scripts/build_catalog.py --refresh  # fetches translations.csv again and re-measures sizes

Every eBible.org translation that is downloadable, freely redistributable, and has at least a
whole testament (counting a Septuagint's deuterocanonical books) is included. Tanakh editions go under Judaism; the rest under Christianity.
"""
import csv
import datetime
import io
import json
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'sources'
CACHE = ROOT / '.cache'
USER_AGENT = 'notetwo-texts catalog builder (https://github.com/benslen/notetwo-texts)'

# eBible.org translations that belong to Judaism rather than Christianity.
JEWISH = {'engjps', 'englee', 'engoke', 'hbo', 'hboWLC', 'hebwlc'}

# ISO 639-3 codes to the two-letter codes apps use, where one exists.
TWO_LETTER = {
    'afr': 'af', 'amh': 'am', 'arb': 'ar', 'ara': 'ar', 'asm': 'as', 'aze': 'az', 'bel': 'be', 'ben': 'bn', 'bod': 'bo', 'bos': 'bs',
    'bul': 'bg', 'cat': 'ca', 'ces': 'cs', 'cmn': 'zh', 'cym': 'cy', 'dan': 'da', 'deu': 'de', 'ell': 'el', 'eng': 'en', 'epo': 'eo',
    'est': 'et', 'eus': 'eu', 'fao': 'fo', 'fas': 'fa', 'pes': 'fa', 'fin': 'fi', 'fra': 'fr', 'gle': 'ga', 'glg': 'gl', 'grc': 'grc',
    'guj': 'gu', 'hat': 'ht', 'hau': 'ha', 'haw': 'haw', 'hbo': 'hbo', 'heb': 'he', 'hin': 'hi', 'hrv': 'hr', 'hun': 'hu', 'hye': 'hy',
    'ibo': 'ig', 'ind': 'id', 'isl': 'is', 'ita': 'it', 'jpn': 'ja', 'kan': 'kn', 'kat': 'ka', 'kaz': 'kk', 'khm': 'km', 'kin': 'rw',
    'kir': 'ky', 'kor': 'ko', 'lao': 'lo', 'lat': 'la', 'lav': 'lv', 'lit': 'lt', 'mal': 'ml', 'mar': 'mr', 'mkd': 'mk', 'mlg': 'mg',
    'mlt': 'mt', 'mon': 'mn', 'mri': 'mi', 'msa': 'ms', 'zsm': 'ms', 'mya': 'my', 'nep': 'ne', 'npi': 'ne', 'nld': 'nl', 'nob': 'nb',
    'nno': 'nn', 'nor': 'no', 'nya': 'ny', 'ori': 'or', 'ory': 'or', 'orm': 'om', 'pan': 'pa', 'pol': 'pl', 'por': 'pt', 'pus': 'ps',
    'ron': 'ro', 'rus': 'ru', 'sin': 'si', 'slk': 'sk', 'slv': 'sl', 'smo': 'sm', 'sna': 'sn', 'som': 'so', 'spa': 'es', 'sqi': 'sq',
    'srp': 'sr', 'swa': 'sw', 'swh': 'sw', 'swe': 'sv', 'tam': 'ta', 'tel': 'te', 'tgk': 'tg', 'tgl': 'tl', 'tha': 'th', 'tir': 'ti',
    'ton': 'to', 'tsn': 'tn', 'tur': 'tr', 'twi': 'tw', 'uig': 'ug', 'ukr': 'uk', 'urd': 'ur', 'uzb': 'uz', 'uzn': 'uz', 'vie': 'vi',
    'wol': 'wo', 'xho': 'xh', 'yor': 'yo', 'yue': 'yue', 'zho': 'zh', 'zul': 'zu', 'fij': 'fj', 'tpi': 'tpi', 'cop': 'cop', 'syc': 'syc',
}
LANGUAGE_NAMES = {'en': 'English', 'zh': 'Chinese', 'de': 'German', 'fr': 'French', 'sv': 'Swedish', 'nl': 'Dutch', 'ar': 'Arabic'}


def fetch(url, timeout=60):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def content_length(url):
    request = urllib.request.Request(url, method='HEAD', headers={'User-Agent': USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            length = response.headers.get('Content-Length')
            return int(length) if length else None
    except Exception:
        return None


def translations(refresh):
    path = CACHE / 'translations.csv'
    if refresh or not path.exists():
        CACHE.mkdir(exist_ok=True)
        path.write_bytes(fetch('https://ebible.org/Scriptures/translations.csv'))
    return list(csv.DictReader(io.StringIO(path.read_text(encoding='utf-8-sig'))))


def number(value):
    try:
        return int(value or 0)
    except ValueError:
        return 0


def ebible_editions(rows):
    editions = {'christianity': [], 'judaism': []}
    for row in rows:
        ot, nt, dc = number(row['OTbooks']), number(row['NTbooks']), number(row['DCbooks'])
        # A whole testament; Septuagints count their deuterocanonical books toward the Old Testament.
        if row['downloadable'] != 'True' or row['Redistributable'] != 'True' or (ot + dc < 39 and nt < 27):
            continue
        tid = row['translationId']
        jewish = tid in JEWISH
        title = (row['shortTitle'] or row['title']).strip()
        lowered = (title + ' ' + row['description']).lower()
        if jewish:
            work = 'Targum' if 'targum' in lowered else 'Tanakh'
        elif 'septuag' in title.lower() or 'lxx' in title.lower():
            work = 'Septuagint'
        elif ot >= 39 and nt >= 27:
            work = 'Bible'
        elif nt >= 27:
            work = 'New Testament'
        else:
            work = 'Old Testament'
        parts = []
        if ot:
            parts.append('Hebrew Scriptures' if jewish else 'Old Testament')
        if nt:
            parts.append('New Testament')
        contents = ' and '.join(parts) + (f', with {dc} deuterocanonical books' if dc else '')
        code = row['languageCode']
        copyright = row['Copyright'].strip()
        public = 'public domain' in copyright.lower()
        edition = {
            'id': f'ebible:{tid}',
            'work': work,
            'title': title,
            'description': row['description'].strip(),
            'contents': contents,
            'language': TWO_LETTER.get(code, code),
            'languageName': row['languageNameInEnglish'].strip() or row['languageName'].strip(),
            'nativeLanguageName': row['languageName'].strip(),
            'direction': 'rtl' if row['textDirection'] == 'rtl' else 'ltr',
            'format': 'usfm-verses',
            'url': f'https://ebible.org/Scriptures/{tid}_vpl.zip',
            'file': f'{tid}_vpl.txt',
            'source': f'https://ebible.org/details.php?id={tid}',
            'publisher': 'eBible.org',
            'license': 'Public domain' if public else f'{copyright}. Shared freely through eBible.org.',
        }
        editions['judaism' if jewish else 'christianity'].append(edition)
    return editions


def curated_edition(edition):
    edition = dict(edition)
    kind, _, key = edition['id'].partition(':')
    if kind == 'gutenberg':
        edition.setdefault('url', f'https://www.gutenberg.org/cache/epub/{key}/pg{key}.txt')
        edition.setdefault('source', f'https://www.gutenberg.org/ebooks/{key}')
        edition.setdefault('publisher', 'Project Gutenberg')
        edition.setdefault('license', 'Public domain in the United States')
    elif kind == 'archive':
        edition.setdefault('source', f'https://archive.org/details/{key}')
        edition.setdefault('publisher', 'Internet Archive')
        edition.setdefault('license', 'Public domain (published before 1930)')
    edition.setdefault('languageName', LANGUAGE_NAMES.get(edition['language'], edition['language']))
    edition.setdefault('direction', 'ltr')
    if edition.get('scanned'):
        edition.setdefault('description', 'Text read from page images of the printed book, so expect occasional misread words and stray page headers.')
    return edition


def sort_key(edition):
    return (edition['language'] != 'en', edition['languageName'].casefold(), edition['work'].casefold(), edition['title'].casefold())


def main():
    refresh = '--refresh' in sys.argv
    curated = json.loads((SOURCES / 'curated.json').read_text())
    books = {k: v for k, v in json.loads((SOURCES / 'books.json').read_text()).items() if not k.startswith('_')}
    surahs = json.loads((SOURCES / 'surahs.json').read_text())['surahs']
    from_ebible = ebible_editions(translations(refresh))

    religions = []
    for religion in curated['religions']:
        editions = [curated_edition(e) for e in religion['editions']] + from_ebible.get(religion['id'], [])
        religions.append({'id': religion['id'], 'name': religion['name'], 'editions': sorted(editions, key=sort_key)})
    religions.sort(key=lambda r: r['name'].casefold())

    # Download sizes, remembered between runs so a rebuild doesn't ask every server again.
    sizes_path = SOURCES / 'sizes.json'
    sizes = {} if refresh or not sizes_path.exists() else json.loads(sizes_path.read_text())
    missing = [e for r in religions for e in r['editions'] if e['id'] not in sizes]
    with ThreadPoolExecutor(max_workers=6) as pool:
        for edition, size in zip(missing, pool.map(lambda e: content_length(e['url']), missing)):
            if size:
                sizes[edition['id']] = size
    sizes_path.write_text(json.dumps(dict(sorted(sizes.items())), indent=0) + '\n')
    for religion in religions:
        for edition in religion['editions']:
            if edition['id'] in sizes:
                edition['size'] = sizes[edition['id']]

    ids = [e['id'] for r in religions for e in r['editions']]
    assert len(ids) == len(set(ids)), 'Edition IDs must be unique'
    catalog = {
        'schema': 1,
        'updated': datetime.date.today().isoformat(),
        'about': 'Religious and sacred texts that are free to read, grouped by religion, with where to download each. Made for NoteTwo; anyone may use it.',
        'books': books,
        'surahs': surahs,
        'religions': religions,
    }
    (ROOT / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=1) + '\n')
    print(f'{len(religions)} religions, {len(ids)} editions:')
    for religion in religions:
        languages = {e['language'] for e in religion['editions']}
        print(f"  {religion['name']}: {len(religion['editions'])} editions in {len(languages)} languages")


if __name__ == '__main__':
    main()
