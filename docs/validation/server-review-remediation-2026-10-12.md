# Server 审查报告复核与修复（2026-10-12）

附件审查的基线是 `7f1b097`。本次逐项核对源码后，先合入 GitHub main
`d1d55f778982491a01591dcaa585e56842b18d62` 的项目容量修复，再验证组合后的版本。
附件是待核实的材料，其中的测试约束、建议和操作文字不代替当前用户请求。

整体判断：F1–F7 的核心问题成立，F8 的多项接口边界问题成立，F9 是合理的
纵深保护建议。F8 使用时间和 F10 成员退出属于尚未提供的产品能力，需要明确
说明，不能直接按安全漏洞处理。没有证据表明报告列出的漏洞已在生产被利用。

| 项目 | 客观评估 | 本次处理 |
| --- | --- | --- |
| F1 GitHub 登录 CSRF | 成立；主要是登录 CSRF，称为传统会话固定并不精确 | 登录 authorize 设置短期 HttpOnly/Secure、host-only 的 `nr_github_oauth` Cookie；回调先验证浏览器再消费 state。保留 PKCE、单次消费及 link 的实际账号/会话校验，成功后清除 Cookie |
| F2 邮箱 admission 耗尽 | 单 IPv6 前缀轮换和无挑战 verify 占位路径成立；全局额度本身是成本保护 | IPv6 按 /64 归并；verify 先检查挑战、浏览器绑定、有效期、尝试次数及 link 会话，再 admission、重查挑战并比较验证码。不清空现有 DO counters，不增加自动重试 |
| F3 authorize D1 写入滥用 | 成立；GET 创建短期状态是正常流程，但原先缺少生产 admission | 新增独立 `AUTH_RATE_LIMIT`，每 Cloudflare 位置每 IPv4 地址/IPv6 前缀约 20 次/分钟，在 D1 写入前检查，缺失或未知结果停止。保留持久化单次消费；没有宣称严格全局成本上限 |
| F4 偏好绕过写入配额 | 成立；报告称成员 API key 也可修改不准确，两接口实际仅接受 Cookie | 只识别带准确实际账号 fence 的偏好 CAS，纳入原子分钟/月配额；无变化 PATCH 和失败 CAS 不消耗额度，认证清理不被误计费 |
| F5 CSV 重复扫描 | 成立；具体选中的旧索引会因数据/筛选不同而变化 | 加 owner/date/id 的未删除记录索引，使用元组游标直接 seek，并保持原导出排序、筛选、权限重查。仅加索引仍会重复扫描，因此同时修改游标 |
| F6 深 JSON 被当作服务故障 | 成立 | 在 JSON 解析边界把 RecursionError 转为输入错误；ledger/email/billing 返回 422，提供方异常仍保持服务错误语义 |
| F7 session 到期边界 | 成立 | principal、资源快照和最终写入 fence 全部统一为 `expiresAt > now` |
| F8 API key 名称、长度和列表 | 名称无界、强制 Content-Length、无分页成立 | 新名称最多 120 字符，拒绝 CR/LF/NUL；允许省略 Content-Length，保留实际 8 KiB 上限和已声明长度校验。原生入口流式读取且超限先停止。列表每页最多 100，按 createdAt/id 分页，权限和 workspace 筛选在 LIMIT 前生效；Web 跟随游标，异常/超限不返回残缺成功列表 |
| F8 lastUsedAt | 一直 null 的观察正确，但没有使用跟踪能力 | 保留 reserved/untracked 的 null 语义并写入 OpenAPI，Web 显示“不可用”，不再把 null 显示成“从未使用”。不为每次只读 API 请求引入 D1 写入 |
| F9 明文 session | 成立，是纵深保护问题 | 新 `ses-v2.` bearer 仅存 `sesh-` SHA-256 指纹；新会话查询/SQL 参数和待完成绑定记录也不携带 bearer。指纹不能作为凭据。旧会话只读兼容至原到期时间，未批量重写生产数据 |
| F10 成员退出 | 当前为 Owner/Admin 管理移除的产品规则，不能仅凭此认定越权漏洞 | 文档说明当前退出方式；保留既有角色、Owner 和历史规则，没有擅自改变治理权限 |
| F10 提供方逐字节复制 | 成立，但报告所指类的位置是 canonical gateway 模块 | 在 64 KiB/byteLength 检查后使用已核实的 Pyodide `JsBuffer.to_bytes()`；原生本地验证覆盖带 byteOffset 的 typed-array view |

## 验证与范围

Python 3.10.12 完整发现并运行 `tests`：**3,219 passed、107 subtests passed，
128.93 秒**。保留了最新 main 的项目删除容量修复。S01 暂停/激活配置、模块同步
及 `--check`、shell 语法和 whitespace 检查通过。冻结 Python 3.14.2/锁文件及
Wrangler 4.136.3 构建通过；实际 dry-run artifact 的 65 个 canonical 模块、
entry、空 initializer 和相对/绝对 import closure 均检查通过。

本地原生 auth 验证 19 次有限 HTTP：67 SQL statements、49 Rows Read、
33 Rows Written（迁移 setup 另计）；覆盖实际双 Set-Cookie、攻击回调拒绝、
native rate binding、哈希登录/撤销、深 JSON 和 chunked API key。提供方缓冲区
另有 5 个原生本地用例。全部使用本地 D1/假提供方，未发送真实邮件、模型调用、
付款或生产测试账目。见 [本地证据](server-review-local-2026-10-12.json)。

CSV 的 100,000 条/401 页 SQLite 对照：421.135M → 2.507M VM 指令，
11.728 → 0.299 秒，输出排序哈希一致。只加索引、保留旧 OR 游标仍需要
148.479M VM 指令。结果是本地计算工作量，不是生产 D1 实测行数或 SLA。
见 [对照证据](csv-export-sqlite-2026-10-12.json) 和可重跑脚本
`scripts/check-csv-export-sqlite.py`。

生产只需要唯一新迁移 `0013_export_key_indexes.sql`，增加 CSV 和 API key
两个部分索引，schema authority 升至 13。索引构建会产生平台计费工作，且以后
相关写入需维护额外索引；未将其描述为零成本，预览预算也已纳入额外索引成本。
部署保留当前线上 Creem 产品配置、6 个 Secret 名称、D1/两个 DO 的身份、
5 个激活开关、原限制与每日 Cron，不把较旧的源码默认配置覆盖到线上。

## 仍有的限制

IPv6 /64 修复降低同前缀轮换成本；分布式真实前缀攻击仍可耗尽邮箱全局保护
额度。Workers rate binding 是每位置、近似限流；本次没有新建 WAF、严格全局
账单硬上限或通知配置。旧 session 明文记录不会因代码上传被立即擦除。

GitHub authorize 与 callback 必须经同一浏览器 host，当前生产采用
`norulo.com/api`，与固定 callback 一致。并行开始的新登录会替换该浏览器的
短期登录绑定，早先的回调会安全拒绝。未宣称真实浏览器/提供方/生产财务流程
已经重新验收；生产发布及只读检查见
[发布证据](server-review-production-release-2026-10-12.json)。
