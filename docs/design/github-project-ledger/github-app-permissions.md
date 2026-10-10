# 当前版本的 GitHub App 权限

2026-10-10。本文记录新注册的真实 Norulo App 和当前代码要求，替代迁移时
机械替换名称的源服务 App 设置说明。源服务历史 App ID、Client ID 和验收
记录不是该 Norulo App 的身份或验收证据。当前步骤配置 GitHub App 和必要
Secrets，暂不发布完整业务程序或创建数据库。

当前 Organization 关联、多仓库项目和账本邀请不需要新增
Organization 或 Account 权限。以下是代码实际调用所需的最小配置。

| GitHub App 设置区域 | 权限 | 当前需要 |
| --- | --- | --- |
| Repository permissions | Metadata | Read-only，GitHub App 默认必需 |
| Organization permissions | Members 及其他组织权限 | No access |
| Account permissions | Email addresses 及其他账户权限 | No access |
| Enterprise permissions | 全部 | No access |
| Repository permissions | Contents、Pull requests、Issues、Actions、Administration 等 | No access |

当前 Server 仅使用 user access token 调用 `GET /user`、
`GET /user/installations`、`GET /user/installations/{id}/repositories`，
以及邀请时的公开 `GET /users/{login}`。当前用户、安装发现和公开用户
查询无额外 fine-grained permission 要求；仓库列表要求 Metadata read。
Organization ID/login/type 来自当前授权安装的 account metadata，未调用
组织成员、团队、仓库内容、PR、Issues 或 Actions 接口。

如未来增加 `GET /orgs/{org}/members` 或组织团队目录功能，再增加
Organization permissions → Members → Read-only。如未来读取私有邮箱，再
增加 Account permissions → Email addresses → Read-only 并接入相应接口。
这些功能当前未实现，不是本版安装要求。GitHub App user token 使用 App 的
fine-grained permissions；旧授权 URL 的 OAuth scope 字符串不会额外赋权。

如需关联目标 Organization 的仓库，还需在该 Organization 安装 App，
并选择需要使用的仓库。独立项目不需要仓库安装或 Organization 关联。
Only select repositories 可以限制安装范围；All repositories 由组织策略决定。
Organization Owner 可安装或批准请求，也可限制仓库管理员的安装权限。
如 App 要安装到注册账户之外的账户或组织，注册设置
Where can this GitHub App be installed? 需允许 Any account。
这是安装范围设置，不会公开仓库数据或改变 Norulo 的账本角色。

用户授权 App、App 安装到组织以及安装选中的仓库分别校验；可见仓库是
调用成员现有 GitHub access 与 App 安装范围的交集。Organization 的 GitHub
成员身份不会自动授予 Norulo Owner/Admin/Editor/Viewer。账本角色由
Norulo 显式邀请和成员权限管理决定。

## 已核实的 Norulo App 公开信息

用户已新建 App。2026-10-10 通过 GitHub `GET /apps/norulo` 只读核对：

| 字段 | 已核实值 |
| --- | --- |
| Name | Norulo |
| Owner | Organization Norulo |
| Slug | norulo |
| OAuth Client ID | Iv23li78ZPeUgSxJkLUj |
| Permissions | 仅 Metadata read |
| Events | 空列表 |

公开页面：[Norulo App](https://github.com/apps/norulo)。
管理入口：[Norulo App 设置](https://github.com/organizations/Norulo/settings/apps/norulo)。
管理入口需要拥有该 App 管理权限的 GitHub 网页登录会话。Client ID 和 slug
是公开配置；当前用户令牌实现不需要数字 App ID、App private key 或 webhook
secret，历史 App ID 不应填入当前配置。

## 管理页面需核对的设置

| 设置 | 当前代码需要的值 |
| --- | --- |
| Homepage URL | https://norulo.com |
| Callback URL | https://norulo.com/api/auth/github/callback |
| Setup URL | https://norulo.com/api/integrations/github/callback |
| Expire user authorization tokens | 开启 |
| Request user authorization (OAuth) during installation | 关闭 |
| Redirect on update | 关闭 |
| Enable Device Flow | 关闭 |
| Webhook Active | 关闭；Webhook URL、secret 和事件不填 |
| Where can this GitHub App be installed? | Any account |

代码分开签发登录和安装的一次性 state。安装时请求 OAuth 授权会使 GitHub
不提供 Setup URL，而改跳 OAuth Callback；自动 Redirect on update 也可能
缺少当前安装流程签发的 state，因此两项关闭。当前代码使用浏览器 OAuth
与 PKCE，不使用 Device Flow 或 GitHub webhook；保留令牌过期以配合已实现
的 refresh token 轮换。

公开 App API 未核实上述 callbacks、后台选项、安装范围或 Client Secret。
events 为空也不能单独证明 Webhook Active 已关闭。管理者需在网页逐项保存
并核对；本次公开元数据检查没有编辑这些设置，也没有完成真实登录或安装
验收。之后将同一 App 的 Client Secret 安全配置到
`NORULO_GITHUB_CLIENT_SECRET`，不得写入文档、Git 或聊天。此次步骤不进行
完整业务发布。临时暂停 Worker 已为安全录入 Secret 创建，新的
`NORULO_GITHUB_TOKEN_KEY` 已安全生成并上传；用户当前只需在 Cloudflare
控制台填写 `NORULO_GITHUB_CLIENT_SECRET`。生产 D1 仍暂停，真实登录未验收。

官方依据：

- [仓库列表及 Metadata read](https://docs.github.com/en/rest/apps/installations#list-repositories-accessible-to-the-user-access-token)
- [用户可访问的 App 安装](https://docs.github.com/en/rest/apps/installations#list-app-installations-accessible-to-the-user-access-token)
- [当前用户](https://docs.github.com/en/rest/users/users#get-the-authenticated-user)、[公开用户查询](https://docs.github.com/en/rest/users/users#get-a-user)
- [GitHub App user access token](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)
- [注册 GitHub App 的 callbacks 和选项](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)
- [安装 App 到组织](https://docs.github.com/en/apps/using-github-apps/installing-a-github-app-from-a-third-party)
- [请求 Organization Owner 安装](https://docs.github.com/en/apps/using-github-apps/requesting-a-github-app-from-your-organization-owner)
- [组织成员接口](https://docs.github.com/en/rest/orgs/members)
- [修改 App 注册权限](https://docs.github.com/en/apps/maintaining-github-apps/modifying-a-github-app-registration#changing-the-permissions-of-a-github-app)
- [App 管理者资格](https://docs.github.com/en/apps/maintaining-github-apps/about-github-app-managers)
