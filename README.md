# mailgatewy

[English](#english) | [简体中文](#简体中文)

---

## English

[English](#english) | [简体中文](#简体中文)

SMTP Mail Gateway — a standalone, reusable HTTP→SMTP delivery service.

It exposes a single HTTP `POST /send` endpoint that accepts a JSON payload (recipient / subject / HTML body) and delivers the message over native SMTP. It is designed to decouple *message producers* (monitoring alert webhooks, scripts, external systems) from *actual mailbox delivery*, making it generic infrastructure for any system that needs to send HTML email.

### Use Cases & Compatibility

This project originates from the real-world need to **deliver Zabbix alert emails**, and **the solution is built and validated on Zabbix 6.0 LTS and Zabbix 7.0 LTS**:

| Zabbix version | Call pattern | Reference config |
|---|---|---|
| **Zabbix 6.0 LTS** | Remote Zabbix calls the gateway across hosts: `http://<gateway-host>:8025/send` | `yaml/zbx6_remote_aimedia.yaml` |
| **Zabbix 7.0 LTS** | Local Zabbix calls the gateway via loopback: `http://127.0.0.1:8025/send` | `yaml/zbx7_local_aimedia.yaml` |

Both reference configs are Zabbix **Media (Webhook media type) export files** and contain:

- A webhook media script: first call an LLM to generate a plain-language "digest" of the alert, then assemble the HTML email body together with the alert fields;
- Title/body templates **aligned with the existing email media** (problem: `【故障据点】: {INVENTORY.TAG}`, recovery: `【恢复通知】【据点名称】: {INVENTORY.TAG}`);
- All credentials given as `CHANGE_ME_*` placeholders that must be replaced after importing into Zabbix.

> The gateway itself does **not depend on Zabbix**. Any system that can issue an HTTP request (shell, CI, business apps) can reuse it; Zabbix 6.0 / 7.0 LTS is simply its primary caller.

### Features

- **Unified HTTP entry point**: just `POST /send`, no need to deal with SSH/SMTP details.
- **Token auth**: supports `Authorization: Bearer <token>`, a bare token, and `?token=`.
- **Multiple profiles**: built-in `local` / `remote` sending accounts, switchable per target environment.
- **HTML email**: the body is sent as `text/html`, so HTML templates can be assembled directly.
- **Concurrency limiting & automatic retry**: a semaphore caps concurrency; failures are retried with a backoff strategy.
- **No false success**: the `smtplib.sendmail()` return value is strictly checked — any refused recipient is treated as a failure.
- **Secure defaults**: with no environment variables set, SMTP credentials fall back to the `UNSET_PLS_SET_ME` placeholder; no secrets are hard-coded.

### Directory Layout

```text
mailgatewy/
├── src/
│   └── gateway.py            # Core program (Python standard library only, zero third-party deps)
├── deploy/
│   ├── install.sh            # One-shot installer (creates user/dirs/service/env.conf)
│   ├── gateway.service       # systemd unit
│   └── env.conf.example      # Environment variable sample
├── yaml/                     # Zabbix Media (Webhook) reference configs
│   ├── zbx6_remote_aimedia.yaml  # Zabbix 6.0 LTS, remote call
│   └── zbx7_local_aimedia.yaml   # Zabbix 7.0 LTS, local call
├── tests/                    # pytest regression tests
├── docs/RELEASE_NOTES.md     # Release notes
├── AGENTS.md                 # Collaboration conventions (every change must be tested)
├── LICENSE                   # GPL-3.0
├── .gitattributes            # Enforce LF newlines so archives do not break on Linux
└── README.md
```

### Quick Start

#### 1. Clone and install

```bash
git clone --branch v1.0.3 git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy/deploy
sudo bash install.sh
```

The install script will:

- Create the directories `/opt/zabbix-ai-email` and `/etc/zabbix-ai-email`;
- Create a dedicated low-privilege user `zabbix-ai-email`;
- Copy `gateway.py` and the systemd unit;
- Generate `env.conf` on first run;
- Register and start `gateway.service`.

#### 2. Configure credentials

Edit `/etc/zabbix-ai-email/env.conf` and change at least three items:

```ini
GATEWAY_TOKEN=your-gateway-token
GATEWAY_SMTP_USER=your-smtp-user
GATEWAY_SMTP_PASS=your-smtp-password
GATEWAY_SMTP_FROM=display-sender
```

Then restart the service:

```bash
sudo systemctl restart gateway.service
```

#### 3. Test sending

```bash
curl -s -X POST http://127.0.0.1:8025/send \
  -H 'Authorization: Bearer your-gateway-token' \
  -H 'Content-Type: application/json' \
  -d '{"to":"recipient@example.com","subject":"test","body":"<b>hello</b>"}'
```

A `200` response means success; logs are available via `journalctl -u gateway -f`.

### Integrating with Zabbix

1. Pick the reference config matching your version from the table above and import the Media type in Zabbix (*Administration → Media types → Import*);
2. Replace the `CHANGE_ME_*` placeholders (gateway host, token, LLM API key, etc.);
3. Bind the media to a user and **set its status to Enabled** (`active=1`).

> **Practical warning**: a Zabbix user media is **disabled by default** (`active=0`) in many setups; while it is disabled Zabbix will not send any alert email, and it does not necessarily report an error. Always check this first when troubleshooting, and set it to **Enabled**.

### API

#### `POST /send`

Request body (JSON):

| Field | Required | Type | Description |
|---|---|---|---|
| `to` | yes | string/list | Recipient. A single address or an array of addresses |
| `subject` | yes | string | Email subject |
| `body` | yes | string | Email body (sent as `text/html`) |
| `profile` | no | string | Which sending account to use, defaults to `local` |

Auth: the request must include `Authorization: Bearer <token>` (or a bare token / `?token=`).

Responses:

| HTTP code | Meaning |
|---|---|
| 200 | Email successfully delivered to the MTA |
| 400 | Missing required field or invalid profile |
| 401 | Token check failed |
| 404 | Path other than `/send` |
| 502 | SMTP delivery failed (including after retries) |

### Environment Variables

| Variable | Description |
|---|---|
| `GATEWAY_HOST` / `GATEWAY_PORT` | HTTP listen address (default `127.0.0.1:8025`) |
| `GATEWAY_TOKEN` | Caller authentication token |
| `GATEWAY_SMTP_HOST` / `GATEWAY_SMTP_PORT` | SMTP server and port (default 465 SSL) |
| `GATEWAY_SMTP_USER` / `GATEWAY_SMTP_PASS` | Sending account and password |
| `GATEWAY_SMTP_FROM` | Display sender |
| `GATEWAY_SMTP_HELO` | EHLO hostname for the handshake (default `localhost`) |
| `GATEWAY_<PROFILE>_SMTP_*` | Per-profile overrides of the corresponding SMTP parameters |
| `GATEWAY_SMTP_MAX_CONCURRENCY` | Max concurrent SMTP sessions (default 5) |
| `GATEWAY_SMTP_MAX_RETRIES` | Number of retries after a failure (default 2) |
| `GATEWAY_SMTP_RETRY_BACKOFF` | Retry backoff base in seconds (default 0.8) |

### Development & Testing

```bash
pip install pytest
pytest -v
```

Test coverage: secure placeholder fallback when no env is set, env overrides, named-profile inheritance from the same source, and detection of missing-credential warnings.

### Deploying to systemd (manual)

```bash
sudo mkdir -p /opt/zabbix-ai-email /etc/zabbix-ai-email
sudo cp src/gateway.py /opt/zabbix-ai-email/
sudo cp deploy/env.conf.example /etc/zabbix-ai-email/env.conf
# edit env.conf and fill in the real credentials
sudo chmod 600 /etc/zabbix-ai-email/env.conf
sudo cp deploy/gateway.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gateway.service
```

### License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**. The full license text is in the [`LICENSE`](LICENSE) file.

You are free to use, modify and redistribute this software, including for commercial purposes, provided that:

- derivative works are distributed under the same GPL-3.0 license;
- the complete corresponding source code is made available;
- any changes to the original source are clearly marked.

The software is provided **without any warranty**, to the extent permitted by law. See the [official GNU GPL v3.0 page](https://www.gnu.org/licenses/gpl-3.0.html) for the authoritative terms.

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

[English](#english) | [简体中文](#简体中文)

SMTP 邮件网关 —— 一个可独立部署、随处复用的 HTTP→SMTP 投递服务。

对外暴露一个 HTTP `POST /send` 接口，接收 JSON 载荷（收件人/主题/HTML 正文），内部调用原生 SMTP 发送邮件。设计用于把「消息生产方」（如监控告警 Webhook、脚本、外部系统）与「真实邮箱投递」解耦，是任何需要发送 HTML 邮件的系统的通用基础设施。

### 适用场景与兼容性

本项目源自 **Zabbix 告警邮件投递**的实际需求，**解决方案构建并验证于 Zabbix 6.0 LTS 与 Zabbix 7.0 LTS**：

| Zabbix 版本 | 调用方式 | 参考配置 |
|---|---|---|
| **Zabbix 6.0 LTS** | 远端 Zabbix 跨主机调用网关：`http://<网关地址>:8025/send` | `yaml/zbx6_remote_aimedia.yaml` |
| **Zabbix 7.0 LTS** | 本机 Zabbix 走回环调用网关：`http://127.0.0.1:8025/send` | `yaml/zbx7_local_aimedia.yaml` |

两份参考配置均为 Zabbix **Media（Webhook 媒介类型）导出文件**，内含：

- Webhook 媒介脚本：先调用大模型生成告警的「白话解读」，再与告警字段一起拼装 HTML 邮件体；
- 与既有邮件媒介**对齐的标题/正文模板**（告警 `【故障据点】: {INVENTORY.TAG}`、恢复 `【恢复通知】【据点名称】: {INVENTORY.TAG}`）；
- 全部凭据以 `CHANGE_ME_*` 占位符给出，导入 Zabbix 后需自行替换。

> 网关本身**不依赖 Zabbix**。任何能发起 HTTP 请求的系统（Shell、CI、业务应用）都可复用；Zabbix 6.0 / 7.0 LTS 只是它最主要的调用方。

### 特性

- **HTTP 统一入口**：只需 `POST /send`，无需关心 SSH/SMTP 细节。
- **Token 鉴权**：支持 `Authorization: Bearer <token>`、裸 token、`?token=` 三种方式。
- **多 Profile**：内置 `local` / `remote` 两套发信账号，可按目标环境切换。
- **HTML 邮件**：正文按 `text/html` 发送，可直接拼 HTML 模板。
- **并发限流 & 自动重试**：信号量限制并发，失败按退避策略自动重试。
- **防伪成功**：严格检查 `smtplib.sendmail()` 返回值，任一收件人被拒即视为失败。
- **安全默认**：无环境变量时 SMTP 凭据回落 `UNSET_PLS_SET_ME` 占位符，不硬编码机密。

### 目录结构

```text
mailgatewy/
├── src/
│   └── gateway.py            # 核心程序（Python 标准库实现，零第三方依赖）
├── deploy/
│   ├── install.sh            # 一键安装脚本（创建用户/目录/service/env.conf）
│   ├── gateway.service       # systemd unit
│   └── env.conf.example      # 环境变量样例
├── yaml/                     # Zabbix Media（Webhook）参考配置
│   ├── zbx6_remote_aimedia.yaml  # Zabbix 6.0 LTS，远端调用
│   └── zbx7_local_aimedia.yaml   # Zabbix 7.0 LTS，本机调用
├── tests/                    # pytest 回归测试
├── docs/RELEASE_NOTES.md     # 发布说明
├── AGENTS.md                 # 协作约定（每次改动须 commit + 测试）
├── LICENSE                   # GPL-3.0
├── .gitattributes            # 统一 LF 换行，避免归档包在 Linux 上失效
└── README.md
```

### 快速开始

#### 1. 克隆并安装

```bash
git clone --branch v1.0.3 git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy/deploy
sudo bash install.sh
```

安装脚本会：

- 创建目录 `/opt/zabbix-ai-email` 与 `/etc/zabbix-ai-email`；
- 创建低权限专用用户 `zabbix-ai-email`；
- 拷贝 `gateway.py` 与 systemd unit；
- 首次生成 `env.conf`；
- 注册并启动 `gateway.service`。

#### 2. 配置凭据

编辑 `/etc/zabbix-ai-email/env.conf`，至少修改三项：

```ini
GATEWAY_TOKEN=你的鉴权Token
GATEWAY_SMTP_USER=发件账号
GATEWAY_SMTP_PASS=发件密码
GATEWAY_SMTP_FROM=显示发件人
```

然后重启服务：

```bash
sudo systemctl restart gateway.service
```

#### 3. 测试发送

```bash
curl -s -X POST http://127.0.0.1:8025/send \
  -H 'Authorization: Bearer 你的TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"to":"recipient@example.com","subject":"测试","body":"<b>你好</b>"}'
```

响应 `200` 即成功；日志位于 `journalctl -u gateway -f`。

### 接入 Zabbix

1. 按上表选择对应版本的参考配置，在 Zabbix 中导入 Media type（*Administration → Media types → Import*）；
2. 替换配置中的 `CHANGE_ME_*` 占位符（网关地址、Token、大模型 API Key 等）；
3. 给用户绑定该 Media，并**将其状态置为 Enabled**（`active=1`）。

> **实操警告**：Zabbix 用户媒介（media）在多数环境下**默认为 disabled**（`active=0`），此时告警不会外发，且 Zabbix 侧不一定报错。排障时请优先检查该项，并将其置为 **Enabled**。

### API 说明

#### `POST /send`

请求体（JSON）：

| 字段 | 必填 | 类型 | 说明 |
|---|---|---|---|
| `to` | 是 | string/list | 收件人。可传单个邮箱或邮箱数组 |
| `subject` | 是 | string | 邮件主题 |
| `body` | 是 | string | 邮件正文（按 `text/html` 发送） |
| `profile` | 否 | string | 使用哪个发信账号，缺省 `local` |

鉴权：请求头需含 `Authorization: Bearer <token>`（或裸 token / `?token=`）。

响应：

| HTTP 码 | 含义 |
|---|---|
| 200 | 邮件已成功投递至 MTA |
| 400 | 缺少必填字段或 profile 非法 |
| 401 | Token 校验失败 |
| 404 | 非 `/send` 路径 |
| 502 | SMTP 发送失败（含重试后） |

### 环境变量

| 变量 | 说明 |
|---|---|
| `GATEWAY_HOST` / `GATEWAY_PORT` | HTTP 监听地址（默认 `127.0.0.1:8025`） |
| `GATEWAY_TOKEN` | 调用方鉴权 Token |
| `GATEWAY_SMTP_HOST` / `GATEWAY_SMTP_PORT` | SMTP 服务器与端口（默认 465 SSL） |
| `GATEWAY_SMTP_USER` / `GATEWAY_SMTP_PASS` | 发件账号与密码 |
| `GATEWAY_SMTP_FROM` | 显示发件人 |
| `GATEWAY_SMTP_HELO` | 握手 EHLO 主机名（默认 `localhost`） |
| `GATEWAY_<PROFILE>_SMTP_*` | 按 profile 覆盖对应 SMTP 参数 |
| `GATEWAY_SMTP_MAX_CONCURRENCY` | 最大并发 SMTP 会话数（默认 5） |
| `GATEWAY_SMTP_MAX_RETRIES` | 失败重试次数（默认 2） |
| `GATEWAY_SMTP_RETRY_BACKOFF` | 重试退避基数秒（默认 0.8） |

### 开发与测试

```bash
pip install pytest
pytest -v
```

测试覆盖：无 env 时的安全占位符回落、env 覆盖、named profile 同源继承、缺失凭据告警判定。

### 部署到 systemd（手动）

```bash
sudo mkdir -p /opt/zabbix-ai-email /etc/zabbix-ai-email
sudo cp src/gateway.py /opt/zabbix-ai-email/
sudo cp deploy/env.conf.example /etc/zabbix-ai-email/env.conf
# 编辑 env.conf 填入真实凭据
sudo chmod 600 /etc/zabbix-ai-email/env.conf
sudo cp deploy/gateway.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gateway.service
```

### 许可证

本项目基于 **GNU 通用公共许可证第 3 版（GPL-3.0）** 发布，完整条款见 [`LICENSE`](LICENSE) 文件。

你可以自由使用、修改、再分发本软件（含商业用途），但需满足以下条件：

- 衍生作品须以相同的 GPL-3.0 许可证发布；
- 须提供完整的对应源代码；
- 对原始源代码的修改须明确标注。

在法律允许的最大范围内，本软件**不提供任何担保**。权威条款以 [GNU GPL v3.0 官方页面](https://www.gnu.org/licenses/gpl-3.0.html) 为准。

[English](#english) | [简体中文](#简体中文)
