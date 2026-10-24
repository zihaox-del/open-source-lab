# 网页搬表 · WebSheet Agent

**把同类详情页变成可追溯的表格。先检查一条，再确定性批量执行。**

v0.3 早期可运行版本，不是“万能浏览器代理”。适合整理有权访问的公开静态目录、公告或资料详情页；不适合登录后页面、复杂交互、反爬绕过或任意网站自动操作。

## 为什么做这个

- 手工复制几十个页面容易漏项，通用聊天回答又容易丢失来源。
- 本项目将“字段规则建议”和“批量执行”分开：DeepSeek 只建议规则，执行器不会让模型随意点击、填写或编造缺失值。
- 每条记录保留来源 ID、原始 URL、成功/失败状态和原因；规则失效时明确失败，不用空白假装成功。
- 结果逐行保存到本机 SQLite；中断后继续未处理行，成功与失败记录不覆盖。修正规则后另建任务，便于对照。

## 支持边界

| 引擎 | 实际行为 | 状态 |
| --- | --- | --- |
| 静态 HTML | 读取公开 HTTPS 网页并按规则提取，不执行 JS | 离线端到端与安全测试通过；未对真实网站做兼容性承诺 |
| 浏览器演示 | Playwright 执行内置合成页 JS、读取渲染后 DOM；所有页面网络请求禁用 | GitHub Actions 已通过真实 Chromium 合成页 JS 渲染测试；v0.3 四项真实仪表盘流程测试通过；桌面及 390px 窄屏合成状态截图已审阅 |

浏览器演示仅接受 `demo://catalog/1` 至 `demo://catalog/99`，不是公网浏览器采集功能。不能声称完成了真实网站浏览器自动化。GitHub Actions 已验证内置合成页真实渲染；下一阶段仍需扩展多视口/无障碍验收及面向公网的出站隔离，才能考虑公开动态页。

## 普通用户：免 Python 便携包（Windows / Linux）

Windows x64 和 Linux x86_64 已通过原生构建及**实际 ZIP 解压后的可执行文件验收**，不需要安装 Python。下载 [已验证的构建产物](https://github.com/zihaox-del/open-source-lab/actions/runs/40052433273)；它们是早期试用包，尚未代码签名，不是正式稳定发行版。macOS 便携包暂未提供。

1. 在上述成功运行页面下载 `websheet-agent-Windows-X64` 或 `websheet-agent-Linux-X64`（Actions 下载通常需要登录 GitHub；产物保留 14 天）。下载物是外层产物 ZIP，先解压得到应用 ZIP 和同名 `.sha256`，再完整解压应用 ZIP。
2. 完整解压 ZIP 到自己可读的位置，不要直接在压缩软件里运行，也不要只复制 `.exe`。
3. Windows 双击 `WebSheet-Agent.exe`，启动成功后自动打开本机浏览器。无需管理员权限，无需安装 Python、浏览器自动化组件或填写 Key。
4. 保留启动窗口，按下方“第一次使用”完成合成数据演示。停止时在启动窗口按 Ctrl+C，等待窗口退出；关掉网页不会停止采集。

未签名程序可能被系统拦截。不要关闭安全防护、绕过警告或使用来源不明的镜像；请检查源码/构建记录，或等待可信分发方式。端口已占用时会报错，不会打开或接管未知服务。数据默认留在当前用户目录，不会写进解压目录；删除程序文件不等于删除数据。

包内 `START_HERE.txt` 说明隐私、数据目录、备份与停止方法，`THIRD_PARTY_NOTICES.md` 和 `licenses/` 保留运行时依赖许可证。包内不带真实任务、密钥、账号或 Chromium；可选 Playwright 演示不属于便携包功能。

## 开发者运行（Python 3.11+）

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m websheet
```

启动后自动在本机浏览器打开 http://127.0.0.1:8765（可用 `python -m websheet --no-browser` 关闭自动打开）。固定仅监听 loopback；不提供账号、远程协作或生产多用户部署，不要暴露到公网。Windows 源码使用 `msvcrt` 文件锁，POSIX 使用 `flock`；Windows 实际兼容性以对应提交 CI 为准。Windows 虚拟环境激活命令为 `.venv\Scripts\activate`。

使用 `python -m websheet --self-check` 可无网络验证 30 条合成数据及 XLSX 导出。启动器支持 `--port 8766`，默认仍为 8765；浏览器草稿按端口隔离，数据库历史不按端口隔离。

也可运行 `sh scripts/start.sh`：先检查 Python/依赖、数据目录和端口，再启动。不自动安装软件或修改全局设置。单独检查：`python -m websheet.preflight`。

### 第一次使用：无需 CSS、无需 API Key

1. 点击“先试试演示”，自动读取第一条合成页面，进入内容选择。共 **30 个纯合成页面**，不访问真实商品网站。
2. 选择“合成示例商品 01”和“13.00”等内容，把默认“列1”“列2”改成你需要的名称，例如“名称”“价格”。系统自动验证真实样本，生成样表，不替你猜字段含义。
3. 检查样表后，点击“确认样表，开始整理 30 页”。这是明确开始批量执行的唯一确认，不需要另找预览按钮或确认复选框。
4. 任务在后台逐页运行，界面显示完成计数。可以刷新、查看历史，或暂停；暂停会等待当前页读取结束。成功和失败行不自动重复运行。
5. 完成后点击“下载 Excel”或“下载 CSV”，然后可“整理另一组网页”。导出包括所有状态，请检查失败计数；失败行会附原因。旧任务从“查看本机历史任务”找回。

### 换成自己的公开静态页面

- 粘贴一个或多个详情页网址，点击“读取网页，选择内容 →”，用第一条网址作为样本并点选字段。候选只显示解析后的文本，不展示或执行原网页 HTML；最多 100 个候选，最多选 20 列。
- 批量网址可每行粘贴一个，最多 100 个同源 HTTPS 网址；重复项按首次出现顺序去重。
- 也可展开“从列表页找详情网址”，读取该页最多 100 个去重同源链接，自行勾选真正的详情页。**不自动翻页、不访问候选链接、不判断链接一定是详情页**。
- 未找到所需字段，可能是页面需要 JavaScript/登录，或其结构超出当前候选识别范围。不要把空结果当作成功。
- 高级选项保留手动规则：`h1`、`.price`、`#sku`、`span.price`，以及自动生成的有限层级规则，如 `html > body > p:nth-of-type(2)`。不是完整 CSS/XPath 引擎，不接受任意脚本。
- 自动定位按样本结构生成，页面布局变化可能读到其他值或失败；批量前必须核对预览，完成后抽查结果。每字段必须恰好匹配一个非空元素。

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

载入演示后，在高级选项选择“浏览器演示”。可添加字段 `渲染验证`、选择器 `#rendered`、属性 `text`，预览将显示“浏览器已执行 JavaScript”。静态引擎对这个字段会明确失败，区别于假装执行的演示。

可通过 `PLAYWRIGHT_BROWSERS_PATH` 设置官方浏览器安装缓存，或使用 `WEBSHEET_CHROMIUM_PATH` 指定已安装的 Chromium。不要为了运行而关闭操作系统安全限制。若环境禁止浏览器创建 socket，请改用允许浏览器运行的环境；静态功能不受影响。

## 数据与恢复

- 默认数据库：Windows `%LOCALAPPDATA%\WebSheetAgent\websheet.sqlite3`；Linux `${XDG_DATA_HOME:-~/.local/share}/WebSheetAgent/websheet.sqlite3`；macOS `~/Library/Application Support/WebSheetAgent/websheet.sqlite3`（macOS 便携包未提供、未验收）。可由 `WEBSHEET_DB` 指定另一条本机路径。
- **旧版本升级**：原来的 `data/websheet.sqlite3` 不会自动搬迁或删除。请先停止旧服务并备份，再设置 `WEBSHEET_DB` 指向旧文件，或把该文件复制到上述新目录；不要在服务仍运行时复制数据库。首次使用新目录会显示空历史，不代表旧数据已丢失。
- 数据库保存任务规则快照、原始 URL、提取值和错误，不保存模型密钥；内容为明文，请依照数据敏感程度保护本机目录。
- URL 去重保持首次输入顺序；来源 ID 为 URL SHA-256 的前 20 个十六进制字符。
- 单进程默认服务；跨进程 OS 文件锁阻止多个任务同时写入运行结果。每处理完一行立即提交，进程退出会释放锁。通过本项目启动器按 Ctrl+C 停止时，会等待当前行结束再暂停未完成任务；强制结束/关机后，重启会恢复为可继续状态。
- 任务历史保存在 SQLite，清除浏览器数据后仍能从历史列表找回。浏览器 localStorage 保存当前草稿（网址列表、样本网址、字段规则）、选中任务和未确认创建请求的标识/内容；均为本机明文，不用于共享。刷新不停止后台任务；停止服务会中断任务，重启后可继续待处理行。
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

测试使用合成数据，不触网、不花费模型费用。覆盖 30 页批量任务、无 CSS 候选、同源链接发现、预览、两种导出、源 ID、崩溃恢复、后台暂停/继续、并发重复请求、失效规则、SSRF、重定向、公式注入、非法 XLSX 字符、AI 结构化返回和本机 API 边界。`scripts/demo.py` 会在临时目录运行 30 页并验证导出，输出明确的合成数据报告。

可选真实浏览器测试：`WEBSHEET_BROWSER_TEST=1 python -m unittest discover -s tests -v`。需要可运行的 Chromium；默认明确跳过，不将未运行计为成功。参见 [验证记录](docs/VERIFICATION.md)。

MIT © 2026 zihaox-del and WebSheet Agent contributors。欢迎小范围、可测试的贡献，参见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [SECURITY.md](SECURITY.md)。

## English summary

WebSheet Agent is an original, local-first MVP for reviewed static-page extraction into traceable CSV/XLSX files. Version 0.3 introduces a three-stage first-use flow with one URL input, text-value selection, automatic sample preview and an explicit start confirmation. Persistent history, bounded same-origin link discovery and cooperative pause/resume remain available. Native Windows x64 and Linux x86_64 portable bundles passed exact-ZIP executable smoke tests without Python on PATH. They are unsigned early test builds, not a signed installer or a guarantee for every machine. Manual selectors and optional DeepSeek suggestions remain available. Duplicate creation requests are idempotent. It is not a universal browser agent. A separate Playwright renderer runs bundled synthetic demos only with page network access disabled; real Chromium rendering of 30 bundled synthetic pages passed in GitHub Actions, and previous-version dashboard tests passed. The redesigned v0.3 dashboard passed four real-browser workflow tests and desktop/390px synthetic-state screenshot review; no full accessibility audit is claimed. Public JavaScript pages, logins, CAPTCHA bypass and hosted multi-user operation are out of scope. Native Windows validation passed on the CI runner; macOS has no portable build. Start with `python -m websheet`; use the 30-page offline demo without any API key.


## v0.3 验证状态

[测试流水线](https://github.com/zihaox-del/open-source-lab/actions/runs/40052433129) 的真实 Chromium 作业 **59 项测试全部通过，零跳过**；Python 3.11–3.13 离线作业也通过（54 通过、5 项浏览器测试明确跳过）。四项真实仪表盘流程覆盖三步上手、自动样表、重复点击、刷新、暂停/继续、历史、实际下载、读取失败/无候选以及迟到的异步结果。

[Windows/Linux 打包验收](https://github.com/zihaox-del/open-source-lab/actions/runs/40052433273) 实际运行 ZIP 解压后的程序，验证不依赖 PATH 中的 Python、30 条合成采集、两种导出、端口冲突拒绝、正常停止和重启恢复。下载包的 SHA256、界面源码和实际原生依赖声明已核对。

桌面及 390px 窄屏的输入、点选、完成/部分失败状态截图已审阅，未见阻挡主要操作的重叠或裁切；宽表格需要横向滚动，不代表所有设备或无障碍验收。未验证真实网站兼容性、付费模型、macOS 或所有 Windows 版本。无需模型 Key。详见 [验证记录](docs/VERIFICATION.md)。
