import os
import unittest
from websheet.core import Column, extract

@unittest.skipUnless(os.environ.get('WEBSHEET_BROWSER_TEST') == '1', 'Real browser QA opt-in; not simulated')
class BrowserTests(unittest.TestCase):
    def test_real_rendered_javascript(self):
        from websheet.browser import renderer
        with renderer() as render:
            for n in range(1, 31):
                row = extract(render(f'demo://catalog/{n}'), [Column(name='rendered', selector='#rendered')])
                self.assertEqual(row['rendered'], '浏览器已执行 JavaScript')
