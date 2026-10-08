#!/usr/bin/env python3
"""Checks catalog.json: its shape, that every download link answers, and (with --deep) that each
hand-picked text downloads and splits into the sections its heading pattern promises.

    python3 scripts/check_catalog.py          # shape and links
    python3 scripts/check_catalog.py --deep   # also downloads and reads every non-eBible edition

Exits non-zero if anything is wrong, so it can run on a schedule.
"""
import io
import json
import re
import sys
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.cache' / 'downloads'
USER_AGENT = 'notetwo-texts catalog checker (https://github.com/benslen/notetwo-texts)'
FORMATS = {'gutenberg', 'plain', 'tanzil', 'usfm-verses'}
REQUIRED = ('id', 'work', 'title', 'language', 'languageName', 'direction', 'format', 'url', 'source', 'publisher', 'license')


def request(url, method='GET', headers=None):
    return urllib.request.Request(url, method=method, headers={'User-Agent': USER_AGENT, **(headers or {})})


def answers(url):
    """True if the link works. Some servers refuse HEAD, so a one-byte GET is the fallback, and
    archive.org is sometimes slow, so each is tried twice."""
    for method, headers in (('HEAD', {}), ('GET', {'Range': 'bytes=0-0'})) * 2:
        try:
            with urllib.request.urlopen(request(url, method, headers), timeout=60) as response:
                if response.status in (200, 206):
                    return True
        except Exception:
            continue
    return False


def download(edition):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (re.sub(r'[^A-Za-z0-9._-]', '_', edition['id']) + '.bin')
    if not path.exists():
        with urllib.request.urlopen(request(edition['url']), timeout=300) as response:
            path.write_bytes(response.read())
    data = path.read_bytes()
    if edition['format'] == 'usfm-verses':
        data = zipfile.ZipFile(io.BytesIO(data)).read(edition['file'])
    return data.decode('utf-8-sig').replace('\r\n', '\n')


def gutenberg_body(text):
    start = re.search(r'^\*\*\* ?START OF (?:THE|THIS) PROJECT GUTENBERG.*$', text, re.M)
    end = re.search(r'^\*\*\* ?END OF (?:THE|THIS) PROJECT GUTENBERG', text, re.M)
    return text[start.end() if start else 0:end.start() if end else len(text)]


def deep_check(edition):
    text = download(edition)
    fmt = edition['format']
    if fmt == 'usfm-verses':
        verses = re.findall(r'^[0-9A-Z]{3} \d+:\d+ ', text, re.M)
        return len(verses) > 1000, f'{len(verses)} verses'
    if fmt == 'tanzil':
        verses = re.findall(r'^\d+\|\d+\|', text, re.M)
        return len(verses) == 6236, f'{len(verses)} verses'
    body = gutenberg_body(text) if fmt == 'gutenberg' else text
    # Short texts are fine (the Sutra of Forty-two Sections is 4,500 characters); empty ones aren't.
    if len(body) < 2000:
        return False, f'only {len(body)} characters'
    if 'headings' in edition:
        count = len(re.findall(edition['headings']['pattern'], body, re.M))
        return count >= 3, f'{count} sections'
    return True, f'{len(body)} characters'


def main():
    deep = '--deep' in sys.argv
    catalog = json.loads((ROOT / 'catalog.json').read_text())
    problems = []
    editions = [e for r in catalog['religions'] for e in r['editions']]
    for edition in editions:
        missing = [k for k in REQUIRED if not edition.get(k)]
        if missing:
            problems.append(f"{edition.get('id')}: missing {', '.join(missing)}")
        if edition.get('format') not in FORMATS:
            problems.append(f"{edition['id']}: unknown format {edition.get('format')}")
        if edition.get('format') == 'usfm-verses' and not edition.get('file'):
            problems.append(f"{edition['id']}: a zip needs the file to read")
        if not edition.get('url', '').startswith('https://'):
            problems.append(f"{edition['id']}: links must be https")
        if 'headings' in edition:
            try:
                re.compile(edition['headings']['pattern'])
            except re.error as error:
                problems.append(f"{edition['id']}: bad heading pattern ({error})")

    with ThreadPoolExecutor(max_workers=8) as pool:
        for edition, ok in zip(editions, pool.map(lambda e: answers(e['url']), editions)):
            if not ok:
                problems.append(f"{edition['id']}: {edition['url']} didn't answer")

    if deep:
        for edition in editions:
            if edition['format'] == 'usfm-verses' and edition['id'] not in ('ebible:engwebp', 'ebible:eng-kjv', 'ebible:hboWLC'):
                continue
            try:
                ok, detail = deep_check(edition)
            except Exception as error:
                ok, detail = False, str(error)
            print(f"{'ok ' if ok else 'BAD'} {edition['id']}: {detail}")
            if not ok:
                problems.append(f"{edition['id']}: {detail}")

    print(f'{len(editions)} editions checked.')
    for problem in problems:
        print('PROBLEM', problem)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
