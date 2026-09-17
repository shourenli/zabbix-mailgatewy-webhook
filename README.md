# mailgatewy

SMTP 邮件网关 —— 一个可独立部署、随处复用的 HTTP→SMTP 投递服务。

对外暴露一个 HTTP `POST /send` 接口，接收 JSON 载荷（收件人/主题/HTML 正文），
内部调用原生 SMTP 发送邮件。设计用于把「消息生产方」（如监控告警 Webhook、脚本、
外部系统）与「真实邮箱投递」解耦，是任何需要发送 HTML 邮件的系统的通用基础设施。

## 适用场景与兼容性

本项目源自 **Zabbix 告警邮件投递**的实际需求，**解决方案构建并验证于 Zabbix 6.0 LTS 与 Zabbix 7.0 LTS**：

| Zabbix 版本 | 调用方式 | 参考配置 |
|---|---|---|
| **Zabbix 6.0 LTS** | 远端 Zabbix 跨主机调用网关：`http://<网关地址>:8025/send` | `yaml/zbx6_remote_aimedia.yaml` |
| **Zabbix 7.0 LTS** | 本机 Zabbix 走回环调用网关：`http://127.0.0.1:8025/send` | `yaml/zbx7_local_aimedia.yaml` |

两份参考配置均为 Zabbix **Media（Webhook 媒介类型）导出文件**，内含：

- Webhook 媒介脚本：先调用大模型生成告警的「白话解读」，再与告警字段一起拼装 HTML 邮件体；
- 与既有邮件媒介**对齐的标题/正文模板**（告警 `【故障据点】: {INVENTORY.TAG}`、恢复 `【恢复通知】【据点名称】: {INVENTORY.TAG}`）；
- 全部凭据以 `CHANGE_ME_*` 占位符给出，导入 Zabbix 后需自行替换。

> 网关本身**不依赖 Zabbix**。任何能发起 HTTP 请求的系统（Shell、CI、业务应用）都可复用；
> Zabbix 6.0 / 7.0 LTS 只是它最主要的调用方。

## 特性

- **HTTP 统一入口**：只需 `POST /send`，无需关心 SSH/SMTP 细节。
- **Token 鉴权**：支持 `Authorization: Bearer <token>`、裸 token、`?token=` 三种方式。
- **多 Profile**：内置 `local` / `remote` 两套发信账号，可按目标环境切换。
- **HTML 邮件**：正文按 `text/html` 发送，可直接拼 HTML 模板。
- **并发限流 & 自动重试**：信号量限制并发，失败按退避策略自动重试。
- **防伪成功**：严格检查 `smtplib.sendmail()` 返回值，任一收件人被拒即视为失败。
- **安全默认**：无环境变量时 SMTP 凭据回落 `UNSET_PLS_SET_ME` 占位符，不硬编码机密。

## 目录结构

```
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

## 快速开始

### 1. 克隆并安装

```bash
git clone git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy/deploy
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

## 接入 Zabbix

1. 按上表选择对应版本的参考配置，在 Zabbix 中导入 Media type（*Administration → Media types → Import*）；
2. 替换配置中的 `CHANGE_ME_*` 占位符（网关地址、Token、大模型 API Key 等）；
3. 给用户绑定该 Media，并**将其状态置为 Enabled**（`active=1`）——媒介或用户媒介被禁用时不会有任何邮件外发。

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
| `GATEWAY_SMTP_HELO`           | 握手 EHLO 主机名（默认 `localhost`）  |
| `GATEWAY_<PROFILE>_SMTP_*`    | 按 profile 覆盖对应 SMTP 参数         |
| `GATEWAY_SMTP_MAX_CONCURRENCY` | 最大并发 SMTP 会话数（默认 5）        |
| `GATEWAY_SMTP_MAX_RETRIES`    | 失败重试次数（默认 2）                 |
| `GATEWAY_SMTP_RETRY_BACKOFF`  | 重试退避基数秒（默认 0.8）             |

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
