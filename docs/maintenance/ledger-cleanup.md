# 记账产品工程清理清单

日期：2026-09-28。范围：norulo-server、norulo-web 及控制它们的根 AGENTS.md。
清理前两端工作树没有未提交变更。所有改动留在工作树，未提交、推送或部署。

## 已清理

| 类别 | 结果 |
| --- | --- |
| Server 旧代码 | 删除 Worker 入口不可达的 8 个模块：旧仓库目录发布、VM 配置/日志/部署状态、GitHub REST/GraphQL 采集、旧 Jev 问题和子进程传输 |
| Server 旧测试/工具 | 删除对应旧模块测试、Pi/release-gate 夹具、失效数据库模板、个人 Codex 启动包装和 VM 环境示例 |
| Server 账单残留 | 删除旧 processing usage DTO/空接口、旧额度字段、未使用的处理/调度表定义；保留账户 CAS、支付事件、签名、幂等和订阅事实 |
| Server 依赖 | 移除 Authlib、cryptography、PyGithub、requests、urllib3 根生产依赖及锁内无用传递依赖；保留 Worker SDK 锁和部署检查 PyYAML |
| Web 旧入口/代码 | 删除原型 review 页和导航、重复 Pages 代理、旧产品读取/下载/防抖工具、旧 Pi 夹具和失效翻译生成脚本 |
| Web 账单残留 | 删除旧智能处理用量/PR、CI、Updates 活动面板；购买、升级、取消、恢复、支付历史继续保留 |
| Web 文案/样式 | 五种共享语言目录各删除 489 条无用短语，裁剪无用动态规则/图标；删除 792 条无引用样式规则和 2 个无用动画，保留当前 token/layout 规则 |
| Web 分享素材 | SVG、生成脚本及 PNG 均改为项目支出记账；检查了生成图片 |
| 文档/规则 | 两端 AGENTS.md 和根产品说明收敛为当前记账产品；15 份阶段交接合并成两份相互链接的当前验收记录；删除设计中的旧代码基线和过时执行规则 |
| 临时产物 | 删除日志、缓存、旧截图、快照、构建产物及空历史目录；运行验证产生的缓存在交付前再次清除 |

原本借用旧产品名称的 API Key 列表和首页支出预览样式已改名。
CI 收集全部存续 Server 测试，安装部署检查额外依赖，并在检查前生成 Worker 模块镜像。

## 保留

- GitHub 登录/App 授权、Session/API Key 安全、Creem 支付事务和当前记账功能/测试。
- 当前设计、OpenAPI、三份未执行目标 migration、预览/生产配置、部署保护和离线建议评估。
- 开发依赖环境、Worker 安装依赖和 CodeGraph 本地索引属于标准工具环境；不把它们当产品源代码删除。
- 无效旧 scope/restriction 的拒绝用例属于当前权限边界回归，仍保留。
- 旧本地状态数据库可能包含账户/支付事实，已移出两个工程并保存在
  [本地状态备份](../.cleanup-backups/2026-09-28/server-local-state)，未读取或删除其中业务数据。

## 验证及边界

- Server：Python 3.10.12，全部 107 项测试、22 项子测试通过；镜像同步、契约/配置静态检查、依赖锁校验通过。
- Web：33 个测试文件、252 项测试、Lint、构建和离线配置检查通过；分享素材变更后现有 SEO/定位测试 3 项通过。
- 两端 diff 空白检查通过；源代码可达性及现行文档链接已复核。CodeGraph 查询未返回，使用本地 AST 回退。
- 最近 Server CI 失败于缺少 PyYAML，已在工作树修复；当前改动没有远程 CI 结果。Web 查询未返回工作流运行。
- 浏览器连接器不可用，本次没有页面截图验证。S17 的真实 workerd CSV 桥接/Worker 联调和 S18 远程验收仍开放。
- 未运行 Wrangler/workerd/D1 命令、远程迁移、部署、cron 或真实提供商调用。成本暂停和显式授权门槛保持有效。

当前状态：[Server 验收](../validation/local-acceptance.md)、
[Web 验收](../../../norulo-web/docs/validation/local-acceptance.md)。

## 全面复核与 CodeGraph 排除

2026-09-28 后续复核清除了四个源码和测试均无引用的 Server 函数、Web
已退役的 setIssue 参数和历史处理用量翻译，以及本地 .codex 旧交接、
预览图片和四工程自动提交脚本。旧 Reviewer 专用本地技能也已移除；
当前 norulo-dev 技能、配置、依赖和数据库备份保留。
移除了 Web 未使用且 Server 已不存在的 /settings API 客户端，并清除了
目标目录已不存在的 Web 原始视觉基线 worktree 注册；实际存续 worktree 保留。

已确认安装的 CodeGraph 0.9.4 使用 .gitignore / Git 可见文件，不支持
独立的 .codegraphignore。工作区根目录及两端仓库的 .gitignore 已补齐
依赖、生成镜像、工具目录、缓存、构建和备份的排除规则。源码、现行测试、
契约和 migrations 保留可见。扫描器实测选中工作区 150 个文件，
Server 63 个、Web 87 个，没有任何被排除目录中的源文件。

Server 的现有索引已强制刷新：63 个文件，0 个待同步变化；实际 map
也检查了没有依赖、镜像或旧 probe 路径。Web 未隐式创建独立索引。
根目录 .gitignore / 工具清理属于非 Git 工作区本地设置；两端仓库规则
随代码提交。更改规则后应刷新已有索引，避免旧节点残留。

## 删除的受版本控制文件

### norulo-server（28 个）

- `.codegraph/codegraph.lock`
- `.env.example`
- `docs/handoffs/S01-contract-deployment.md`
- `docs/handoffs/S05-ledger-auth-billing-keys.md`
- `docs/handoffs/S06-projects-categories.md`
- `docs/handoffs/S07-expenses.md`
- `docs/handoffs/S08-reports-export.md`
- `docs/handoffs/S13-ledger-suggestions.md`
- `docs/handoffs/S15-legacy-cleanup.md`
- `docs/handoffs/S17-local-integration.md`
- `ops/codex-node22`
- `norulo_server/cloudflare_repository_directory.py`
- `norulo_server/deployment_status.py`
- `norulo_server/github_transport.py`
- `norulo_server/jev_deadline_transport.py`
- `norulo_server/jev_questions.py`
- `norulo_server/logging_config.py`
- `norulo_server/repository_access.py`
- `norulo_server/system_config.py`
- `tests/db_template.py`
- `tests/fixtures/pi_result_publication.mjs`
- `tests/release_gate_minimal_support.py`
- `tests/release_gate_sample_set_support.py`
- `tests/test_deployment_status.py`
- `tests/test_github_graphql_transport.py`
- `tests/test_github_transport_contracts.py`
- `tests/test_jev_deadline_transport.py`
- `tests/test_jev_questions.py`

### norulo-web（21 个）

- `.playwright-cli/page-2026-08-04T08-58-46-286Z.yml`
- `2026-07-31-130656-this-session-is-being-continued-from-a-previous-c.txt`
- `dead_full.txt`
- `docs/handoffs/S09-projects-categories.md`
- `docs/handoffs/S10-expense-flows.md`
- `docs/handoffs/S11-ledger-reports.md`
- `docs/handoffs/S12-ledger-copy.md`
- `docs/handoffs/S14-ledger-suggestion-ui.md`
- `docs/handoffs/S16-legacy-web-cleanup.md`
- `docs/handoffs/S17-local-integration.md`
- `functions/api/[[path]].js`
- `functions/api/proxy.test.js`
- `retired-graph-footprint.test.js`
- `review.html`
- `scripts/split-locales.mjs`
- `src/lib/download.js`
- `src/lib/product-data.js`
- `src/lib/quota-display.js`
- `src/lib/use-debounced-value.js`
- `src/review-main.jsx`
- `src/test/fixtures/pi-public-issue.json`

## 临时目录/文件的首次清理清单

| 路径 | 文件数 | 字节 |
| --- | ---: | ---: |
| `norulo-server/norulo_server/cloudflare_repository_directory.py` | 1 | 5515 |
| `norulo-server/norulo_server/deployment_status.py` | 1 | 2944 |
| `norulo-server/norulo_server/github_transport.py` | 1 | 9892 |
| `norulo-server/norulo_server/jev_deadline_transport.py` | 1 | 4045 |
| `norulo-server/norulo_server/jev_questions.py` | 1 | 5047 |
| `norulo-server/norulo_server/logging_config.py` | 1 | 4061 |
| `norulo-server/norulo_server/repository_access.py` | 1 | 3391 |
| `norulo-server/norulo_server/system_config.py` | 1 | 35553 |
| `norulo-server/tests/test_deployment_status.py` | 1 | 4054 |
| `norulo-server/tests/test_github_graphql_transport.py` | 1 | 3107 |
| `norulo-server/tests/test_github_transport_contracts.py` | 1 | 6900 |
| `norulo-server/tests/test_jev_deadline_transport.py` | 1 | 2734 |
| `norulo-server/tests/test_jev_questions.py` | 1 | 2511 |
| `norulo-server/tests/db_template.py` | 1 | 2594 |
| `norulo-server/tests/release_gate_minimal_support.py` | 1 | 4665 |
| `norulo-server/tests/release_gate_sample_set_support.py` | 1 | 9329 |
| `norulo-server/tests/fixtures/pi_result_publication.mjs` | 1 | 2092 |
| `norulo-server/ops` | 11 | 120831 |
| `norulo-server/generated` | 1 | 59793 |
| `norulo-server/.agents` | 0 | 0 |
| `norulo-server/.pytest_cache` | 5 | 373503 |
| `norulo-server/.wrangler` | 1 | 1934 |
| `norulo-server/cloudflare/server/.wrangler` | 583 | 60512573 |
| `norulo-server/docs/handoffs` | 8 | 21220 |
| `norulo-server/.codegraph/codegraph.lock` | 1 | 5 |
| `norulo-server/.env.example` | 1 | 3859 |
| `norulo-web/src/lib/download.js` | 1 | 1195 |
| `norulo-web/src/lib/product-data.js` | 1 | 6167 |
| `norulo-web/src/lib/use-debounced-value.js` | 1 | 353 |
| `norulo-web/src/lib/quota-display.js` | 1 | 762 |
| `norulo-web/src/review-main.jsx` | 1 | 309 |
| `norulo-web/review.html` | 1 | 752 |
| `norulo-web/dead_full.txt` | 1 | 2549 |
| `norulo-web/2026-07-31-130656-this-session-is-being-continued-from-a-previous-c.txt` | 1 | 47729 |
| `norulo-web/scripts/split-locales.mjs` | 1 | 2654 |
| `norulo-web/retired-graph-footprint.test.js` | 1 | 1359 |
| `norulo-web/src/test/fixtures/pi-public-issue.json` | 1 | 4935 |
| `norulo-web/functions` | 2 | 16901 |
| `norulo-web/.playwright-cli` | 5 | 1551 |
| `norulo-web/.pytest_cache` | 4 | 542 |
| `norulo-web/output` | 135 | 6078125 |
| `norulo-web/dist` | 38 | 1161794 |
| `norulo-web/vendor` | 0 | 0 |
| `norulo-web/docs/handoffs` | 7 | 11225 |
| `norulo-server/.codex-server.err.log` | 1 | 20668 |
| `norulo-server/.codex-server.out.log` | 1 | 0 |
| `norulo-server/.p5a-server-regression.log` | 1 | 1336 |
| `norulo-server/.p5a-thread-red.log` | 1 | 7662 |
| `norulo-web/.codex-vite-browser.err.log` | 1 | 0 |
| `norulo-web/.codex-vite-browser.out.log` | 1 | 4144 |
| `norulo-web/.codex-vite.err.log` | 1 | 5117 |
| `norulo-web/.codex-vite.out.log` | 1 | 137202 |
| `norulo-web/.p5a-check.log` | 1 | 6076 |
| `norulo-web/.p5a-final-check.log` | 1 | 5664 |
| `norulo-web/.p5a-green.log` | 1 | 700 |
| `norulo-web/.p5a-lint.log` | 1 | 88 |
| `norulo-web/.p5a-red.log` | 1 | 886748 |
| `norulo-web/.seo-vite.err.log` | 1 | 3418 |
| `norulo-web/.seo-vite.out.log` | 1 | 29617 |
| `norulo-web/.vite-dev.log` | 1 | 22852 |
| `norulo-web/dev-server-run.err.log` | 1 | 35377 |
| `norulo-web/dev-server-run.out.log` | 1 | 74100 |
| `norulo-web/dev-server.log` | 1 | 7595 |
| `norulo-web/vite-dev.err.log` | 1 | 0 |
| `norulo-web/vite-dev.log` | 1 | 9252 |
| `norulo-server\norulo_server\__pycache__` | 610 | 15667750 |
| `norulo-server\tests\__pycache__` | 952 | 17627997 |
| `norulo-server\cloudflare\server\src\__pycache__` | 1 | 5790 |
| `norulo-server\cloudflare\server\__pycache__` | 1 | 19458 |
