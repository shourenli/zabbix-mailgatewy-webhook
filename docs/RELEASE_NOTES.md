# mailgatewy v1.0.1 — Zabbix 告警邮件 HTTP→SMTP 网关

> **最新发布（latest）**：`v1.0.1`
>
> 仓库：`git@github.com:shourenli/zabbix-mailgatewy-webhook.git`（私有）
> 标签：`v1.0.1` → 指向 `main`（**14 个文件**，含本 release note）
> 上一版：`v1.0.0` → `5b0f3a9`（11 个文件）
> 发布线：`main`

---

## 简介

`mailgatewy` 是一个可独立部署、随处复用的 **HTTP→SMTP 邮件投递网关**。它对外暴露统一的 HTTP 入口 `POST /send`，接收 JSON（`to / subject / body / profile`），内部通过原生 `smtplib.SMTP_SSL` 完成真实邮箱投递。

核心价值：**解耦消息生产方与真实邮箱投递**。Zabbix Webhook、Shell 脚本、定时任务等任何能发 HTTP 的调用方，都不再需要关心 SMTP 凭据与协议细节，只需调用网关即可发信，从而把「发信账号 / 密码 / 服务器」从各生产方收拢到网关一处统一管理。

---

## 技术基础与兼容性

本方案源自 **Zabbix 告警邮件投递**的实际生产需求，**构建并验证于 Zabbix 6.0 LTS 与 Zabbix 7.0 LTS 两个 LTS 版本**。

| Zabbix 版本 | 调用路径 | 参考配置 |
|---|---|---|
| **Zabbix 6.0 LTS** | 远端 Zabbix 跨主机调用网关 `http://<网关地址>:8025/send` | `yaml/zbx6_remote_aimedia.yaml`（`zabbix_export.version: '6.0'`） |
| **Zabbix 7.0 LTS** | 本机 Zabbix 走回环调用网关 `http://127.0.0.1:8025/send` | `yaml/zbx7_local_aimedia.yaml`（`zabbix_export.version: '7.0'`） |

两份参考配置均为 Zabbix **Media（`type: WEBHOOK`）导出文件**，可直接在 *Administration → Media types → Import* 导入，内含：

- Webhook 媒介脚本 —— 先调用大模型（GLM）生成告警「白话解读」，再连同告警字段拼装 HTML 邮件体，最后 POST 到本网关；
- 与既有邮件媒介**逐字段对齐的标题/正文模板**：
  - 告警：`【故障据点】: {INVENTORY.TAG}`
  - 恢复：`【恢复通知】【据点名称】: {INVENTORY.TAG}`
- 全部凭据以 `CHANGE_ME_*` 占位符给出。

> 网关本身**不依赖 Zabbix**：任何能发起 HTTP 请求的系统（Shell、CI、业务应用）都可复用；Zabbix 6.0 / 7.0 LTS 是它最主要的调用方，也是本版本完成真实收信验证的场景。

---

## 核心特性

- **HTTP 统一入口**：单一 `POST /send` 端点，`application/json`，字段 `to / subject / body / profile`。
- **三种 Token 鉴权**：`Authorization: Bearer <token>`、裸 token 头、`?token=<token>` 查询参数均可。
- **多 Profile 发信账号**：内置 `local` / `remote` 两套 Profile，允许不同调用方走不同发信账号；由 `GATEWAY_<PROFILE>_SMTP_*` 覆盖，未覆盖时回落顶层默认值。
- **HTML 邮件支持**：`body` 可直接传 HTML，网关原样透传。
- **并发限流 + 自动重试**：`threading.BoundedSemaphore` 限制并发 SMTP 会话，避免突发打爆邮箱服务器；失败按退避基数自动重试。
- **防伪成功判定**：严格检查 `smtplib.sendmail()` 返回值 —— 只要存在被拒绝的收件人即判定失败，杜绝「看似发送成功、实际被拒」的静默误报。
- **多收件人归一化**：`to` 同时接受 `string` 与 `list`。Zabbix 7 在真实告警触发时会把 `{ALERT.SENDTO}` 展开为**数组**，网关内部统一归一化，避免「测试按钮能发、真实告警收不到」的差异。
- **安全默认，零硬编码机密**：无环境变量时 SMTP 凭据回落 `UNSET_PLS_SET_ME`、网关 Token 默认 `CHANGE_ME_LOCAL_TOKEN`；源码 / 配置示例 / 参考 YAML 均不含任何真实内网 IP 或公司实名。

---

## 版本历史

### v1.0.1（本版）

**仅文档与工程规范化，程序逻辑与 `v1.0.0` 完全一致（`src/` 与 `tests/` 逐字节相同）。**

| 变更 | 说明 |
|---|---|
| 新增 `.gitattributes` | `* text=auto eol=lf`（脚本/配置显式 `eol=lf`，二进制显式 `binary`）。根治 Windows 下 `core.autocrlf=true` 把归档包转成 CRLF、导致 `deploy/install.sh` 在 Linux 上报 `bad interpreter` 的问题 |
| README 补充兼容性 | 明确本方案构建并验证于 **Zabbix 6.0 LTS 与 7.0 LTS**；新增「接入 Zabbix」步骤（含用户媒介必须 Enabled 的提醒） |
| README 修正 | 修正环境变量名（`GATEWAY_SMTP_MAX_CONCURRENCY` / `_MAX_RETRIES` / `_RETRY_BACKOFF`）、补全目录树、修正标题拼写 |
| 补回 `LICENSE` | GPL-3.0（建库时选定，曾因历史覆盖而丢失） |
| release note 随版发布 | `v1.0.0` 的 tag 中不含 `docs/`，本版起 release note 随 tag 一并分发 |

> **本版将 tag 内容与 `main` 对齐**：`v1.0.0` 的 tag 停在 11 个文件，`main` 已前进到 14 个文件；`v1.0.1` 起两者一致。

### v1.0.0

首次正式发布（stable）。

- 通用 HTTP→SMTP 网关核心实现（鉴权 / 多 Profile / 限流 / 重试 / 防伪成功 / 多收件人归一化）；
- 一键部署脚本与 systemd 单元；
- Zabbix **6.0 LTS 与 7.0 LTS** 两类 Media（Webhook）参考配置，含标题/正文模板对齐；
- 凭据安全测试套件（`pytest` 全绿）；
- 完成脱敏的干净 git 基线（仓库重建后全新历史，无残留旧对象）。

---

## 目录结构

```
mailgatewy/
├── src/gateway.py                # 核心实现：HTTP 服务 + SMTP 投递编排
├── deploy/
│   ├── install.sh                # 一键安装（建用户/建目录/装 systemd 单元）
│   ├── gateway.service           # systemd 单元
│   └── env.conf.example          # 环境变量示例（含全部 GATEWAY_* 项）
├── yaml/
│   ├── zbx7_local_aimedia.yaml   # 参考：Zabbix 7.0 LTS Media 导出（本机调用）
│   └── zbx6_remote_aimedia.yaml  # 参考：Zabbix 6.0 LTS Media 导出（远端调用）
├── tests/
│   ├── conftest.py
│   └── test_gateway_creds.py     # 覆盖占位符回落/env 覆盖/profile 继承等
├── docs/RELEASE_NOTES.md         # 本文件
├── AGENTS.md                     # 协作约定（改动必 commit + 更新测试）
├── LICENSE                       # GPL-3.0
├── .gitattributes                # 统一 LF 换行，保证归档包在 Linux 可用
└── .gitignore
```

---

## 快速开始

```bash
# 1) 克隆（要最新文档请用 main 或 v1.0.1）
git clone --branch v1.0.1 git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy

# 2) 一键安装（创建用户 zabbix-ai-email、目录 /opt/zabbix-ai-email、/etc/zabbix-ai-email）
sudo ./deploy/install.sh

# 3) 配置环境变量
sudo cp /etc/zabbix-ai-email/env.conf.example /etc/zabbix-ai-email/env.conf
# 编辑 env.conf，至少设置：
#   GATEWAY_TOKEN=<你的鉴权token>
#   GATEWAY_SMTP_USER / GATEWAY_SMTP_PASS / GATEWAY_SMTP_FROM

# 4) 启动服务
sudo systemctl enable --now gateway

# 5) 测试
curl -X POST http://127.0.0.1:8025/send \
  -H "Authorization: Bearer <GATEWAY_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"to":"you@example.com","subject":"test","body":"<h1>Hello</h1>","profile":"local"}'
```

---

## API

### `POST /send`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `to` | string / list | 是 | 收件人邮箱（支持多收件人列表） |
| `subject` | string | 是 | 邮件标题 |
| `body` | string | 是 | 邮件正文（支持 HTML） |
| `profile` | string | 否 | 发信账号 Profile，缺省用默认 |

**响应码**

| 状态 | 含义 |
|------|------|
| 200 | 投递成功（全部收件人被接受） |
| 400 | 参数缺失/非法（缺 `to/subject/body` 或格式错误） |
| 401 | Token 鉴权失败 |
| 404 | 路径不存在 |
| 502 | SMTP 投递失败（含被拒绝收件人） |

---

## 配置（环境变量）

| 变量 | 说明 |
|------|------|
| `GATEWAY_HOST` | 监听地址（默认 `127.0.0.1`） |
| `GATEWAY_PORT` | 监听端口（默认 `8025`） |
| `GATEWAY_TOKEN` | 鉴权 Token（默认 `CHANGE_ME_LOCAL_TOKEN`） |
| `GATEWAY_SMTP_*` | 默认发信账号（`HOST` / `PORT` / `USER` / `PASS` / `FROM` / `HELO`） |
| `GATEWAY_<PROFILE>_SMTP_*` | 各 Profile 覆盖项，如 `GATEWAY_REMOTE_SMTP_USER` |
| `GATEWAY_SMTP_MAX_CONCURRENCY` | 最大并发 SMTP 会话数（默认 5） |
| `GATEWAY_SMTP_MAX_RETRIES` | 失败重试次数（默认 2） |
| `GATEWAY_SMTP_RETRY_BACKOFF` | 重试退避基数（秒，默认 0.8） |

---

## 开发与测试

```bash
pip install pytest
pytest -v
```

测试覆盖：无环境变量时占位符回落、`GATEWAY_*` 环境变量覆盖、`GATEWAY_<PROFILE>_*` 继承顶层默认、缺失凭据告警判定。

---

## 已知事项

- **换行符**：仓库已通过 `.gitattributes` 统一为 LF。若你的工作副本是早期版本（`v1.0.0` 及以前），Windows 下 checkout 可能带 CRLF，此时自行打归档包需加 `-c core.autocrlf=false -c core.eol=lf`，否则 `install.sh` 在 Linux 上会报 `bad interpreter`。
- **用户媒介状态**：Zabbix 中「媒介类型」或「用户 → 媒介」被禁用（`active=0`）时不会有任何邮件外发，且 Zabbix 侧不一定报错。排障时优先检查该项。
- **凭据轮换**：若曾在生产环境与历史版本同源使用过 SMTP 密码 / 网关 Token / 大模型 API Key，建议轮换。

---

## 安全与脱敏说明

- 全仓库凭据一律**占位符化**（`CHANGE_ME_*` / `UNSET_PLS_SET_ME`）；源码、配置示例、参考 YAML 均无任何真实 SMTP 密码、Token、内网 IP 或公司实名。
- 发布前已对 **git 完整历史**做三层脱敏改写（文件内容 / commit message / 作者身份），使可达历史中不再残留真实内网 IP 或公司实名。
- 对于强推后 GitHub 服务端仍可凭旧 SHA 取回的**不可达旧对象**，已通过**删除原仓库并同名重建**彻底切断 —— 重建后按旧 SHA 取回返回 `not our ref`，旧内容不可再获取。

---

*mailgatewy v1.0.1 — 2026-09-17*
