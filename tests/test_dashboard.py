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
    if url == 'https://example.org/limits':
        return '<html><body><nav>' + ''.join(f'<a href="/{i}">Menu {i}</a>' for i in range(150)) + '</nav><h1>Product <span>Alpha</span></h1></body></html>'
    if core.origin(url) != 'demo://catalog':
        raise core.ExtractionError('Dashboard QA permits synthetic catalog only')
    time.sleep(0.06)
    if url == 'demo://catalog/99':
        return '<html><body><script>0</script></body></html>'
    if url == 'demo://catalog/97':
        return '<a href="demo://catalog/1">First</a><a href="demo://catalog/2">Second</a>'
    if url == 'demo://catalog/98':
        return '<html><body><h1>合成缺字段示例</h1></body></html>'
    return original_fetch(url)
core.fetch = synthetic_fetch
import websheet.app as app_module
original_extract = app_module.extract
def delayed_extract(content, fields):
    if any(field.name == '慢列' for field in fields):
        time.sleep(0.7)
    return original_extract(content, fields)
app_module.extract = delayed_extract
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

    def screenshot(self, name):
        artifacts = Path(__file__).resolve().parents[1] / 'test-artifacts'
        artifacts.mkdir(exist_ok=True)
        self.page.screenshot(path=str(artifacts / (name + '.png')), full_page=True)

    def load_demo(self):
        self.page.locator('#demo').click()
        self.expect(self.page.locator('#choose-stage')).to_be_visible()
        self.expect(self.page.locator('#demo')).to_be_enabled()

    def choose_fields(self):
        for value, name in [('合成示例商品 01', '名称'), ('13.00', '价格')]:
            self.page.get_by_label('字段名称：' + value, exact=True).fill(name)
            self.page.locator('#candidates').get_by_role(
                'button', name='选择 ' + value, exact=True).click()
        self.expect(self.page.locator('#preview-result')).to_be_visible()
        self.expect(self.page.locator('#preview-grid')).to_contain_text('合成示例商品 01')
        self.expect(self.page.locator('#preview-grid')).to_contain_text('13.00')
        self.expect(self.page.locator('#run')).to_be_enabled()

    def wait_complete(self, total=30):
        self.expect(self.page.locator('#job-status')).to_contain_text('整理完成', timeout=30000)
        self.expect(self.page.locator('#completed')).to_have_text(str(total))
        self.expect(self.page.locator('#failed')).to_have_text('0')
        self.expect(self.page.locator('#results tbody tr')).to_have_count(total)

    def assert_downloads(self):
        from openpyxl import load_workbook
        for format in ('csv', 'xlsx'):
            with self.page.expect_download() as event:
                self.page.locator('#' + format).click()
            download = event.value
            self.assertIsNone(download.failure())
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
            rows = [dict(zip(matrix[0], row)) for row in matrix[1:]]
            self.assertEqual(len({row['source_id'] for row in rows}), 30)
            self.assertEqual([row['source_url'] for row in rows],
                             [f'demo://catalog/{n}' for n in range(1, 31)])
            self.assertTrue(all(row['status'] == 'success' for row in rows))
            self.assertEqual(rows[0]['名称'], '合成示例商品 01')
            self.assertEqual(rows[-1]['名称'], '合成示例商品 30')
            self.assertEqual(str(rows[0]['价格']), '13.00')
            self.assertEqual(str(rows[-1]['价格']), '390.00')

    def test_first_use_automatic_preview_refresh_duplicate_start_and_download(self):
        self.expect(self.page.locator('#input-stage')).to_be_visible()
        self.expect(self.page.locator('#engine')).not_to_be_visible()
        self.expect(self.page.locator('#result-stage')).not_to_be_visible()
        self.screenshot('desktop-input')
        self.load_demo()
        self.expect(self.page.get_by_label('字段名称：13.00', exact=True)).to_have_value('列2')
        self.choose_fields()
        self.expect(self.page.locator('#scope')).to_contain_text('30 页 · 2 列')
        self.screenshot('desktop-choose')
        self.page.reload()
        self.expect(self.page.locator('#choose-stage')).to_be_visible()
        self.expect(self.page.get_by_label('字段名称：13.00', exact=True)).to_have_value('价格')
        self.expect(self.page.locator('#run')).to_be_enabled()
        created = []
        self.page.on('request', lambda request: created.append(request.url)
                     if request.method == 'POST' and request.url == self.base + '/api/jobs' else None)
        self.page.locator('#run').evaluate('(button) => { button.click(); button.click(); }')
        self.expect(self.page.locator('#result-stage')).to_be_visible()
        self.page.reload()
        self.wait_complete()
        self.assertEqual(len(created), 1)
        self.expect(self.page.locator('#choose-stage')).not_to_be_visible()
        self.assert_downloads()
        self.screenshot('desktop-complete')
        self.screenshot('dashboard')

    def test_cancel_pause_resume_and_history_navigation(self):
        self.load_demo()
        self.choose_fields()
        self.page.locator('#cancel-fields').click()
        self.expect(self.page.locator('#input-stage')).to_be_visible()
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#run')).to_be_disabled()
        self.choose_fields()
        self.page.locator('#run').click()
        self.expect(self.page.locator('#pause')).to_be_enabled()
        self.page.locator('#pause').click()
        self.expect(self.page.locator('#job-status')).to_contain_text('已暂停', timeout=15000)
        completed = int(self.page.locator('#completed').inner_text())
        self.assertLess(completed, 30)
        history_id = self.page.locator('#history').input_value()
        self.page.reload()
        self.expect(self.page.locator('#job-status')).to_contain_text('已暂停')
        self.expect(self.page.locator('#completed')).to_have_text(str(completed))
        self.page.locator('#resume').click()
        self.wait_complete()
        self.page.locator('#new-task').click()
        self.expect(self.page.locator('#input-stage')).to_be_visible()
        self.page.locator('#history-section summary').click()
        self.page.locator('#history').select_option(history_id)
        self.expect(self.page.locator('#result-stage')).to_be_visible()
        self.page.goto(self.base + '/api/demo')
        self.page.go_back()
        self.expect(self.page.locator('#result-stage')).to_be_visible()
        self.page.go_forward()
        self.page.go_back()
        self.wait_complete()
        self.assert_downloads()

    def test_narrow_single_url_and_failure_outcome(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.screenshot('mobile-input')
        self.page.locator('#urls').fill('demo://catalog/1')
        self.page.locator('#inspect').click()
        self.choose_fields()
        self.expect(self.page.locator('#scope')).to_contain_text('1 页 · 2 列')
        self.screenshot('mobile-choose')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), 390)
        self.page.locator('#run').click()
        self.wait_complete(1)
        self.screenshot('mobile-complete')
        self.page.locator('#new-task').click()
        self.page.locator('#urls').fill('demo://catalog/1\ndemo://catalog/98')
        self.page.locator('#inspect').click()
        self.choose_fields()
        self.page.locator('#run').click()
        self.expect(self.page.locator('#job-status')).to_contain_text('整理完成', timeout=15000)
        self.expect(self.page.locator('#completed')).to_have_text('1')
        self.expect(self.page.locator('#failed')).to_have_text('1')
        self.expect(self.page.locator('#failure-note')).to_be_visible()
        self.expect(self.page.locator('#results')).to_contain_text('匹配 0 个元素')
        self.expect(self.page.locator('#xlsx')).to_be_enabled()
        self.screenshot('mobile-partial-failure')

    def test_read_errors_empty_discovery_and_stale_preview(self):
        self.page.locator('#urls').fill('https://[broken')
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#message')).to_contain_text('网址格式')
        self.expect(self.page.locator('#urls')).to_have_value('https://[broken')
        self.page.locator('#urls').fill('demo://catalog/99')
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#message')).to_contain_text('没有找到可选的静态文字')
        self.expect(self.page.locator('#run')).to_be_disabled()
        self.page.locator('#cancel-fields').click()
        self.expect(self.page.locator('#urls')).to_have_value('demo://catalog/99')
        self.page.locator('#urls').fill('demo://catalog/97')
        self.page.locator('#discovery summary').click()
        self.page.locator('#discover').click()
        self.expect(self.page.locator('#links input')).to_have_count(2)
        self.page.locator('#links input').nth(0).check()
        self.page.locator('#links input').nth(1).check()
        self.page.locator('#use-links').click()
        self.expect(self.page.locator('#urls')).to_have_value('demo://catalog/1\ndemo://catalog/2')
        self.page.locator('#inspect').click()
        self.choose_fields()
        self.expect(self.page.locator('#preview-grid table thead th')).to_have_count(2)
        price_name = self.page.get_by_label('字段名称：13.00', exact=True)
        with self.page.expect_request(lambda request: request.url.endswith('/api/preview')):
            price_name.fill('慢列')
        price_name.fill('更新后的列')
        self.expect(self.page.locator('#run')).to_be_enabled()
        self.expect(self.page.locator('#preview-grid th')).to_have_text(['名称', '更新后的列'])
        self.page.wait_for_timeout(900)  # Let older, real delayed extraction finish.
        self.expect(self.page.locator('#preview-grid th')).to_have_text(['名称', '更新后的列'])
        with self.page.expect_request(lambda request: request.url.endswith('/api/preview')):
            price_name.fill('慢列')
        self.page.locator('#cancel-fields').click()
        self.page.wait_for_timeout(900)
        self.expect(self.page.locator('#input-stage')).to_be_visible()
        self.expect(self.page.locator('#run')).to_be_disabled()
        # Advanced demo-engine selection must not trap the ordinary input flow.
        self.page.locator('#inspect').click()
        self.page.locator('#advanced summary').first.click()
        self.page.locator('#engine').select_option('browser-demo')
        self.page.locator('#cancel-fields').click()
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#choose-stage')).to_be_visible()
        self.expect(self.page.locator('#engine')).to_have_value('static')

    def test_candidate_and_link_limits_are_actionable(self):
        self.page.locator('#urls').fill('https://example.org/limits')
        self.page.locator('#discovery summary').click()
        self.page.locator('#discover').click()
        self.expect(self.page.locator('#links input')).to_have_count(100)
        self.expect(self.page.locator('#message')).to_contain_text('超过 100 个')
        self.expect(self.page.locator('#message')).to_contain_text('直接粘贴')
        self.page.locator('#inspect').click()
        self.expect(self.page.locator('#candidate-limit')).to_be_visible()
        self.expect(self.page.locator('#candidate-limit')).to_contain_text('高级选项')
        self.expect(self.page.locator('#candidates button').first).to_have_text('选择 Product Alpha')
        self.page.locator('#candidates button').first.click()
        self.expect(self.page.locator('#preview-grid')).to_contain_text('Product Alpha')
        self.expect(self.page.locator('#run')).to_be_enabled()
        self.screenshot('desktop-candidate-limit')
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.screenshot('mobile-candidate-limit')
        self.page.locator('#cancel-fields').click()
        self.page.locator('#demo').click()
        self.expect(self.page.locator('#choose-stage')).to_be_visible()
        self.expect(self.page.locator('#candidate-limit')).to_be_hidden()
