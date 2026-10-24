"""Offline review/retry contracts: no network, no silent semantic claims."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from websheet.app import create_app
from websheet.core import Column, ExtractionError, export_rows, fetch


class ReviewRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.tmp.name) / 'test.sqlite3')
        self.store = self.app.state.store
        self.client = TestClient(self.app, base_url='http://127.0.0.1')
        self.fields = [Column(name='名称', selector='h1')]
        self.urls = [f'demo://catalog/{n}' for n in range(1, 7)]
        self.config = dict(urls=self.urls, fields=[f.model_dump() for f in self.fields])

    def tearDown(self):
        self.store.shutdown()
        self.client.close()
        self.tmp.cleanup()

    def review(self, config=None):
        response = self.client.post('/api/review', json=config or self.config)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def partial(self):
        parent = self.store.create(self.urls[:3], self.fields, True)
        def read(url):
            if url == self.urls[1]:
                raise ExtractionError('Synthetic failed page')
            return fetch(url)
        return self.store.run(parent['id'], read)

    def test_changed_retry_fixture_really_fails_generated_price_rule(self):
        from websheet.core import candidate_report, fetch, extract
        candidates = candidate_report(fetch('demo://catalog/1'))['candidates']
        price = next(c for c in candidates if c['value'] == '13.00')
        field = Column(name='价格', selector=price['selector'])
        changed = '<h1>合成变化页面</h1><p id="sku">REPAIRED-96</p>'
        with self.assertRaises(ExtractionError):
            extract(changed, [field])
        self.assertEqual(extract(changed, [Column(name='价格', selector='#sku')]), {'价格': 'REPAIRED-96'})

    def test_deterministic_deduplicated_first_middle_last_actual_values(self):
        with patch('websheet.app.fetch', wraps=fetch) as read:
            review = self.review({**self.config, 'urls': self.urls + self.urls[:1]})
        selected = [self.urls[0], self.urls[3], self.urls[5]]
        self.assertEqual([s['source_url'] for s in review['samples']], selected)
        self.assertEqual([c.args[0] for c in read.call_args_list], selected)
        self.assertTrue(review['all_ok'])
        self.assertTrue(review['review_token'])
        self.assertIn('04', review['samples'][1]['row']['名称'])
        for length in (1, 2, 3):
            self.assertEqual(len(self.review({**self.config, 'urls': self.urls[:length]})['samples']), length)

    def test_position_warning_exposes_successfully_matched_wrong_semantics(self):
        config = {**self.config, 'fields': [{'name': '价格', 'selector': 'html > body > p:nth-of-type(2)'}]}
        def read(url):
            if url == self.urls[3]:
                return '<html><body><p>Promotion</p><p>Title not price</p><p>13.00</p></body></html>'
            return '<html><body><p>Title</p><p>13.00</p></body></html>'
        with patch('websheet.app.fetch', side_effect=read):
            review = self.review(config)
        self.assertTrue(review['all_ok'])  # Uniqueness is not semantic validation.
        self.assertTrue(review['positional_warning'])
        self.assertEqual([s['row']['价格'] for s in review['samples']], ['13.00', 'Title not price', '13.00'])

    def test_per_source_errors_never_issue_token_and_config_change_invalidates(self):
        with patch('websheet.app.fetch', side_effect=lambda url: '<h2>Missing</h2>' if url == self.urls[3] else fetch(url)):
            review = self.review()
        self.assertFalse(review['all_ok'])
        self.assertIsNone(review['review_token'])
        self.assertTrue(review['samples'][1]['error'])
        self.assertTrue(review['samples'][0]['row'])
        self.assertEqual(self.client.post('/api/jobs', json={**self.config, 'reviewed': True}).status_code, 400)
        token = self.review()['review_token']
        for change in ({'urls': self.urls[:-1]}, {'fields': [{'name':'Other','selector':'h1'}]}, {'engine':'browser-demo'}):
            self.assertEqual(self.client.post('/api/jobs', json={**self.config, **change, 'reviewed':True, 'review_token':token}).status_code, 400)
        self.assertEqual(self.client.post('/api/jobs', json={**self.config, 'reviewed':False, 'review_token':token}).status_code, 400)

    def test_retry_only_failed_new_task_parent_snapshot_immutable(self):
        parent = self.partial()
        snapshot = export_rows(parent, 'csv')
        draft = self.client.get(f'/api/jobs/{parent["id"]}/retry-draft').json()
        self.assertEqual(draft['urls'], [self.urls[1]])
        self.assertEqual(draft['fields'], parent['fields'])
        draft['fields'] = [{'name':'修正名称', 'selector':'h1'}]
        token = self.review(draft)['review_token']
        body = dict(draft, reviewed=True, review_token=token, request_id='one-retry')
        first = self.client.post('/api/jobs', json=body).json()
        second = self.client.post('/api/jobs', json=body).json()
        self.assertEqual(first['id'], second['id'])
        self.assertNotEqual(first['id'], parent['id'])
        self.assertEqual(first['parent_job_id'], parent['id'])
        calls = []
        def read(url):
            calls.append(url)
            return fetch(url)
        done = self.store.run(first['id'], read)
        self.assertEqual(calls, [self.urls[1]])
        self.assertEqual(done['completed'], 1)
        original = self.store.get(parent['id'])
        self.assertEqual(original['rows'], parent['rows'])
        self.assertEqual(original['fields'], parent['fields'])
        self.assertEqual(export_rows(original, 'csv'), snapshot)
        self.assertEqual(original['child_job_ids'], [first['id']])
        self.assertNotEqual(export_rows(done, 'csv'), snapshot)

    def test_backend_rejects_forged_parent_success_pending_or_changed_scope(self):
        parent = self.partial()
        for urls in (self.urls[:1], self.urls[:3], [], [self.urls[1], self.urls[2]]):
            with self.assertRaises(ExtractionError):
                self.store.create(urls, self.fields, True, parent_job_id=parent['id'])
        with self.assertRaises(KeyError):
            self.store.create(self.urls[:1], self.fields, True, parent_job_id='missing')
        with self.assertRaises(ExtractionError):
            self.store.create([self.urls[1]], self.fields, True, engine='browser-demo', parent_job_id=parent['id'])
        for status in ('ready', 'running', 'pausing', 'paused', 'interrupted'):
            other = self.store.create(self.urls[:1], self.fields, True)
            with self.store.connect() as db:
                db.execute('UPDATE jobs SET status=? WHERE id=?', (status, other['id']))
            self.assertEqual(self.client.get(f'/api/jobs/{other["id"]}/retry-draft').status_code, 400)
        success = self.store.run(self.store.create(self.urls[:1], self.fields, True)['id'])
        self.assertEqual(self.client.get(f'/api/jobs/{success["id"]}/retry-draft').status_code, 400)

    def test_parent_identity_and_review_cannot_be_reused_for_another_parent(self):
        first, second = self.partial(), self.partial()
        draft = self.store.retry_draft(first['id'])
        token = self.review(draft)['review_token']
        wrong = dict(draft, parent_job_id=second['id'], reviewed=True, review_token=token)
        self.assertEqual(self.client.post('/api/jobs', json=wrong).status_code, 400)
        body = dict(draft, reviewed=True, review_token=token, request_id='retry-parent')
        self.assertEqual(self.client.post('/api/jobs', json=body).status_code, 200)
        wrong['request_id'] = 'retry-parent'
        self.assertEqual(self.client.post('/api/jobs', json=wrong).status_code, 400)

    def test_concurrent_retry_creation_idempotent(self):
        parent = self.partial()
        draft = self.store.retry_draft(parent['id'])
        token = self.review(draft)['review_token']
        def create(_):
            return self.store.create(draft['urls'], self.fields, True, request_id='concurrent-retry', parent_job_id=parent['id'], review_token=token, require_review=True)
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = list(pool.map(create, range(8)))
        self.assertEqual(len({j['id'] for j in jobs}), 1)
        self.assertEqual(self.store.get(parent['id'])['rows'], parent['rows'])

    def test_legacy_request_identity_remains_recoverable_without_recreating(self):
        job = self.store.create(self.urls, self.fields, True, request_id='legacy')
        legacy = dict(urls=self.urls, fields=[f.model_dump() for f in self.fields], reviewed=True, engine='static')
        with self.store.connect() as db:
            db.execute('UPDATE jobs SET request_payload=? WHERE id=?', (json.dumps(legacy), job['id']))
        recovered = self.client.post('/api/jobs', json=dict(self.config, reviewed=True, request_id='legacy'))
        self.assertEqual(recovered.status_code, 200, recovered.text)
        self.assertEqual(recovered.json()['id'], job['id'])
        self.assertEqual(len(self.store.list_jobs()), 1)
