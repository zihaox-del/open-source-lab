"""Optional real browser renderer restricted to bundled, synthetic demo pages."""
import os
from contextlib import contextmanager
from .core import ExtractionError, fetch, origin

@contextmanager
def renderer():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ExtractionError('浏览器演示需要安装 requirements-browser.txt 与 Chromium') from None
    with sync_playwright() as runtime:
        browser = None
        try:
            options = {'headless': True}
            if os.environ.get('WEBSHEET_CHROMIUM_PATH'):
                options['executable_path'] = os.environ['WEBSHEET_CHROMIUM_PATH']
            browser = runtime.chromium.launch(**options)
            context = browser.new_context(service_workers='block', accept_downloads=False)
            context.route('**/*', lambda route: route.abort())
            context.set_offline(True)
            page = context.new_page()
            def render(url):
                if origin(url) != 'demo://catalog':
                    raise ExtractionError('浏览器演示仅支持内置 demo://catalog 页面；不访问外部网页')
                content = fetch(url)
                # This exact script is owned demo content, never untrusted HTML or model output.
                content = content.replace('</body>', '<p id="rendered"></p><script>'
                    'document.getElementById("rendered").textContent="浏览器已执行 JavaScript";'
                    '</script></body>')
                page.set_content(content, wait_until='domcontentloaded', timeout=5000)
                page.wait_for_function('document.getElementById("rendered").textContent.length > 0', timeout=5000)
                return page.content()
            yield render
        except ExtractionError:
            raise
        except Exception:
            raise ExtractionError('浏览器演示启动或执行失败；请安装 Chromium 或改用静态 HTML 模式。') from None
        finally:
            if browser:
                browser.close()
