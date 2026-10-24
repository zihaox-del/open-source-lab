"""Offline HTTP-to-extraction regressions: synthetic bytes, never a live socket."""
import codecs
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from websheet.app import create_app
from websheet.core import (Column, ExtractionError, MAX_BYTES, candidate_report,
                           candidates, discover_links, extract, fetch, link_report)


class EncodingTests(unittest.TestCase):
    def fetched(self, data, content_type='text/html'):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda key, default='': {'Content-Type': content_type, 'Content-Encoding': 'identity'}.get(key, default)
        response.read.return_value = data
        with patch('websheet.core.public_addresses', return_value=['93.184.216.34']), patch('websheet.core.PinnedHTTPS', return_value=connection):
            try:
                return fetch('https://example.org/item')
            finally:
                connection.close.assert_called_once()
                response.read.assert_called_once_with(MAX_BYTES + 1)

    def value(self, data, content_type='text/html'):
        return extract(self.fetched(data, content_type), [Column(name='name', selector='h1')])['name']

    def test_http_charset_chinese_utf8_gb18030_and_aliases(self):
        for encoding in ['utf-8', 'GB18030', 'gbk']:
            with self.subTest(encoding=encoding):
                self.assertEqual(self.value('<h1>中文商品</h1>'.encode(encoding), f'text/html; charset="{encoding}"'), '中文商品')
        self.assertEqual(self.value('<h1>Café €</h1>'.encode('cp1252'), 'text/html; CHARSET=windows-1252'), 'Café €')

    def test_http_charset_precedes_conflicting_meta(self):
        page = '<meta charset="utf-8"><h1>中文商品</h1>'.encode('gb18030')
        self.assertEqual(self.value(page, 'text/html; charset=gb18030'), '中文商品')

    def test_no_header_bom_meta_and_utf8_fallback(self):
        for data in [codecs.BOM_UTF8 + '<h1>中文</h1>'.encode(), '<h1>中文</h1>'.encode('utf-16'),
                     '<meta charset="gb18030"><h1>中文</h1>'.encode('gb18030'),
                     '<meta http-equiv="Content-Type" content="text/html; charset=gb18030"><h1>中文</h1>'.encode('gb18030'),
                     '<h1>中文</h1>'.encode()]:
            with self.subTest(data=data):
                self.assertEqual(self.value(data), '中文')
                self.assertEqual(extract(data, [Column(name='name', selector='h1')])['name'], '中文')

    def test_bom_precedes_meta_and_xhtml_xml_declaration(self):
        self.assertEqual(self.value(codecs.BOM_UTF8 + '<meta charset="gbk"><h1>中文</h1>'.encode()), '中文')
        self.assertEqual(self.value('<?xml version="1.0" encoding="UTF-8"?><html><h1>中文</h1></html>'.encode(), 'application/xhtml+xml; charset=UTF-8'), '中文')

    def test_malformed_meta_is_handled_without_server_error(self):
        self.assertEqual(self.value(b'<meta http-equiv><h1>Hello</h1>'), 'Hello')
        self.assertEqual(self.value(b'<meta http-equiv=content-type content><h1>Hello</h1>'), 'Hello')
        with self.assertRaisesRegex(ExtractionError, '字符编码'):
            self.value(b'<meta charset="utf-8\x00"><h1>Hello</h1>')

    def test_invalid_unsupported_or_mismatched_encoding_fails_not_replaces(self):
        for charset in ['', 'unknown-charset', 'base64_codec', 'unicode_escape', 'utf-7']:
            with self.subTest(charset=charset), self.assertRaisesRegex(ExtractionError, '字符编码'):
                self.value(b'<h1>safe</h1>', f'text/html; charset="{charset}"')
        for data, content_type in [(b'<h1>\xff</h1>', 'text/html; charset=utf-8'), (b'<h1>\xff</h1>', 'text/html'),
                                   (b'<meta charset="not-a-codec"><h1>safe</h1>', 'text/html')]:
            with self.subTest(data=data), self.assertRaisesRegex(ExtractionError, '编码'):
                self.value(data, content_type)


class CandidateReliabilityTests(unittest.TestCase):
    def test_complete_heading_nested_inline_text_and_inline_hidden_ancestors(self):
        page = '<html><body><h1>Product <span><em>Alpha</em></span></h1><span style="DISPLAY: none !important">Old</span><div style="visibility:hidden"><p>Secret</p></div><p>New</p></body></html>'
        result = candidates(page)
        self.assertIn('Product Alpha', [c['value'] for c in result])
        self.assertNotIn('Old', [c['value'] for c in result])
        self.assertNotIn('Secret', [c['value'] for c in result])
        for c in result:
            self.assertEqual(extract(page, [Column(name='value', selector=c['selector'])])['value'], c['value'])

    def test_content_not_starved_by_navigation_and_truncation_disclosed(self):
        page = '<html><body><nav>' + ''.join(f'<a href="/{i}">Menu {i}</a>' for i in range(150)) + '</nav><h1>Actual product</h1></body></html>'
        report = candidate_report(page)
        self.assertEqual(report['candidates'][0]['value'], 'Actual product')
        self.assertEqual(len(report['candidates']), 100)
        self.assertTrue(report['truncated'])
        self.assertFalse(report['scan_limited'])
        self.assertFalse(candidate_report('<h1>Title</h1>')['truncated'])

    def test_scan_limit_is_explicit(self):
        report = candidate_report('<html><body>' + '<hr>' * 5000 + '<h1>Too late</h1></body></html>')
        self.assertTrue(report['scan_limited'])
        self.assertTrue(report['truncated'])

    def test_positional_selector_can_still_return_wrong_value(self):
        # Deliberate counterexample: uniqueness is not semantic validation.
        sample = '<html><body><div><span>99</span></div><div><span>In stock</span></div></body></html>'
        selector = next(c['selector'] for c in candidates(sample) if c['tag'] == 'span' and c['value'] == '99')
        shifted = '<html><body><div><span>Sale ends Friday</span></div><div><span>99</span></div><div><span>In stock</span></div></body></html>'
        self.assertEqual(extract(shifted, [Column(name='price', selector=selector)])['price'], 'Sale ends Friday')

    def test_same_origin_base_relative_fragment_and_first_base(self):
        page = '<base href="/catalog/#part"><base href="https://evil.example/"><a href="item.html#part">Item</a><a href="item.html#again">Duplicate</a><a href="https://other.example/no">No</a>'
        self.assertEqual(discover_links(page, 'https://example.org/list'), [{'url':'https://example.org/catalog/item.html', 'label':'Item'}])

    def test_cross_origin_or_unsafe_base_errors_not_fabricated_links(self):
        for base in ['https://evil.example/', 'http://example.org/', 'https://user:pass@example.org/', 'https://[broken']:
            with self.subTest(base=base), self.assertRaises(ExtractionError):
                discover_links(f'<base href="{base}"><a href="/one">One</a>', 'https://example.org/list')

    def test_link_truncation_and_exact_limit(self):
        for count in [99, 100, 101]:
            report = link_report(''.join(f'<a href="/{i}">{i}</a>' for i in range(count)), 'https://example.org/list')
            self.assertEqual(report['truncated'], count > 100)
            self.assertEqual(len(report['links']), min(count, 100))

    def test_api_retains_lists_and_adds_limit_metadata(self):
        with tempfile.TemporaryDirectory() as tmp, TestClient(create_app(Path(tmp)/'test.sqlite3'), base_url='http://127.0.0.1') as client:
            for endpoint, key, page in [('inspect', 'candidates', ''.join(f'<p>{i}</p>' for i in range(101))),
                                        ('discover', 'links', ''.join(f'<a href="/{i}">{i}</a>' for i in range(101)))]:
                with patch('websheet.app.fetch', return_value=page):
                    response = client.post('/api/'+endpoint, json={'url':'https://example.org/list'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(response.json()[key]), 100)
                self.assertTrue(response.json()['truncated'])
                self.assertEqual(response.json()['limit'], 100)
