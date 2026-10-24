WebSheet Agent — 本机网页转表格

1. 将 ZIP 完整解压到一个普通文件夹，不要直接在压缩包里运行。
2. Windows：双击 WebSheet-Agent.exe。Linux：运行 WebSheet-Agent。
3. 浏览器会打开本机界面。先选“先试试演示”，选择内容并检查自动生成的样表，
   再点击“确认样表，开始整理 30 页”，完成后下载 Excel 或 CSV。
   不需要 Python、管理员权限、账号、API Key 或 Chromium；内置演示也不需要联网。
4. 用完后在启动窗口按 Ctrl+C 停止。只关闭浏览器标签页不会停止程序。

如果浏览器没有自动打开，请复制启动窗口中的本机网址到浏览器。
默认网址为 http://127.0.0.1:8765 。端口被占用时程序会拒绝启动，
不会擅自连接另一个服务；可以关闭已有程序或从终端使用 --port 8766。

请保留整个文件夹，包括 _internal 和 licenses，不要只复制 exe。
这是本地服务，不应暴露到公网。任务数据保存位置以启动窗口提示为准；
停止程序后再备份该目录。下载的表格保存在浏览器的下载位置。
Windows 数据默认在 %LOCALAPPDATA%\WebSheetAgent\websheet.sqlite3；
Linux 在 ${XDG_DATA_HOME:-~/.local/share}/WebSheetAgent/websheet.sqlite3。
数据库与浏览器草稿均为本机明文，可能含网址、规则和提取内容。删除程序文件夹
不会删除历史数据。不设置 API Key、不主动同意 AI 摘要发送时，不会调用模型服务。
没有自动上传任务、注册表改动、自启动、后台系统服务或自动更新。
旧源码版本的 data/websheet.sqlite3 不会自动迁移；先停止旧服务并备份，
再设置 WEBSHEET_DB 指向旧文件或将其复制到新数据目录。

安全与限制
- 仅处理你有权访问和提取的公开 HTTPS 静态 HTML 页面；请遵守网站条款。
- 不是任意网站的自动化浏览器，不处理登录、验证码或绕过反爬。
- JavaScript 浏览器演示属于源码版可选功能，此便携包不包含 Chromium。
- AI 辅助不是必需功能，启用前需要单独配置及明确同意数据发送。
- 此版本没有代码签名。只从你信任的项目构建/发布渠道获取，核对 SHA256。
  不要关闭杀毒软件或绕过系统安全警告；无法确认来源时请勿运行。
- CI 构建产物只有通过该平台的打包烟雾测试后才适合下载试用，
  不代表经过所有设备、Windows 版本或第三方网站验证。

高级用法（终端）
WebSheet-Agent.exe --no-browser --port 8766
WebSheet-Agent.exe --self-check
Linux 将 WebSheet-Agent.exe 换为 ./WebSheet-Agent。

许可证
本项目采用 MIT 许可证，见 LICENSE.txt。
第三方许可证见 THIRD_PARTY_NOTICES.md 与 licenses 文件夹。
