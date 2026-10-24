import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from websheet.app import create_app
from websheet.core import Column, ExtractionError, candidates, discover_links, extract, origin


class GuidedTests(unittest.TestCase):
    def test_candidates_are_unique_and_repeated_siblings_use_bounded_path(self):
        content = '<html><body><h1>Title</h1><section><p>One</p><p>Two</p></section><span class="price">13.00</span></body></html>'
        choices = candidates(content)
        self.assertEqual([c['value'] for c in choices], ['Title', 'One', 'Two', '13.00'])
        for candidate in choices:
            self.assertEqual(extract(content, [Column(name='x', selector=candidate['selector'])])['x'], candidate['value'])
        self.assertIn(':nth-of-type(2)', choices[2]['selector'])

    def test_path_grammar_is_not_arbitrary_css_or_xpath(self):
        for selector in ['html > body > p:nth-of-type(0)', 'html > body > p:nth-of-type(10000)', 'html > body > p[1]', 'html > body > script | //a', 'html > *', 'html > body:hover', 'html > ' + ' > '.join(['div'] * 16)]:
            with self.assertRaises(ValueError):
                Column(name='x', selector=selector)

    def test_text_only_candidates_and_bounds(self):
        content = '<html><head><title>Private title</title></head><body><script>evil()</script><div hidden><p>Hidden</p></div><p>&lt;img src=x onerror=evil()&gt;</p>' + ''.join(f'<span>{i}</span>' for i in range(150)) + '</body></html>'
        choices = candidates(content)
        self.assertEqual(len(choices), 100)
        self.assertEqual(choices[0]['value'], '<img src=x onerror=evil()>')
        self.assertTrue(all(set(c) == {'value','selector','attribute','tag'} for c in choices))
        self.assertFalse(any('evil()' == c['value'] or 'Hidden' == c['value'] for c in choices))

    def test_discovery_same_origin_deduplicated_capped(self):
        content = '''<a href="/one">One</a><a href="/one#part">Duplicate</a><a href="https://other.example/two">Other</a><a href="javascript:alert(1)">JS</a><a href="https://user:pass@example.org/x">Credentials</a><a href="https://[broken">Broken</a><a href="#part">Fragment</a>'''
        links = discover_links(content, 'https://example.org/list')
        self.assertEqual(links, [{'url':'https://example.org/one', 'label':'One'}])
        many = ''.join(f'<a href="/{n}">{n}</a>' for n in range(150))
        self.assertEqual(len(discover_links(many, 'https://example.org/list')), 100)

    def test_invalid_url_actionable(self):
        with self.assertRaises(ExtractionError):
            origin('https://[broken')

    def test_guided_api_end_to_end_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(Path(tmp)/'test.sqlite3'), base_url='http://127.0.0.1') as client:
                result = client.post('/api/inspect', json={'url':'demo://catalog/1'})
                self.assertEqual(result.status_code, 200)
                choice = result.json()['candidates'][0]
                field = {'name':'名称','selector':choice['selector']}
                payload = {'urls':['demo://catalog/1','demo://catalog/2'], 'fields':[field], 'reviewed':True, 'request_id':'stable-key'}
                payload['review_token'] = client.post('/api/review', json=payload).json()['review_token']
                job = client.post('/api/jobs', json=payload).json()
                again = client.post('/api/jobs', json=payload).json()
                self.assertEqual(job['id'], again['id'])
                self.assertEqual(len(client.get('/api/jobs').json()['jobs']), 1)
                self.assertEqual(client.post(f'/api/jobs/{job["id"]}/run').status_code, 200)
                deadline = time.monotonic()+5
                while time.monotonic() < deadline:
                    done = client.get(f'/api/jobs/{job["id"]}').json()
                    if done['status'] == 'complete': break
                    time.sleep(.01)
                self.assertEqual(done['completed'], 2)
                self.assertEqual(client.post('/api/inspect', json={'url':'https://[broken'}).status_code, 400)
                with patch('websheet.app.fetch', return_value='<a href="/detail">Detail</a>'):
                    links = client.post('/api/discover', json={'url':'https://example.org/list'}).json()['links']
                self.assertEqual(links[0]['url'], 'https://example.org/detail')
