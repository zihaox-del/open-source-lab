#!/usr/bin/env python3
"""Opt-in external-network fixture test. Not customer adoption or production data."""
import argparse
import json
import sys
import time
from pathlib import Path
from urllib.robotparser import RobotFileParser

BASE = 'https://books.toscrape.com'
MAIN = 'html > body > div > div > div:nth-of-type(2) > div:nth-of-type(2) > article'
FIELDS = [
    {'name': 'title', 'selector': 'h1'},
    {'name': 'price', 'selector': MAIN + ' > div:nth-of-type(1) > div:nth-of-type(2) > p:nth-of-type(1)'},
    {'name': 'upc', 'selector': MAIN + ' > table > tr:nth-of-type(1) > td'},
]
CASES = [
    ('a-light-in-the-attic_1000', {'title': 'A Light in the Attic', 'price': '£51.77', 'upc': 'a897fe39b1053632'}),
    ('tipping-the-velvet_999', {'title': 'Tipping the Velvet', 'price': '£53.74', 'upc': '90fa61229261140a'}),
    ('soumission_998', {'title': 'Soumission', 'price': '£50.10', 'upc': '6957f44c3847a760'}),
]

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project', required=True, type=Path)
    ap.add_argument('--allow-public-network', action='store_true')
    args = ap.parse_args()
    if not args.allow_public_network:
        ap.error('requires explicit --allow-public-network; default makes zero requests')
    sys.path.insert(0, str(args.project.resolve()))
    from websheet.core import Column, PinnedHTTPS, public_addresses, fetch, extract
    urls = [BASE + '/catalogue/' + slug + '/index.html' for slug, _ in CASES]
    fields = [Column(**field) for field in FIELDS]
    # One robots request, identical validated/pinned TLS transport, no redirect,
    # proxy fallback, cookie handling, JavaScript, retries, or resource loading.
    c = PinnedHTTPS('books.toscrape.com', public_addresses('books.toscrape.com')[0])
    try:
        c.request('GET', '/robots.txt', headers={'User-Agent': 'WebSheet-Agent/0.3.1 (static HTML extraction)', 'Accept-Encoding': 'identity'})
        r = c.getresponse()
        if r.status == 200:
            if r.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise RuntimeError('robots response compressed: stop for review')
            data = r.read(65537)
            if len(data) > 65536:
                raise RuntimeError('robots response too large: stop for review')
            rules = RobotFileParser()
            rules.parse(data.decode('utf-8', errors='strict').splitlines())
            if any(not rules.can_fetch('WebSheet-Agent', url) for url in urls):
                raise RuntimeError('robots disallows selected URL: stop')
            delay = rules.crawl_delay('WebSheet-Agent') or 2
        elif r.status == 404:
            delay = 2  # No published file; separate explicit sandbox invitation.
        else:
            raise RuntimeError('robots status %s: stop for review' % r.status)
    finally:
        c.close()
    result = []
    for url, (_, expected) in zip(urls, CASES):
        time.sleep(max(2, delay))
        actual = extract(fetch(url), fields)
        if actual != expected:
            raise AssertionError(json.dumps({'url': url, 'expected': expected, 'actual': actual, 'reason': 'fixture drift or extraction regression; review manually, never auto-rebaseline'}, ensure_ascii=False))
        result.append({'url': url, 'data': actual})
    print(json.dumps({'classification': 'external network fixtures, not customer adoption', 'passed': len(result), 'max_external_requests': 4, 'rows': result}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
