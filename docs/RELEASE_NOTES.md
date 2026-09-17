# mailgatewy v1.0.3 — Zabbix Alert Email HTTP→SMTP Gateway

[English](#english) | [简体中文](#简体中文)

---

## English

[English](#english) | [简体中文](#简体中文)

> **Latest release**: `v1.0.3`
>
> Repository: `git@github.com:shourenli/zabbix-mailgatewy-webhook.git` (private)
> Tag: `v1.0.3` → points to `main` (the same 14-file set as `v1.0.2`, documentation update only)
> Previous: `v1.0.2` → `f09f595`; `v1.0.1` → `22ede87`; `v1.0.0` → `5b0f3a9` (11 files)
> Release line: `main`

### Overview

`mailgatewy` is a standalone, reusable **HTTP→SMTP mail delivery gateway**. It exposes a single HTTP entry point `POST /send`, accepts JSON (`to / subject / body / profile`), and performs real mailbox delivery internally over native `smtplib.SMTP_SSL`.

Core value: **decoupling message producers from actual mailbox delivery**. Zabbix Webhooks, shell scripts, cron jobs — any caller that can issue an HTTP request — no longer need to care about SMTP credentials or protocol details; they simply call the gateway to send mail. This consolidates the "sending account / password / server" from every producer into a single place: the gateway.

### Technical Basis & Compatibility

This solution originates from the real production need to **deliver Zabbix alert emails**, and **it is built and validated on both LTS versions, Zabbix 6.0 LTS and Zabbix 7.0 LTS**.

| Zabbix version | Call path | Reference config |
|---|---|---|
| **Zabbix 6.0 LTS** | Remote Zabbix calls the gateway across hosts: `http://<gateway-host>:8025/send` | `yaml/zbx6_remote_aimedia.yaml` (`zabbix_export.version: '6.0'`) |
| **Zabbix 7.0 LTS** | Local Zabbix calls the gateway via loopback: `http://127.0.0.1:8025/send` | `yaml/zbx7_local_aimedia.yaml` (`zabbix_export.version: '7.0'`) |

Both reference configs are Zabbix **Media (`type: WEBHOOK`) export files** that can be imported directly under *Administration → Media types → Import*; they contain:

- A webhook media script — first call an LLM (GLM) to generate a plain-language "digest" of the alert, then assemble the HTML email body together with the alert fields, and finally POST it to this gateway;
- Title/body templates **aligned field-by-field with the existing email media**:
  - Problem: `【故障据点】: {INVENTORY.TAG}`
  - Recovery: `【恢复通知】【据点名称】: {INVENTORY.TAG}`
- All credentials are given as `CHANGE_ME_*` placeholders.

> The gateway itself **does not depend on Zabbix**: any system that can issue an HTTP request (shell, CI, business apps) can reuse it; Zabbix 6.0 / 7.0 LTS is its primary caller and the scenario in which this release completed real delivery verification.

### Key Features

- **Unified HTTP entry point**: a single `POST /send` endpoint, `application/json`, with fields `to / subject / body / profile`.
- **Three Token auth forms**: `Authorization: Bearer <token>`, a bare token header, or the `?token=<token>` query parameter.
- **Multiple profile sending accounts**: built-in `local` / `remote` profiles let different callers use different sending accounts; overridden by `GATEWAY_<PROFILE>_SMTP_*`, falling back to the top-level defaults when not overridden.
- **HTML email support**: `body` can carry HTML directly and is passed through as-is.
- **Concurrency limiting + automatic retry**: `threading.BoundedSemaphore` caps concurrent SMTP sessions to avoid a burst overwhelming the mail server; failures are retried with a backoff base.
- **No false success**: the `smtplib.sendmail()` return value is strictly checked — the presence of any refused recipient is treated as a failure, eliminating the silent false positive of "looks sent, actually refused".
- **Recipient normalization**: `to` accepts both `string` and `list`. Zabbix 7 expands `{ALERT.SENDTO}` into an **array** on a real alert trigger, and the gateway normalizes it internally, avoiding the "test button works but real alerts are not received" discrepancy.
- **Secure defaults, zero hard-coded secrets**: with no environment variables, SMTP credentials fall back to `UNSET_PLS_SET_ME` and the gateway token defaults to `CHANGE_ME_LOCAL_TOKEN`; the source, config sample, and reference YAML contain no real internal IPs or company names.

### Version History

| Version | Summary |
|---|---|
| **v1.0.3** (this release) | **License declaration only** — added `### License` / `### 许可证` sections to the README and the release notes (GPL-3.0, obligations, warranty disclaimer). **`src/` and `tests/` are byte-for-byte identical to v1.0.0/v1.0.1/v1.0.2 (zero code change).** |
| v1.0.2 | Documentation internationalization only — bilingual English/Chinese README and release notes. |
| v1.0.1 | Documentation and engineering standardization only; program logic identical to v1.0.0 (`src/` and `tests/` byte-for-byte identical). |
| v1.0.0 | First stable release. |

#### v1.0.3 (this release)

**Documentation only; program logic is identical to `v1.0.2` (`src/` and `tests/` are byte-for-byte identical to `v1.0.0`/`v1.0.1`/`v1.0.2`).**

The `LICENSE` file (GPL-3.0) had been in the repository since `v1.0.1`, but neither the README nor the release notes ever **stated** it — the only occurrence of "GPL-3.0" was a comment inside the directory tree (`├── LICENSE  # GPL-3.0`), so a reader could not tell what license the project uses.

| Change | Description |
|---|---|
| Added `### License` | At the end of the English region (after "Deploying to systemd"): GPL-3.0, the three obligations (derivative works under the same license / complete corresponding source available / modifications clearly marked), a no-warranty disclaimer, and links to the local `LICENSE` file and the official GNU page. |
| Added `### 许可证` | The Chinese counterpart, structurally symmetrical to the English section. |
| Release notes kept in sync | `docs/RELEASE_NOTES.md` gained the same license sections in both language regions, so the two documents agree. |
| Zero code change | `src/gateway.py` and everything under `tests/` are byte-for-byte identical to `v1.0.0`/`v1.0.1`/`v1.0.2`. |
| LF and anchors unchanged | The CR byte count is 0 in both files; language-switch links and their anchor targets are untouched. |

#### v1.0.2

**Documentation internationalization only; program logic is identical to `v1.0.1` (`src/` and `tests/` are byte-for-byte identical to `v1.0.0`/`v1.0.1`).**

| Change | Description |
|---|---|
| README bilingualized | Rewritten as a **single-file bilingual** document (English first, Chinese after), with in-page language links at the top; technical content is fully equivalent between the two languages. |
| Release notes bilingualized | `docs/RELEASE_NOTES.md` upgraded to bilingual `v1.0.2`, with the version history and known issues updated. |
| Zero code change | `src/gateway.py` and everything under `tests/` are byte-for-byte identical to `v1.0.0`/`v1.0.1`. |

#### v1.0.1

**Documentation and engineering standardization only; program logic is identical to `v1.0.0` (`src/` and `tests/` are byte-for-byte identical).**

| Change | Description |
|---|---|
| Added `.gitattributes` | `* text=auto eol=lf` (scripts/config explicitly `eol=lf`, binaries explicitly `binary`). Fixes the Windows `core.autocrlf=true` behavior that turned archives into CRLF and made `deploy/install.sh` report `bad interpreter` on Linux. |
| README compatibility | States that the solution is built and validated on **Zabbix 6.0 LTS and 7.0 LTS**; adds an "Integrating with Zabbix" section (including the reminder that user media must be Enabled). |
| README fixes | Fixed environment variable names (`GATEWAY_SMTP_MAX_CONCURRENCY` / `_MAX_RETRIES` / `_RETRY_BACKOFF`), completed the directory tree, and fixed a heading typo. |
| Restored `LICENSE` | GPL-3.0 (chosen at repository creation; had been lost to a historical overwrite). |
| Release note shipped with the release | The `v1.0.0` tag did not include `docs/`; from this release onward the release note is distributed with the tag. |

> **This release aligns the tag content with `main`**: the `v1.0.0` tag stopped at 11 files while `main` had advanced to 14 files; from `v1.0.1` onward the two are consistent.

#### v1.0.0

First stable release.

- Generic HTTP→SMTP gateway core (auth / multi-profile / throttling / retry / no-false-success / recipient normalization);
- One-shot deployment script and systemd unit;
- Reference Media (Webhook) configs for both Zabbix **6.0 LTS and 7.0 LTS**, with aligned title/body templates;
- Credential security test suite (`pytest` fully green);
- A clean, desensitized git baseline (fresh history after the repository was rebuilt, with no residual old objects).

### Directory Layout

```text
mailgatewy/
├── src/gateway.py                # Core implementation: HTTP service + SMTP delivery orchestration
├── deploy/
│   ├── install.sh                # One-shot install (create user/dirs/install systemd unit)
│   ├── gateway.service           # systemd unit
│   └── env.conf.example          # Environment variable sample (with common GATEWAY_* entries)
├── yaml/
│   ├── zbx7_local_aimedia.yaml   # Reference: Zabbix 7.0 LTS Media export (local call)
│   └── zbx6_remote_aimedia.yaml  # Reference: Zabbix 6.0 LTS Media export (remote call)
├── tests/
│   ├── conftest.py
│   └── test_gateway_creds.py     # Covers placeholder fallback / env override / profile inheritance, etc.
├── docs/RELEASE_NOTES.md         # This file
├── AGENTS.md                     # Collaboration conventions (changes must be committed + tested)
├── LICENSE                       # GPL-3.0
├── .gitattributes                # Enforce LF newlines so archives work on Linux
└── .gitignore
```

### Quick Start

```bash
# 1) Clone (use main or v1.0.3 for the latest documentation)
git clone --branch v1.0.3 git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy

# 2) One-shot install (creates user zabbix-ai-email, dirs /opt/zabbix-ai-email, /etc/zabbix-ai-email)
sudo ./deploy/install.sh

# 3) Configure environment variables
# run from the repository root
sudo cp deploy/env.conf.example /etc/zabbix-ai-email/env.conf
# edit env.conf and set at least:
#   GATEWAY_TOKEN=<your-gateway-token>
#   GATEWAY_SMTP_USER / GATEWAY_SMTP_PASS / GATEWAY_SMTP_FROM

# 4) Start the service
sudo systemctl enable --now gateway

# 5) Test
curl -X POST http://127.0.0.1:8025/send \
  -H "Authorization: Bearer <GATEWAY_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"to":"you@example.com","subject":"test","body":"<h1>Hello</h1>","profile":"local"}'
```

### API

#### `POST /send`

| Field | Type | Required | Description |
|---|---|---|---|
| `to` | string / list | yes | Recipient email (supports a list of recipients) |
| `subject` | string | yes | Email subject |
| `body` | string | yes | Email body (HTML supported) |
| `profile` | string | no | Sending account profile; uses the default when omitted |

**Response codes**

| Status | Meaning |
|---|---|
| 200 | Delivered successfully (all recipients accepted) |
| 400 | Missing/invalid parameter (missing `to/subject/body` or malformed) |
| 401 | Token authentication failed |
| 404 | Path not found |
| 502 | SMTP delivery failed (including refused recipients) |

### Configuration (Environment Variables)

| Variable | Description |
|---|---|
| `GATEWAY_HOST` | Listen address (default `127.0.0.1`) |
| `GATEWAY_PORT` | Listen port (default `8025`) |
| `GATEWAY_TOKEN` | Authentication token (default `CHANGE_ME_LOCAL_TOKEN`) |
| `GATEWAY_SMTP_*` | Default sending account (`HOST` / `PORT` / `USER` / `PASS` / `FROM` / `HELO`) |
| `GATEWAY_<PROFILE>_SMTP_*` | Per-profile overrides, e.g. `GATEWAY_REMOTE_SMTP_USER` |
| `GATEWAY_SMTP_MAX_CONCURRENCY` | Max concurrent SMTP sessions (default 5) |
| `GATEWAY_SMTP_MAX_RETRIES` | Number of retries after a failure (default 2) |
| `GATEWAY_SMTP_RETRY_BACKOFF` | Retry backoff base in seconds (default 0.8) |

### Development & Testing

```bash
pip install pytest
pytest -v
```

Test coverage: placeholder fallback when no environment variables are set, `GATEWAY_*` environment variable overrides, `GATEWAY_<PROFILE>_*` inheritance of top-level defaults, and detection of missing-credential warnings.

### Known Issues

- **Newlines**: the repository already standardizes on LF via `.gitattributes`. If your working copy is from an early version (`v1.0.0` and earlier), a Windows checkout may carry CRLF; in that case, when you make an archive yourself, add `-c core.autocrlf=false -c core.eol=lf`, otherwise `install.sh` will report `bad interpreter` on Linux.
- **User media status**: in Zabbix, when a "media type" or a "user → media" is disabled (`active=0`), no email will be sent, and Zabbix does not necessarily report an error. Check this first when troubleshooting.
- **Credential rotation**: if the SMTP password / gateway token / LLM API key were ever used in production with historical versions sharing the same origin, rotating them is recommended.

### Security & Desensitization Notes

- All credentials across the repository are **placeholders** (`CHANGE_ME_*` / `UNSET_PLS_SET_ME`); the source, config samples, and reference YAML contain no real SMTP password, token, internal IP, or company name.
- Before release, the **entire git history** was rewritten in three layers (file content / commit message / author identity) so that no real internal IP or company name remains in the reachable history.
- For **unreachable old objects** that GitHub's servers could still fetch by old SHA after a force-push, the link was fully severed by **deleting the original repository and recreating it under the same name** — after the rebuild, fetching by the old SHA returns `not our ref`, and the old content is no longer retrievable.

### License

This project is released under the **GNU General Public License v3.0 (GPL-3.0)**. The full text is in the [`LICENSE`](LICENSE) file.

- Derivative works must be distributed under the same GPL-3.0 license.
- The complete corresponding source code must be made available.
- The software is provided **without any warranty**, to the extent permitted by law.

See the [official GNU GPL v3.0 page](https://www.gnu.org/licenses/gpl-3.0.html) for the authoritative terms.

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

[English](#english) | [简体中文](#简体中文)

> **最新发布（latest）**：`v1.0.3`
>
> 仓库：`git@github.com:shourenli/zabbix-mailgatewy-webhook.git`（私有）
> 标签：`v1.0.3` → 指向 `main`（与 `v1.0.2` 相同的 14 个文件，仅文档更新）
> 上一版：`v1.0.2` → `f09f595`；`v1.0.1` → `22ede87`；`v1.0.0` → `5b0f3a9`（11 个文件）
> 发布线：`main`

### 简介

`mailgatewy` 是一个可独立部署、随处复用的 **HTTP→SMTP 邮件投递网关**。它对外暴露统一的 HTTP 入口 `POST /send`，接收 JSON（`to / subject / body / profile`），内部通过原生 `smtplib.SMTP_SSL` 完成真实邮箱投递。

核心价值：**解耦消息生产方与真实邮箱投递**。Zabbix Webhook、Shell 脚本、定时任务等任何能发 HTTP 的调用方，都不再需要关心 SMTP 凭据与协议细节，只需调用网关即可发信，从而把「发信账号 / 密码 / 服务器」从各生产方收拢到网关一处统一管理。

### 技术基础与兼容性

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

### 核心特性

- **HTTP 统一入口**：单一 `POST /send` 端点，`application/json`，字段 `to / subject / body / profile`。
- **三种 Token 鉴权**：`Authorization: Bearer <token>`、裸 token 头、`?token=<token>` 查询参数均可。
- **多 Profile 发信账号**：内置 `local` / `remote` 两套 Profile，允许不同调用方走不同发信账号；由 `GATEWAY_<PROFILE>_SMTP_*` 覆盖，未覆盖时回落顶层默认值。
- **HTML 邮件支持**：`body` 可直接传 HTML，网关原样透传。
- **并发限流 + 自动重试**：`threading.BoundedSemaphore` 限制并发 SMTP 会话，避免突发打爆邮箱服务器；失败按退避基数自动重试。
- **防伪成功判定**：严格检查 `smtplib.sendmail()` 返回值 —— 只要存在被拒绝的收件人即判定失败，杜绝「看似发送成功、实际被拒」的静默误报。
- **多收件人归一化**：`to` 同时接受 `string` 与 `list`。Zabbix 7 在真实告警触发时会把 `{ALERT.SENDTO}` 展开为**数组**，网关内部统一归一化，避免「测试按钮能发、真实告警收不到」的差异。
- **安全默认，零硬编码机密**：无环境变量时 SMTP 凭据回落 `UNSET_PLS_SET_ME`、网关 Token 默认 `CHANGE_ME_LOCAL_TOKEN`；源码 / 配置示例 / 参考 YAML 均不含任何真实内网 IP 或公司实名。

### 版本历史

| 版本 | 摘要 |
|---|---|
| **v1.0.3**（本版） | **仅补许可证声明** —— README 与 release note 新增 `### License` / `### 许可证` 章节（GPL-3.0、义务条款、免责声明）。**`src/` 与 `tests/` 与 v1.0.0/v1.0.1/v1.0.2 逐字节相同（代码零改动）。** |
| v1.0.2 | 仅文档国际化 —— README 与 release note 中英双语。 |
| v1.0.1 | 仅文档与工程规范化；程序逻辑与 v1.0.0 完全一致（`src/` 与 `tests/` 逐字节相同）。 |
| v1.0.0 | 首次正式发布（stable）。 |

#### v1.0.3（本版）

**仅文档变更，程序逻辑与 `v1.0.2` 完全一致（`src/` 与 `tests/` 与 `v1.0.0`/`v1.0.1`/`v1.0.2` 逐字节相同）。**

`LICENSE`（GPL-3.0）自 `v1.0.1` 起就已在仓库中，但 README 与 release note **从未真正声明**过 —— "GPL-3.0" 唯一出现的地方是目录树里的注释 `├── LICENSE  # GPL-3.0`，读者无法从文档看出本项目采用何种许可证。

| 变更 | 说明 |
|---|---|
| 新增 `### License` 章节 | 英文区末尾（systemd 部署段之后）新增：GPL-3.0、三条义务（衍生作品同许可 / 提供完整对应源码 / 标注修改）、免责声明，并链接本地 `LICENSE` 文件与 GNU 官方页面 |
| 新增 `### 许可证` 章节 | 中文区对应章节，与英文区结构对称 |
| release note 同步 | 中英两区同样补许可证章节，与 README 口径一致 |
| 代码零改动 | `src/gateway.py` 与 `tests/` 下全部文件与 `v1.0.0`/`v1.0.1`/`v1.0.2` 逐字节相同 |
| 换行与锚点不变 | 两文件 CR 字节数均为 0；语言切换链接与锚点目标未改动 |

#### v1.0.2

**仅文档国际化，程序逻辑与 `v1.0.1` 完全一致（`src/` 与 `tests/` 与 `v1.0.0`/`v1.0.1` 逐字节相同）。**

| 变更 | 说明 |
|---|---|
| README 双语化 | 改写为**单文件双语**（英文在前、中文在后），顶部带语言跳转；中英技术内容完全等价。 |
| release note 双语化 | `docs/RELEASE_NOTES.md` 升级为双语 `v1.0.2`，同步更新版本历史与已知事项。 |
| 代码零改动 | `src/gateway.py` 与 `tests/` 下全部文件与 `v1.0.0`/`v1.0.1` 逐字节相同。 |

#### v1.0.1

**仅文档与工程规范化，程序逻辑与 `v1.0.0` 完全一致（`src/` 与 `tests/` 逐字节相同）。**

| 变更 | 说明 |
|---|---|
| 新增 `.gitattributes` | `* text=auto eol=lf`（脚本/配置显式 `eol=lf`，二进制显式 `binary`）。根治 Windows 下 `core.autocrlf=true` 把归档包转成 CRLF、导致 `deploy/install.sh` 在 Linux 上报 `bad interpreter` 的问题 |
| README 补充兼容性 | 明确本方案构建并验证于 **Zabbix 6.0 LTS 与 7.0 LTS**；新增「接入 Zabbix」步骤（含用户媒介必须 Enabled 的提醒） |
| README 修正 | 修正环境变量名（`GATEWAY_SMTP_MAX_CONCURRENCY` / `_MAX_RETRIES` / `_RETRY_BACKOFF`）、补全目录树、修正标题拼写 |
| 补回 `LICENSE` | GPL-3.0（建库时选定，曾因历史覆盖而丢失） |
| release note 随版发布 | `v1.0.0` 的 tag 中不含 `docs/`，本版起 release note 随 tag 一并分发 |

> **本版将 tag 内容与 `main` 对齐**：`v1.0.0` 的 tag 停在 11 个文件，`main` 已前进到 14 个文件；`v1.0.1` 起两者一致。

#### v1.0.0

首次正式发布（stable）。

- 通用 HTTP→SMTP 网关核心实现（鉴权 / 多 Profile / 限流 / 重试 / 防伪成功 / 多收件人归一化）；
- 一键部署脚本与 systemd 单元；
- Zabbix **6.0 LTS 与 7.0 LTS** 两类 Media（Webhook）参考配置，含标题/正文模板对齐；
- 凭据安全测试套件（`pytest` 全绿）；
- 完成脱敏的干净 git 基线（仓库重建后全新历史，无残留旧对象）。

### 目录结构

```text
mailgatewy/
├── src/gateway.py                # 核心实现：HTTP 服务 + SMTP 投递编排
├── deploy/
│   ├── install.sh                # 一键安装（建用户/建目录/装 systemd 单元）
│   ├── gateway.service           # systemd 单元
│   └── env.conf.example          # 环境变量示例（含常用 GATEWAY_* 项）
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

### 快速开始

```bash
# 1) 克隆（要最新文档请用 main 或 v1.0.3）
git clone --branch v1.0.3 git@github.com:shourenli/zabbix-mailgatewy-webhook.git mailgatewy
cd mailgatewy

# 2) 一键安装（创建用户 zabbix-ai-email、目录 /opt/zabbix-ai-email、/etc/zabbix-ai-email）
sudo ./deploy/install.sh

# 3) 配置环境变量
# 在仓库根目录执行
sudo cp deploy/env.conf.example /etc/zabbix-ai-email/env.conf
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

### API

#### `POST /send`

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

### 配置（环境变量）

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

### 开发与测试

```bash
pip install pytest
pytest -v
```

测试覆盖：无环境变量时占位符回落、`GATEWAY_*` 环境变量覆盖、`GATEWAY_<PROFILE>_*` 继承顶层默认、缺失凭据告警判定。

### 已知事项

- **换行符**：仓库已通过 `.gitattributes` 统一为 LF。若你的工作副本是早期版本（`v1.0.0` 及以前），Windows 下 checkout 可能带 CRLF，此时自行打归档包需加 `-c core.autocrlf=false -c core.eol=lf`，否则 `install.sh` 在 Linux 上会报 `bad interpreter`。
- **用户媒介状态**：Zabbix 中「媒介类型」或「用户 → 媒介」被禁用（`active=0`）时不会有任何邮件外发，且 Zabbix 侧不一定报错。排障时优先检查该项。
- **凭据轮换**：若曾在生产环境与历史版本同源使用过 SMTP 密码 / 网关 Token / 大模型 API Key，建议轮换。

### 安全与脱敏说明

- 全仓库凭据一律**占位符化**（`CHANGE_ME_*` / `UNSET_PLS_SET_ME`）；源码、配置示例、参考 YAML 均无任何真实 SMTP 密码、Token、内网 IP 或公司实名。
- 发布前已对 **git 完整历史**做三层脱敏改写（文件内容 / commit message / 作者身份），使可达历史中不再残留真实内网 IP 或公司实名。
- 对于强推后 GitHub 服务端仍可凭旧 SHA 取回的**不可达旧对象**，已通过**删除原仓库并同名重建**彻底切断 —— 重建后按旧 SHA 取回返回 `not our ref`，旧内容不可再获取。

### 许可证

本项目基于 **GNU 通用公共许可证第 3 版（GPL-3.0）** 发布，完整条款见 [`LICENSE`](LICENSE) 文件。

- 衍生作品须以相同的 GPL-3.0 许可证发布。
- 须提供完整的对应源代码。
- 在法律允许的最大范围内，本软件**不提供任何担保**。

权威条款以 [GNU GPL v3.0 官方页面](https://www.gnu.org/licenses/gpl-3.0.html) 为准。

[English](#english) | [简体中文](#简体中文)

---

*mailgatewy v1.0.3 — 2026-09-17*
