"""Durability/concurrency tests using only the bundled synthetic catalog."""
import sqlite3
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from websheet.core import Column, ExtractionError, fetch
from websheet.store import Store

FIELDS = [Column(name='名称', selector='h1')]
URLS = ['demo://catalog/1', 'demo://catalog/2', 'demo://catalog/3']


class DurableJobTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'jobs.sqlite3'
        self.store = Store(self.path)
        self.release = threading.Event()

    def tearDown(self):
        self.release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            lock = self.store._lock()
            if lock is not None:
                lock.close()
                break
            time.sleep(.01)
        self.tmp.cleanup()

    def create(self, **kwargs):
        return self.store.create(URLS, FIELDS, True, **kwargs)

    def wait_for(self, job_id, status):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            job = self.store.get(job_id)
            if job['status'] == status:
                return job
            time.sleep(.01)
        self.fail(f'Job did not reach {status}: {job}')

    def blocking_fetcher(self):
        entered = threading.Event()
        calls = []
        def read(url):
            calls.append(url)
            entered.set()
            if not self.release.wait(5):
                raise RuntimeError('test release timed out')
            return fetch(url)
        return read, entered, calls

    def test_async_start_and_repeated_start_have_one_worker(self):
        job = self.create()
        read, entered, calls = self.blocking_fetcher()
        started = self.store.start(job['id'], read)
        self.assertEqual(started['status'], 'running')
        self.assertTrue(entered.wait(2))
        another_store = Store(self.path)
        self.assertEqual(another_store.start(job['id'], read)['status'], 'running')
        self.assertEqual(calls, URLS[:1])
        self.release.set()
        done = self.wait_for(job['id'], 'complete')
        self.assertEqual(done['completed'], 3)
        self.assertEqual(calls, URLS)
        self.assertEqual(self.store.start(job['id'], read), done)

    def test_concurrent_starts_share_the_same_worker(self):
        job = self.create()
        read, entered, calls = self.blocking_fetcher()
        with ThreadPoolExecutor(max_workers=8) as pool:
            started = list(pool.map(lambda _: self.store.start(job['id'], read), range(16)))
        self.assertTrue(entered.wait(2))
        self.assertTrue(all(item['status'] == 'running' for item in started))
        self.assertEqual(calls, URLS[:1])
        self.release.set()
        self.assertEqual(self.wait_for(job['id'], 'complete')['completed'], 3)
        self.assertEqual(calls, URLS)

    def test_other_job_cannot_start_until_worker_releases_lock(self):
        first, second = self.create(), self.create()
        read, entered, _ = self.blocking_fetcher()
        self.store.start(first['id'], read)
        self.assertTrue(entered.wait(2))
        with self.assertRaises(ExtractionError):
            Store(self.path).start(second['id'])
        self.assertEqual(self.store.get(second['id'])['status'], 'ready')

    def test_pause_finishes_current_row_and_resume_skips_committed_rows(self):
        job = self.create()
        read, entered, calls = self.blocking_fetcher()
        self.store.start(job['id'], read)
        self.assertTrue(entered.wait(2))
        self.assertEqual(self.store.pause(job['id'])['status'], 'pausing')
        self.assertEqual(self.store.start(job['id'], read)['status'], 'pausing')
        self.release.set()
        paused = self.wait_for(job['id'], 'paused')
        self.assertEqual(paused['completed'], 1)
        self.assertEqual(calls, URLS[:1])
        restored = Store(self.path)
        self.assertEqual(restored.get(job['id'])['status'], 'paused')
        resumed_calls = []
        def resume(url):
            resumed_calls.append(url)
            return fetch(url)
        self.assertEqual(restored.run(job['id'], resume)['completed'], 3)
        self.assertEqual(resumed_calls, URLS[1:])

    def test_ready_can_be_paused_and_completed_job_pause_is_noop(self):
        job = self.create()
        self.assertEqual(self.store.pause(job['id'])['status'], 'paused')
        done = self.store.run(job['id'])
        self.assertEqual(self.store.pause(job['id']), done)

    def test_crash_recovery_preserves_committed_rows(self):
        job = self.create()
        def crash(url):
            if url == URLS[1]:
                raise KeyboardInterrupt()
            return fetch(url)
        with self.assertRaises(KeyboardInterrupt):
            self.store.run(job['id'], crash)
        interrupted = Store(self.path).get(job['id'])
        self.assertEqual(interrupted['status'], 'interrupted')
        self.assertEqual(interrupted['completed'], 1)
        self.assertTrue(interrupted['error'])
        done = self.store.run(job['id'])
        self.assertEqual(done['completed'], 3)
        self.assertIsNone(done['error'])

    def test_recover_unclean_exit_and_pending_pause(self):
        a, b = self.create(), self.create()
        with self.store.connect() as db:
            db.execute("UPDATE jobs SET status='running' WHERE id=?", (a['id'],))
            db.execute("UPDATE jobs SET status='pausing' WHERE id=?", (b['id'],))
        restored = Store(self.path)
        self.assertEqual(restored.get(a['id'])['status'], 'interrupted')
        self.assertEqual(restored.get(b['id'])['status'], 'paused')

    def test_renderer_context_is_owned_and_closed_by_worker(self):
        job = self.create(engine='browser-demo')
        threads, events = [], []
        @contextmanager
        def renderer():
            threads.append(threading.get_ident())
            events.append('open')
            def read(url):
                threads.append(threading.get_ident())
                return fetch(url)
            try:
                yield read
            finally:
                threads.append(threading.get_ident())
                events.append('close')
        with patch('websheet.browser.renderer', renderer):
            self.store.start(job['id'])
            self.wait_for(job['id'], 'complete')
        self.assertEqual(events, ['open', 'close'])
        self.assertEqual(len(set(threads)), 1)
        self.assertNotEqual(threads[0], threading.get_ident())

    def test_renderer_start_failure_is_persisted_and_resumable(self):
        job = self.create(engine='browser-demo')
        @contextmanager
        def renderer():
            raise ExtractionError('Synthetic browser unavailable')
            yield
        with patch('websheet.browser.renderer', renderer):
            self.store.start(job['id'])
            interrupted = self.wait_for(job['id'], 'interrupted')
        self.assertEqual(interrupted['error'], 'Synthetic browser unavailable')
        self.assertEqual(interrupted['completed'], 0)
        self.assertEqual(interrupted['failed'], 0)
        self.assertEqual(self.store.run(job['id'], fetch)['completed'], 3)

    def test_idempotency_matches_exact_payload_and_persists(self):
        job = self.create(request_id='review-1')
        self.assertEqual(Store(self.path).create(URLS, FIELDS, True, request_id='review-1'), job)
        for urls, fields, engine in [(list(reversed(URLS)), FIELDS, 'static'),
                                     (URLS + [URLS[0]], FIELDS, 'static'),
                                     (URLS, [Column(name='other', selector='h1')], 'static'),
                                     (URLS, FIELDS, 'browser-demo')]:
            with self.assertRaises(ExtractionError):
                self.store.create(urls, fields, True, engine, request_id='review-1')
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_concurrent_duplicate_creates_are_atomic(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            jobs = list(pool.map(lambda _: self.create(request_id='same'), range(16)))
        self.assertEqual(len({job['id'] for job in jobs}), 1)
        self.assertEqual(len(self.store.list_jobs()), 1)

    def test_history_newest_first_and_legacy_schema_migration(self):
        first, second = self.create(), self.create()
        self.assertEqual([j['id'] for j in self.store.list_jobs()], [second['id'], first['id']])
        legacy = Path(self.tmp.name) / 'legacy.sqlite3'
        with sqlite3.connect(legacy) as db:
            db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, fields TEXT NOT NULL, status TEXT NOT NULL, engine TEXT NOT NULL DEFAULT 'static')")
            db.execute("INSERT INTO jobs VALUES('old','[]','running','static')")
        migrated = Store(legacy).get('old')
        self.assertEqual(migrated['status'], 'interrupted')
        self.assertTrue(migrated['created_at'])

    def test_unknown_ids_and_bad_request_ids(self):
        for operation in (self.store.get, self.store.start, self.store.pause, self.store.run):
            with self.assertRaises(KeyError):
                operation('missing')
        for request_id in ('', ' ', 'x' * 129, 42):
            with self.assertRaises(ExtractionError):
                self.create(request_id=request_id)
