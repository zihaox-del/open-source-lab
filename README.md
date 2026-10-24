# 网页搬表 · WebSheet Agent

**把同类详情页变成可追溯的表格。先检查一条，再确定性批量执行。**

早期可运行 MVP，不是“万能浏览器代理”。适合整理有权访问的公开静态目录、公告或资料详情页；不适合登录后页面、复杂交互、反爬绕过或任意网站自动操作。

## 为什么做这个

- 手工复制几十个页面容易漏项，通用聊天回答又容易丢失来源。
- 本项目将“字段规则建议”和“批量执行”分开：DeepSeek 只建议规则，执行器不会让模型随意点击、填写或编造缺失值。
- 每条记录保留来源 ID、原始 URL、成功/失败状态和原因；规则失效时明确失败，不用空白假装成功。
- 结果逐行保存到本机 SQLite；中断后继续未处理行，成功与失败记录不覆盖。修正规则后另建任务，便于对照。

## 支持边界

| 引擎 | 实际行为 | 状态 |
| --- | --- | --- |
| 静态 HTML | 读取公开 HTTPS 网页并按规则提取，不执行 JS | 离线端到端与安全测试通过；未对真实网站做兼容性承诺 |
| 浏览器演示 | Playwright 执行内置合成页 JS、读取渲染后 DOM；所有页面网络请求禁用 | 适配器已实现；当前开发环境禁止 Chromium 创建 socket，真实浏览器验收未完成 |

浏览器演示仅接受 `demo://catalog/1` 至 `demo://catalog/99`，不是公网浏览器采集功能。不能声称完成了真实网站浏览器自动化。下一阶段需先解决受控浏览器环境的验收与出站隔离，再扩展公开动态页。

## 快速开始（Linux / macOS，Python 3.11+）

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m websheet
```

在本机打开 http://127.0.0.1:8765。固定仅监听 loopback；不提供账号、远程协作或生产多用户部署，不要暴露到公网。Windows 原生未支持（文件锁使用 `fcntl`）；可自行在 WSL 中试用，但未验收。

1. 点击“载入演示”，得到 **30 个纯合成页面**，不访问真实商品网站。
2. 保持“静态 HTML”，点击“预览样本”。核对名称、价格和编号。
3. 勾选确认，开始采集，导出 Excel 或 CSV。
4. 刷新页面会恢复最近任务；如任务中断，点击继续处理未完成页面。失败行保留原状，不隐式重试。

真实任务：替换为同一 HTTPS 来源的 1–100 个详情页 URL，按字段填写选择器。示例选择器：`h1`、`.price`、`#sku`、`span.price`、`h1#name`。不是完整 CSS 引擎，不支持后代组合、伪类或属性选择器。每字段必须恰好匹配一个非空元素；`text` 读取文本，也可指定 `href` 等属性（原样值，不解析跳转）。

只使用你有权采集的内容，先检查网站条款和 robots/访问政策。本工具**不自动判断网站许可、不自动读取 robots.txt**，不绕过登录、验证码、付费墙或访问限制。没有并发爬虫、搜索发现或自动翻页。

### 可选 DeepSeek

```bash
export DEEPSEEK_API_KEY='your-own-key'
python -m websheet
```

字段名称填写好后，可点击明确同意上传的 AI 建议按钮。它会把样例页面的有限结构/文本摘要发给 `https://api.deepseek.com/chat/completions`（`deepseek-chat`），可能产生你的 API 费用。**不要对含个人、公司机密或未获准外传内容的页面使用该功能。** 模型输出需先预览、人工确认才批量执行。

密钥只从服务端环境读取，不提供浏览器密钥输入框、不写入结果、不在错误信息中回显。不设置环境变量即可完全离线使用演示和手动规则。开发验证仅使用 mock 模型响应，未使用真实密钥或调用付费模型。

### 可选浏览器演示

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python -m websheet
```

载入演示后选择“浏览器演示”。可添加字段 `渲染验证`、选择器 `#rendered`、属性 `text`，预览将显示“浏览器已执行 JavaScript”。静态引擎对这个字段会明确失败，区别于假装执行的演示。

可通过 `PLAYWRIGHT_BROWSERS_PATH` 设置官方浏览器安装缓存，或使用 `WEBSHEET_CHROMIUM_PATH` 指定已安装的 Chromium。不要为了运行而关闭操作系统安全限制。若环境禁止浏览器创建 socket，请改用允许浏览器运行的环境；静态功能不受影响。

## 数据与恢复

- 默认数据库：`data/websheet.sqlite3`，可由 `WEBSHEET_DB` 改到另一条本机路径。
- 数据库保存任务规则快照、原始 URL、提取值和错误，不保存模型密钥；内容为明文，请依照数据敏感程度保护本机目录。
- URL 去重保持首次输入顺序；来源 ID 为 URL SHA-256 的前 20 个十六进制字符。
- 单进程默认服务；OS 文件锁阻止多个任务同时写入运行结果。每处理完一行立即提交，进程退出会释放锁。
- 最近任务 ID 仅保存在当前浏览器 localStorage。清除浏览器数据不删除数据库，但不会自动找回任务列表；可用已记录的任务 ID 调用 API。
- 批次完成不等于全成功，请看失败计数。失败结果不自动覆盖；重新采集应新建任务。
- 导出保留所有状态，包括未处理/失败行。CSV/XLSX 在潜在公式前加 `'`，移除 XML 非法控制字符；数据库中原始提取值不因此修改。

## 限制与安全设计

- 公网只接受 HTTPS 默认端口；禁止凭据 URL、片段、重定向、非 HTML、压缩响应和超过 1 MB 的页面。
- DNS 返回值全部校验公网地址，连接固定到已验证 IP，并验证原始主机 TLS；阻止私网、loopback、常用云元数据地址和 DNS 混合返回。
- 不携带 cookies，不使用系统 HTTP 代理，不保存会话。公共页面访问可能被网站拒绝；这是失败，不是绕过理由。
- 服务验证 Host/Origin，禁止跨站调用。不提供身份认证，因此必须保持 loopback、本机单用户使用。
- 字段 1–20 个、名称唯一，每个值最多保存 10,000 字符。规则不是语义理解；页面改版、重复元素和动态内容可能失败。
- 浏览器演示绝不读取用户提供的 HTML，也不导航公网 URL；只运行源代码中固定的合成页面脚本。
- 依赖清单锁定直接依赖，**不是完整可复现的传递依赖锁文件**；暂未进行第三方独立渗透测试。

## 开发与验证

```bash
python -m unittest discover -s tests -v
python -m compileall -q websheet tests
python scripts/demo.py
```

测试使用合成数据，不触网、不花费模型费用。覆盖 30 页批量任务、预览、两种导出、源 ID、崩溃恢复、重复执行、失效规则、SSRF、重定向、公式注入、非法 XLSX 字符、AI 结构化返回和本机 API 边界。`scripts/demo.py` 会在临时目录运行 30 页并验证导出，输出明确的合成数据报告。

可选真实浏览器测试：`WEBSHEET_BROWSER_TEST=1 python -m unittest discover -s tests -v`。需要可运行的 Chromium；默认明确跳过，不将未运行计为成功。参见 [验证记录](docs/VERIFICATION.md)。

MIT © 2026 WebSheet Agent contributors。欢迎小范围、可测试的贡献，参见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [SECURITY.md](SECURITY.md)。

## English summary

WebSheet Agent is an original, local-first MVP for reviewed static-page extraction into traceable CSV/XLSX files. It supports same-origin HTTPS URL lists, manual selectors, optional DeepSeek selector suggestions, per-row failures and durable resume. It is not a universal browser agent. A separate Playwright renderer runs bundled synthetic demos only with page network access disabled; real browser QA is explicitly unverified in this sandbox. Public JavaScript pages, logins, CAPTCHA bypass, Windows-native and hosted multi-user operation are out of scope. Start with `python -m websheet`; use the 30-page offline demo without any API key.
