# mailgateway

SMTP 邮件网关 —— 一个可独立部署、随处复用的 HTTP→SMTP 投递服务。

对外暴露一个 HTTP `POST /send` 接口，接收 JSON 载荷（收件人/主题/HTML 正文），
内部调用原生 SMTP 发送邮件。设计用于把「消息生产方」（如监控告警 Webhook、脚本、
外部系统）与「真实邮箱投递」解耦，是任何需要发送 HTML 邮件的系统的通用基础设施。

## 特性

- **HTTP 统一入口**：只需 `POST /send`，无需关心 SSH/STMP 细节。
- **Token 鉴权**：支持 `Authorization: Bearer <token>`、裸 token、`?token=` 三种方式。
- **多 Profile**：内置 `local` / `remote` 两套发信账号，可按目标环境切换。
- **HTML 邮件**：正文按 `text/html` 发送，可直接拼 HTML 模板。
- **并发限流 & 自动重试**：信号量限制并发，失败按退避策略自动重试。
- **防伪成功**：严格检查 `smtplib.sendmail()` 返回值，任一收件人被拒即视为失败。
- **安全默认**：无环境变量时 SMTP 凭据回落 `UNSET_PLS_SET_ME` 占位符，不硬编码机密。

## 目录结构

```
mailgateway/
├── src/
│   └── gateway.py        # 核心程序（Python 标准库实现，零第三方依赖）
├── deploy/
│   ├── install.sh        # 一键安装脚本（创建用户/目录/service/env.conf）
│   ├── gateway.service   # systemd unit
│   └── env.conf.example  # 环境变量样例
├── tests/                # pytest 回归测试
├── AGENTS.md             # 协作约定（每次改动须 commit + 测试）
└── README.md
```

## 快速开始

### 1. 克隆并安装

```bash
git clone <your-git-url> mailgateway
cd mailgateway/deploy
sudo bash install.sh
```

安装脚本会：
- 创建目录 `/opt/zabbix-ai-email` 与 `/etc/zabbix-ai-email`；
- 创建低权限专用用户 `zabbix-ai-email`；
- 拷贝 `gateway.py` 与 systemd unit；
- 首次生成 `env.conf`；
- 注册并启动 `gateway.service`。

### 2. 配置凭据

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

### 3. 测试发送

```bash
curl -s -X POST http://127.0.0.1:8025/send \
  -H 'Authorization: Bearer 你的TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"to":"recipient@example.com","subject":"测试","body":"<b>你好</b>"}'
```

响应 `200` 即成功；日志位于 `journalctl -u gateway -f`。

## API 说明

### `POST /send`

请求体（JSON）：

| 字段    | 必填 | 类型   | 说明                                   |
|---------|------|--------|----------------------------------------|
| `to`    | 是   | string/list | 收件人。可传单个邮箱或邮箱数组    |
| `subject` | 是 | string | 邮件主题                            |
| `body`  | 是   | string | 邮件正文（按 `text/html` 发送）      |
| `profile` | 否 | string | 使用哪个发信账号，缺省 `local`     |

鉴权：请求头需含 `Authorization: Bearer <token>`（或裸 token / `?token=`）。

响应：

| HTTP 码 | 含义                       |
|---------|----------------------------|
| 200     | 邮件已成功投递至 MTA        |
| 400     | 缺少必填字段或 profile 非法 |
| 401     | Token 校验失败              |
| 404     | 非 `/send` 路径             |
| 502     | SMTP 发送失败（含重试后）   |

## 环境变量

| 变量                          | 说明                                |
|-------------------------------|-------------------------------------|
| `GATEWAY_HOST` / `GATEWAY_PORT` | HTTP 监听地址（默认 `127.0.0.1:8025`）|
| `GATEWAY_TOKEN`               | 调用方鉴权 Token                      |
| `GATEWAY_SMTP_HOST` / `_PORT`  | SMTP 服务器与端口（默认 465 SSL）     |
| `GATEWAY_SMTP_USER` / `_PASS`  | 发件账号与密码                        |
| `GATEWAY_SMTP_FROM`           | 显示发件人                            |
| `GATEWAY_SMTP_HELO`           | 握手 EHLO 主机名                       |
| `GATEWAY_<PROFILE>_SMTP_*`    | 按 profile 覆盖对应 SMTP 参数         |
| `GATEWAY_MAX_CONCURRENCY`     | 最大并发（默认 5）                     |
| `GATEWAY_MAX_RETRIES`         | 失败重试次数（默认 2）                 |
| `GATEWAY_RETRY_BACKOFF`       | 重试退避基数秒（默认 0.8）             |

## 开发与测试

```bash
pip install pytest
pytest -v
```

测试覆盖：无 env 时的安全占位符回落、env 覆盖、named profile 同源继承、缺失凭据告警判定。

## 部署到 systemd（手动）

```bash
sudo mkdir -p /opt/zabbix-ai-email /etc/zabbix-ai-email
sudo cp src/gateway.py /opt/zabbix-ai-email/
sudo cp deploy/env.conf.example /etc/zabbix-ai-email/env.conf
# 编辑 env.conf 填入真实凭据
sudo chmod 600 /etc/zabbix-ai-email/env.conf
sudo cp deploy/gateway.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now gateway.service
```
