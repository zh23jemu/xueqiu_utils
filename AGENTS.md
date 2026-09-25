# AGENTS.md — xueqiu_utils

雪球（xueqiu.com）组合（cube）监控工具：抓取组合每日调仓记录、检测跨组合重复持仓，并通过邮件推送日报。

## 运行

- 依赖：`pip install -r requirements.txt`（注意：该文件为 UTF-16 编码，`cat` 输出会带空格，属正常）。
- GUI 入口：`python position_ui.py`（PySide6 + qt-material 深色主题）。
- 无测试、无 lint 配置。代码风格遵循 `.agent/rules/code-style-guide.md`：Python 3.10、PEP 8、docstring、类型注解。
- 提交信息用中文、Conventional Commits 风格（如 `feat(position_ui): ...`）。

## 结构

- `position_ui.py` — 全部 GUI：主窗口 `XueqiuApp`、定时调度（APScheduler）、日志、邮件。
- `src/models/cube.py` — `Cube` 类：调仓历史、基本信息等（requests + JSON API）。
- `src/utils/common.py` — 读 token、带 Cookie 的 GET、时间戳转换。
- `src/utils/cube.py` — 跨组合重复持仓检测（纯函数）。
- `src/utils/verify.py` — 滑动验证码自动过验证（DrissionPage + ddddocr），独立脚本，会向当前目录写 `bg.jpg`/`full.jpg`。

## 数据与敏感文件

- 数据目录（GUI 中指定）必须包含：`cubes.json`（组合 ID 列表，元素以 `ZH` 开头）和 `tokens.json`（`{"tokens": [{"token": "xq_a_token=..."}]}`，只读第一个）。
- `tokens.json` 已被 gitignore，绝不提交；`gui_config.json` 虽被 git 跟踪但含 base64 编码的邮箱授权码（`b64:` 前缀），修改它前先确认是否应提交。

## 编辑须知

- **持仓只能靠浏览器抓，没有可用接口**：`/cubes/holding/list.json` 等二十多个变体已全部 404 下线；持仓数据仍由服务端渲染进组合页 HTML 的 `SNB.cubeInfo.view_rebalancing.holdings`，老正则 `SNB\.cubeInfo = {.*}` + `split('=')[1]` 解析依然有效。**改这块前先读下面"雪球访问门槛"一节。**
- **雪球访问门槛（2026-09 变更）**：组合页 `/P/ZHxxxxxx` 现在需要完整登录态，只注入 `xq_a_token` 会被重定向到 `/snowman/account/login`；且 WAF 会拦截所有普通 HTTP 请求抓取 HTML（各种 cookie 组合 + 完整 Chrome 请求头实测均返回 110310 字节挑战页），只有真实浏览器能过。JSON 接口（净值、调仓）不受影响。**首次使用必须先在程序控制的 Chrome 窗口里手动登录一次**，cookie 持久化在 DrissionPage 用户数据目录（`%LOCALAPPDATA%\Temp\DrissionPage\userData\9222`），之后定时任务才能抓到持仓。
- **绝不要用 `tokens.json` 的 token 覆盖浏览器 cookie**：浏览器登录后拿到的是与账号绑定的新 `xq_a_token`，用旧 token 覆盖会立刻让会话失效。症状很有欺骗性——**第一个组合能抓到，从第二个开始全部跳登录页**。判断登录态看 `xq_is_login` cookie 是否存在（`u` / `xq_a_token` 存在但 `xq_is_login` 缺失＝未真正登录）。
- **服务器上跑测试要用交互式会话**：SSH 落在会话 0（无桌面），DrissionPage 拉不起 Chrome（`BrowserConnectError: 127.0.0.1:9222`）。用 `schtasks /Create ... /IT /RU <用户>` 建任务把脚本跑在 RDP 桌面会话里，输出重定向到文件再读。残留的会话 0 Chrome 进程会占住 9222 端口，需按 `SESSION eq 0` 清掉。
- **线程边界**：`run_task` 运行在后台线程，禁止直接操作 Qt 控件；所有 UI 更新必须经 `self.comm` 的 Signal（`print_signal` / `finished_signal` / `update_date_signal`）。
- **邮件密码**：内存中是明文，落盘时由 `save_config` 自动加 `b64:` 前缀编码；不要把明文写回配置。
- **`get_position()` 依赖本地 Chrome**：通过 DrissionPage 控制真实浏览器读取页面内嵌 JSON；无浏览器或未登录时抛 `RuntimeError`，不再抛 `IndexError`。
- **别用窄 except 兜底索引**：`re.findall(...)[0]` 匹配空列表会抛 `IndexError`，而 `except json.JSONDecodeError` 捕不到，会一路冒到上层兜底并被静默吞掉。匹配前先判空、抛可读异常。
- **响应歧义**：雪球 API 失败时返回 dict（含 `error_code`），成功返回 list 或含 `list` 键的 dict；`common.get_http_response` 不做区分，调用方需自行判断类型并重试（参考 `Cube.get_basic_info` 的 while 循环写法）。
- **调仓筛选**：只统计 `category == 'user_rebalancing'` 且 `status == 'success'` 的记录，日期格式为 `YYYYMMDD`。
- 请求之间有 `time.sleep(2)` 节流（GUI 主循环），勿移除以免触发风控。
- **失败信息必须进邮件**：调仓/持仓的失败原因要 append 进 `json_logs`，否则邮件里会看不到任何提示（用户只能翻 GUI 面板）。
- **缩进陷阱**：重复持仓检测的 `else` 必须挂在 `if portfolios:` 上。历史 bug：该 `else` 错挂在 `if duplicates:` 下，导致持仓全失败时整块被跳过，邮件里重复持仓部分静默消失。
