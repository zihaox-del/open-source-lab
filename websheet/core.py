"""Bounded static-HTML extraction. No JavaScript, cookies or authenticated browser."""
import csv
import hashlib
import http.client
import io
import ipaddress
import json
import re
import socket
import ssl
from urllib.parse import urlsplit, urljoin, urldefrag

from lxml import html
from pydantic import BaseModel, Field, field_validator

MAX_BYTES = 1_000_000
SIMPLE_SELECTOR = re.compile(r'^(?:[a-zA-Z][\w-]*)?(?:[.#][a-zA-Z_][\w-]*)?$')

PATH_PART = re.compile(r'^[a-zA-Z][\w-]*(?::nth-of-type\(([1-9][0-9]{0,3})\))?$')

def supported_selector(value):
    if SIMPLE_SELECTOR.fullmatch(value):
        return True
    parts = value.split(' > ')
    return 2 <= len(parts) <= 16 and parts[0] == 'html' and all(PATH_PART.fullmatch(p) for p in parts)


def select(tree, selector):
    # Only our bounded grammar is translated, never caller-supplied XPath.
    if not supported_selector(selector):
        raise ExtractionError('不支持的字段定位规则，请重新选择样本值')
    if ' > ' in selector:
        parts = []
        for part in selector.split(' > '):
            tag = part.split(':')[0]
            match = PATH_PART.fullmatch(part)
            parts.append(tag + (f'[{int(match.group(1))}]' if match.group(1) else ''))
        return tree.getroottree().xpath('/' + '/'.join(parts))
    tag = re.split(r'[.#]', selector)[0] or '*'
    xpath = f'//{tag}'
    if '#' in selector:
        xpath += f'[@id="{selector.split("#")[1]}"]'
    elif '.' in selector:
        xpath += f'[contains(concat(" ", normalize-space(@class), " "), " {selector.split(".")[1]} ")]'
    return tree.xpath(xpath)

class ExtractionError(ValueError):
    pass

class Column(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    selector: str = Field(min_length=1, max_length=500)
    attribute: str = Field(default='text', pattern=r'^[a-zA-Z][\w-]{0,50}$')

    @field_validator('selector')
    @classmethod
    def selector_supported(cls, value):
        if not supported_selector(value):
            raise ValueError('仅支持简单选择器或自动生成的有限层级定位规则')
        return value


def validate_columns(fields):
    if any(f.name in {'source_id', 'source_url', 'status', 'error'} for f in fields):
        raise ExtractionError('字段名称与保留的来源/状态列冲突')
    if not 1 <= len(fields) <= 20 or len({f.name for f in fields}) != len(fields):
        raise ExtractionError('字段必须为 1–20 个且名称不能重复')


def origin(url):
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError as exc:
        raise ExtractionError('网址格式不正确，请检查域名、方括号和端口') from exc
    if p.username or p.password or p.fragment:
        raise ExtractionError('不接受凭据或 URL 片段')
    if p.scheme == 'demo' and p.netloc == 'catalog' and re.fullmatch(r'/[1-9][0-9]?', p.path) and not p.query:
        return 'demo://catalog'
    if p.scheme != 'https' or not p.hostname or port not in (None, 443):
        raise ExtractionError('公开网页只允许 HTTPS 默认端口；演示使用 demo://catalog/1')
    return f'https://{p.hostname.lower()}'


def public_addresses(host):
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ExtractionError('DNS 查询失败') from exc
    addresses = list(dict.fromkeys(row[4][0] for row in records))
    if not addresses or any(not ipaddress.ip_address(ip).is_global or ip == '168.63.129.16' for ip in addresses):
        raise ExtractionError('拒绝私网、本地或保留 IP 地址')
    return addresses


class PinnedHTTPS(http.client.HTTPSConnection):
    """Connect to the checked IP while verifying TLS for the original hostname."""
    def __init__(self, host, address):
        super().__init__(host, timeout=12, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        sock = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


def fetch(url):
    site = origin(url)
    if site == 'demo://catalog':
        number = int(urlsplit(url).path[1:])
        return (f'<html><body><h1>合成示例商品 {number:02}</h1><span class="price">{number * 13}.00</span>'
                f'<p id="sku">DEMO-{number:03}</p><p>纯离线合成数据，不代表真实商品或价格。</p></body></html>')
    p = urlsplit(url)
    addresses = public_addresses(p.hostname)
    connection = PinnedHTTPS(p.hostname, addresses[0])
    try:
        connection.request('GET', (p.path or '/') + ('?' + p.query if p.query else ''), headers={
            'User-Agent': 'WebSheet-Agent/0.2 (static HTML extraction)', 'Accept': 'text/html', 'Accept-Encoding': 'identity'})
        response = connection.getresponse()
        if response.status != 200:
            raise ExtractionError(f'HTTP {response.status}；重定向不自动跟随')
        if response.getheader('Content-Type', '').split(';')[0].strip().lower() not in ('text/html', 'application/xhtml+xml'):
            raise ExtractionError('目标不是 HTML 页面')
        if response.getheader('Content-Encoding', 'identity').lower() != 'identity':
            raise ExtractionError('不支持压缩响应')
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ExtractionError('页面超过 1 MB 限制')
        return data
    except (OSError, http.client.HTTPException) as exc:
        raise ExtractionError('网页连接失败') from exc
    finally:
        connection.close()


def document(content):
    if not content or len(content) > MAX_BYTES:
        raise ExtractionError('页面为空或过大')
    try:
        return html.fromstring(content, parser=html.HTMLParser(no_network=True))
    except (ValueError, TypeError) as exc:
        raise ExtractionError('无法解析 HTML') from exc


def extract(content, fields):
    validate_columns(fields)
    tree = document(content)
    row = {}
    for field in fields:
        selector = field.selector
        nodes = select(tree, selector)
        if len(nodes) != 1:
            raise ExtractionError(f'字段“{field.name}”匹配 {len(nodes)} 个元素；请更新规则（要求恰好一个）')
        value = nodes[0].text_content() if field.attribute == 'text' else nodes[0].get(field.attribute)
        if value is None or not value.strip():
            raise ExtractionError(f'字段“{field.name}”为空或属性不存在')
        row[field.name] = ' '.join(value.split())[:10000]
    return row


def source_id(url):
    return hashlib.sha256(url.encode()).hexdigest()[:20]


def safe_cell(value):
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffe\uffff]', '', str(value))
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')) else text


def export_rows(job, fmt):
    from openpyxl import Workbook
    headers = ['source_id', 'source_url', 'status', 'error'] + [f['name'] for f in job['fields']]
    rows = [[r['source_id'], r['source_url'], r['status'], r['error'] or ''] +
            [r['data'].get(f['name'], '') for f in job['fields']] for r in job['rows']]
    matrix = [[safe_cell(v) for v in row] for row in [headers] + rows]
    if fmt == 'csv':
        stream = io.StringIO(newline='')
        csv.writer(stream).writerows(matrix)
        return stream.getvalue().encode('utf-8-sig')
    if fmt != 'xlsx':
        raise ExtractionError('仅支持 csv 或 xlsx')
    book = Workbook()
    sheet = book.active
    sheet.title = '提取结果'
    for row in matrix:
        sheet.append(row)
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def candidates(content):
    """Return text-only choices. No fetched HTML ever enters the dashboard DOM."""
    tree = document(content)
    result = []
    for node in tree.iter():
        if node.tag not in {'h1', 'h2', 'h3', 'p', 'span', 'a', 'td', 'th', 'li', 'dt', 'dd', 'strong', 'div'}:
            continue
        if any(a.tag in {'script', 'style', 'template', 'noscript', 'head'} or a.get('hidden') is not None for a in [node, *node.iterancestors()]):
            continue
        if any(isinstance(child.tag, str) and child.tag not in {'b', 'i', 'em', 'small', 'br'} for child in node):
            continue
        value = ' '.join(node.text_content().split())
        if not value or len(value) > 1000:
            continue
        choices = [node.tag]
        if node.get('id'):
            choices.insert(0, '#' + node.get('id'))
        choices += [node.tag + '.' + c for c in node.get('class', '').split()]
        selector = next((c for c in choices if supported_selector(c) and len(select(tree, c)) == 1), None)
        if not selector:
            parts = []
            for element in reversed([node, *node.iterancestors()]):
                if not isinstance(element.tag, str):
                    continue
                siblings = [n for n in element.getparent() if n.tag == element.tag] if element.getparent() is not None else [element]
                parts.append(element.tag + (f':nth-of-type({siblings.index(element)+1})' if len(siblings) > 1 else ''))
            selector = ' > '.join(parts)
        if len(selector) > 500 or not supported_selector(selector) or len(select(tree, selector)) != 1:
            continue
        result.append({'value': value, 'selector': selector, 'attribute': 'text', 'tag': node.tag})
        if len(result) == 100:
            break
    return result


def discover_links(content, url):
    site = origin(url)
    links = []
    seen = set()
    for node in document(content).iter('a'):
        href = node.get('href', '').strip()
        if not href or href.startswith('#'):
            continue
        try:
            target = urldefrag(urljoin(url, href))[0]
            if origin(target) != site or target in seen or target == url:
                continue
        except (ExtractionError, ValueError):
            continue
        seen.add(target)
        links.append({'url': target, 'label': ' '.join(node.text_content().split())[:160] or target})
        if len(links) == 100:
            break
    return links
