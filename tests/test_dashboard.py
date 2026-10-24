"""Opt-in, real Chromium QA of the locally served dashboard.

No remote websites, credentials, API responses, or browser results are simulated.
The server uses the genuine synthetic catalog with a small delay so pause/resume
can be exercised deterministically, even on fast CI machines.
"""
import csv
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen


@unittest.skipUnless(os.environ.get('WEBSHEET_BROWSER_TEST') == '1',
                     'Real dashboard browser QA opt-in; not simulated')
class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.temp = tempfile.TemporaryDirectory(prefix='websheet-dashboard-')
        cls.addClassCleanup(cls.temp.cleanup)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        cls.base = f'http://127.0.0.1:{port}'
        cls.log = open(Path(cls.temp.name) / 'server.log', 'w+')
        cls.addClassCleanup(cls.log.close)
        # Install this guard BEFORE importing app/store so default fetch arguments
        # also use real, delayed synthetic extraction and cannot access the web.
        script = '''
import time
import websheet.core as core
original_fetch = core.fetch
def synthetic_fetch(url):
    if core.origin(url) != 'demo://catalog':
        raise core.ExtractionError('Dashboard QA permits synthetic catalog only')
    time.sleep(0.06)
    return original_fetch(url)
core.fetch = synthetic_fetch
import uvicorn
uvicorn.run('websheet.app:create_app', factory=True, host='127.0.0.1',
            port=PORT, access_log=False)
'''.replace('PORT', str(port))
        env = {key: value for key, value in os.environ.items()
               if not any(word in key.upper() for word in ('API_KEY', 'SECRET', 'TOKEN'))}
        env['WEBSHEET_DB'] = str(Path(cls.temp.name) / 'dashboard.sqlite3')
        cls.server = subprocess.Popen([sys.executable, '-c', script],
                                      cwd=Path(__file__).resolve().parents[1],
                                      env=env, stdout=cls.log, stderr=cls.log)
        cls.addClassCleanup(cls.stop_server)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError('Dashboard server exited: ' + cls.log.read())
            try:
                with urlopen(cls.base + '/api/demo', timeout=1) as response:
                    if response.status == 200:
                        break
            except OSError:
                time.sleep(0.05)
        else:
            raise RuntimeError('Dashboard server did not become ready')
        cls.playwright = sync_playwright().start()
        cls.addClassCleanup(cls.playwright.stop)
        launch = {'headless': True}
        executable = os.environ.get('WEBSHEET_CHROMIUM_EXECUTABLE')
        if executable:
            launch['executable_path'] = executable
        elif not Path(cls.playwright.chromium.executable_path).exists():
            system_chromium = shutil.which('chromium') or shutil.which('chromium-browser')
            if system_chromium:
                launch['executable_path'] = system_chromium
        # A missing or broken Chromium MUST fail, not skip or fake browser success.
        cls.browser = cls.playwright.chromium.launch(**launch)
        cls.addClassCleanup(cls.browser.close)

    @classmethod
    def stop_server(cls):
        cls.server.terminate()
        try:
            cls.server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.wait(timeout=5)

    def setUp(self):
        from playwright.sync_api import expect
        self.expect = expect
        self.context = self.browser.new_context(accept_downloads=True,
                                               viewport={'width': 1440, 'height': 1100})
        self.addCleanup(self.context.close)
        self.external_requests = []
        self.page_errors = []
        def local_only(route):
            if route.request.url.startswith(self.base + '/'):
                route.continue_()
            else:
                self.external_requests.append(route.request.url)
                route.abort()
        self.context.route('**/*', local_only)
        self.page = self.context.new_page()
        self.page.on('pageerror', lambda error: self.page_errors.append(str(error)))
        self.page.goto(self.base)

    def tearDown(self):
        self.assertEqual(self.external_requests, [], 'Dashboard attempted non-local requests')
        self.assertEqual(self.page_errors, [], 'Dashboard emitted JavaScript exceptions')

    def load_demo(self):
        self.page.locator('#demo').click()
        self.expect(self.page.locator('#urls')).to_have_value(re.compile('demo://catalog/1'))
        self.expect(self.page.locator('#demo')).to_be_enabled()

    def preview_and_review(self):
        self.page.locator('#preview').click()
        self.expect(self.page.locator('#preview-result')).to_be_visible()
        self.expect(self.page.locator('#preview-grid')).to_contain_text('合成示例商品 01')
        self.expect(self.page.locator('#preview-grid')).to_contain_text('13.00')
        self.page.locator('#reviewed').check()
        self.expect(self.page.locator('#run')).to_be_enabled()

    def wait_complete(self):
        self.expect(self.page.locator('#job-status')).to_contain_text('采集完成', timeout=30000)
        self.expect(self.page.locator('#completed')).to_have_text('30')
        self.expect(self.page.locator('#failed')).to_have_text('0')
        self.expect(self.page.locator('#results tbody tr')).to_have_count(30)

    def assert_downloads(self):
        from openpyxl import load_workbook
        for format in ('csv', 'xlsx'):
            with self.page.expect_download() as event:
                self.page.locator('#' + format).click()
            download = event.value
            self.assertIsNone(download.failure())
            self.assertTrue(download.suggested_filename.endswith('.' + format))
            path = Path(self.temp.name) / ('verified.' + format)
            download.save_as(path)
            if format == 'csv':
                with path.open(encoding='utf-8-sig', newline='') as file:
                    matrix = list(csv.reader(file))
            else:
                book = load_workbook(path, read_only=True, data_only=True)
                try:
                    matrix = list(book.active.values)
                finally:
                    book.close()
            self.assertEqual(len(matrix), 31)
            headers = list(matrix[0])
            rows = [dict(zip(headers, row)) for row in matrix[1:]]
            self.assertEqual(len({row['source_id'] for row in rows}), 30)
            self.assertEqual([row['source_url'] for row in rows],
                             [f'demo://catalog/{n}' for n in range(1, 31)])
            self.assertTrue(all(row['status'] == 'success' for row in rows))
            self.assertEqual(rows[0]['名称'], '合成示例商品 01')
            self.assertEqual(rows[-1]['名称'], '合成示例商品 30')
            self.assertEqual(str(rows[0]['价格']), '13.00')
            self.assertEqual(str(rows[-1]['价格']), '390.00')

    def test_no_css_selection_background_run_refresh_and_downloads(self):
        self.load_demo()
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#candidate-panel')).to_be_visible()
        for value, name in [('合成示例商品 01', '名称'), ('13.00', '价格')]:
            self.page.get_by_label('字段名称：' + value, exact=True).fill(name)
            self.page.locator('#candidates').get_by_role(
                'button', name='选择 ' + value, exact=True).click()
        self.page.locator('#use-fields').click()
        self.expect(self.page.locator('#candidate-panel')).not_to_be_visible()
        self.preview_and_review()
        created = []
        self.page.on('request', lambda request: created.append(request.url)
                     if request.method == 'POST' and request.url == self.base + '/api/jobs' else None)
        # Two immediate real DOM activations exercise the UI's duplicate-submit
        # guard without replacing its event handler or any network response.
        self.page.locator('#run').evaluate('(button) => { button.click(); button.click(); }')
        self.expect(self.page.locator('#job-status')).to_contain_text('正在采集')
        self.page.reload()
        self.wait_complete()
        self.assertEqual(len(created), 1, 'Repeated start created duplicate jobs')
        self.expect(self.page.locator('#run')).to_be_disabled()
        history_id = self.page.locator('#history').input_value()
        self.assertTrue(history_id)
        self.expect(self.page.locator('#history option[value="' + history_id + '"]')).to_have_count(1)
        self.page.reload()
        self.wait_complete()
        self.expect(self.page.locator('#history')).to_have_value(history_id)
        self.page.locator('#history').select_option(history_id)
        self.expect(self.page.locator('#job-subtitle')).to_contain_text(history_id)
        self.assert_downloads()
        artifacts = Path(__file__).resolve().parents[1] / 'test-artifacts'
        artifacts.mkdir(exist_ok=True)
        # Completion text updates before the 0.3-second progress transition ends.
        # Capture settled evidence, not a misleading partly filled completion bar.
        self.page.wait_for_function('''() => {
            const bar = document.getElementById('bar');
            return bar.style.width === '100%' &&
                Math.abs(bar.getBoundingClientRect().width -
                         bar.parentElement.getBoundingClientRect().width) < 1;
        }''')
        self.page.screenshot(path=str(artifacts / 'dashboard.png'), full_page=True,
                             animations='disabled')

    def test_draft_cancel_pause_resume_and_history(self):
        self.load_demo()
        original_fields = self.page.locator('#fields input').evaluate_all(
            '(inputs) => inputs.map(input => input.value)')
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#candidate-panel')).to_be_visible()
        self.page.get_by_label('字段名称：合成示例商品 01', exact=True).fill('不应保存的草稿')
        self.page.locator('#candidates').get_by_role(
            'button', name='选择 合成示例商品 01', exact=True).click()
        self.page.locator('#cancel-fields').click()
        self.expect(self.page.locator('#candidate-panel')).not_to_be_visible()
        self.assertEqual(self.page.locator('#fields input').evaluate_all(
            '(inputs) => inputs.map(input => input.value)'), original_fields)
        self.preview_and_review()
        self.page.locator('#run').click()
        self.expect(self.page.locator('#pause')).to_be_enabled()
        self.page.locator('#pause').click()
        self.expect(self.page.locator('#job-status')).to_have_text(re.compile('已暂停'), timeout=15000)
        completed = int(self.page.locator('#completed').inner_text())
        self.assertLess(completed, 30, 'Pause did not preserve pending work')
        history_id = self.page.locator('#history').input_value()
        self.page.reload()
        self.expect(self.page.locator('#job-status')).to_have_text(re.compile('已暂停'))
        self.expect(self.page.locator('#completed')).to_have_text(str(completed))
        self.expect(self.page.locator('#history')).to_have_value(history_id)
        self.page.locator('#resume').click()
        self.wait_complete()
        self.assert_downloads()


    def test_switch_history_during_run_and_browser_back_forward(self):
        self.load_demo()
        self.page.locator('#urls').fill('demo://catalog/1')
        self.preview_and_review()
        self.page.locator('#run').click()
        self.expect(self.page.locator('#job-status')).to_contain_text('采集完成', timeout=15000)
        self.expect(self.page.locator('#completed')).to_have_text('1')
        first_id = self.page.locator('#history').input_value()
        self.load_demo()
        self.preview_and_review()
        self.page.locator('#run').click()
        self.expect(self.page.locator('#job-status')).to_contain_text('正在采集')
        self.expect(self.page.locator('#history')).to_be_enabled()
        second_id = self.page.locator('#history').input_value()
        self.assertNotEqual(first_id, second_id)
        self.page.locator('#history').select_option(first_id)
        self.expect(self.page.locator('#job-subtitle')).to_contain_text(first_id)
        self.expect(self.page.locator('#total')).to_have_text('1')
        self.page.locator('#history').select_option(second_id)
        self.expect(self.page.locator('#job-subtitle')).to_contain_text(second_id)
        self.expect(self.page.locator('#total')).to_have_text('30')
        # Leave the actual dashboard, then exercise native history navigation.
        # The background worker and SQLite results must outlive page navigation.
        self.page.goto(self.base + '/api/demo')
        self.page.go_back()
        self.expect(self.page.locator('#history')).to_have_value(second_id)
        self.page.go_forward()
        self.assertEqual(self.page.url, self.base + '/api/demo')
        self.page.go_back()
        self.expect(self.page.locator('#history')).to_have_value(second_id)
        self.wait_complete()
        self.expect(self.page.locator('#urls')).to_have_value(
            '\n'.join(f'demo://catalog/{n}' for n in range(1, 31)))
