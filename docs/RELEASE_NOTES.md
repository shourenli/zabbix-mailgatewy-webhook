# mailgatewy v1.0.0 — 通用 HTTP→SMTP 邮件网关

> 首次正式发布（stable）。本 release note 适用于 commit `1745852`。
>
> 远程仓库：`git@github.com:shourenli/zabbix-mailgatewy-webhook.git`（`main` 分支；原仓库名 `mailgatewy`，后重命名）

---

## 简介

`mailgatewy` 是一个可独立部署、随处复用的 **HTTP→SMTP 邮件投递网关**。它对外暴露一个统一的 HTTP 入口 `POST /send`，接收 JSON（`to / subject / body / profile`），内部通过原生 `smtplib.SMTP_SSL` 完成真实邮箱投递。

核心价值：**解耦消息生产方与真实邮箱投递**。Zabbix Webhook、Shell 脚本、定时任务等任何能发 HTTP 的调用方，都不再需要关心 SMTP 凭据与协议细节，只需调用网关即可发信，从而把"发信账号/密码/服务器"从各生产方中收拢到网关一处统一管理。

---

## 核心特性

- **HTTP 统一入口**：单一 `POST /send` 端点，支持 `application/json`，字段 `to / subject / body / profile`。
- **三种 Token 鉴权**：`Authorization: Bearer <token>`、裸 token 头、`?token=<token>` 查询参数均可。
- **多 Profile 发信账号**：内置 `local` / `remote` 两套 Profile，允许不同调用方走不同发信账号；由 `GATEWAY_<PROFILE>_SMTP_*` 环境变量覆盖，未覆盖时回落顶层默认值。
- **HTML 邮件支持**：`body` 可直接传 HTML，网关原样透传。
- **并发限流 + 自动重试**：`threading.BoundedSemaphore` 限制并发 SMTP 会话，避免突发打爆邮箱服务器；失败按指数退避基数自动重试。
- **防伪成功判定**：严格检查 `smtplib.sendmail()` 返回值——只要存在被拒绝的收件人即判定失败，杜绝"看似发送成功、实际被拒"的静默误报。
- **安全默认，零硬编码机密**：无环境变量时，SMTP 凭据回落 `UNSET_PLS_SET_ME` 占位符、网关 Token 默认 `CHANGE_ME_LOCAL_TOKEN`，源码 / 配置示例 / 参考 YAML 均不含任何真实内网 IP 或公司实名。

---

## 目录结构

```
mailgatewy/
├── src/gateway.py            # 核心实现：HTTP 服务 + SMTP 投递编排
├── deploy/
│   ├── install.sh            # 一键安装脚本（建用户/建目录/装 systemd 单元）
│   ├── gateway.service       # systemd 单元
│   └── env.conf.example      # 环境变量示例（含全部 GATEWAY_* 项）
├── yaml/
│   ├── zbx7_local_aimedia.yaml   # 参考：Zabbix 7.0 本地 Media 导出配置
│   └── zbx6_remote_aimedia.yaml  # 参考：Zabbix 6.0 远端 Media 导出配置
├── tests/
│   ├── conftest.py
│   └── test_gateway_creds.py # 覆盖占位符回落/env 覆盖/profile 继承等
├── README.md
├── AGENTS.md                 # 协作约定（改动必 commit + 更新测试）
└── .gitignore
```

---

## 快速开始

```bash
# 1) 克隆
git clone git@github.com:shourenli/zabbix-mailgatewy-webhook.git
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
| `GATEWAY_SMTP_*` | 默认发信账号（HOST/PORT/USER/PASS/FROM/SSL…） |
| `GATEWAY_<PROFILE>_SMTP_*` | 各 Profile 覆盖项，如 `GATEWAY_REMOTE_SMTP_USER` |
| `GATEWAY_MAX_CONCURRENCY` | 最大并发 SMTP 会话数 |
| `GATEWAY_RETRIES` | 失败重试次数 |
| `GATEWAY_RETRY_BACKOFF` | 重试退避基数（秒） |

---

## 开发与测试

```bash
pip install pytest
pytest -v
```

测试覆盖：无环境变量时占位符回落、`GATEWAY_*` 环境变量覆盖、`GATEWAY_<PROFILE>_*` 继承顶层默认、缺失凭据告警。

---

## 安全与脱敏说明

- 全仓库凭据一律**占位符化**（`CHANGE_ME_*` / `UNSET_PLS_SET_ME`），源码、配置示例、参考 YAML 无任何真实 SMTP 密码、Token、内网 IP 或公司实名。
- 本次发布前已对 **git 完整历史** 做脱敏改写（tree / commit message / 作者身份三层过滤），全部 commit 均已清理，历史 blob 中不再残留任何真实内网 IP 或公司实名。
- 适合公开或跨环境复用；若在生产使用过同源凭据，建议轮换高价值凭证。

---

## 变更范围（相对仓库初始化）

本 v1.0.0 为首次正式发布快照，已包含以下固化成果：

- 通用 HTTP→SMTP 网关核心实现（鉴权 / 多 Profile / 限流 / 重试 / 防伪成功）；
- 一键部署脚本与 systemd 单元；
- Zabbix 7.0 / 6.0 两类 Media 参考配置（凭据占位符化）；
- 凭据安全测试套件；
- 全历史脱敏改写后的干净 git 基线（最新 commit `1745852`）。

---

*mailgatewy v1.0.0 — 2026-09-17*