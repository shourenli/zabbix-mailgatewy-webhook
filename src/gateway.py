#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Zabbix AI 白话解读 - SMTP 邮件网关服务（多 Profile 版）
=========================================================
角色：桥接 Webhook (仅支持 HTTP) 与原 Email 媒介 (原生 SMTP)。
Zabbix Webhook 无法原生做 SMTP 认证发信，因此本服务在本机监听 HTTP POST，
接收 JSON(含收件人/主题/正文)，用指定邮箱账号帮发信。支持"本地 / 远端"
多个 Zabbix 各自使用独立发件人账号(profile)。

特性：
  1. 多 Profile：HTTP body 可带 `profile` 字段选择发信账号
     (默认 local)，兼容不带 profile 的旧调用。
  2. Token 认证：所有请求必须携带 `authorization` 头或查询参数 token。
  3. 失败给出 JSON 错误与 HTTP 状态码，便于 Webhook 脚本判断是否降级。

Profile 说明 (env.conf 中的 GATEWAY_<PROFILE>_SMTP_* 系列变量)：
  内置两个 profile：local(本地 CHANGE_ME_HOST) 与 remote(远端 Zabbix)。
  每个 profile 由 5 个变量定义，缺省回落到顶层默认(local)值：
    GATEWAY_<PROFILE>_SMTP_HOST / _PORT / _USER / _PASS / _FROM / _HELO

部署：
  sudo cp src/gateway.py /opt/zabbix-ai-email/gateway.py
  sudo cp deploy/gateway.service /etc/systemd/system/gateway.service
  sudo systemctl daemon-reload
  sudo systemctl enable --now gateway
"""

import json
import logging
import os
import smtplib
import sys
import threading
import time
from email.header import Header
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate
from uuid import uuid4
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# 配置（优先读环境变量，便于用 systemd EnvironmentFile 管理）
# ---------------------------------------------------------------------------
HOST = os.environ.get("GATEWAY_HOST", "127.0.0.1")
PORT = int(os.environ.get("GATEWAY_PORT", "8025"))

# 本地网关鉴权 Token。强烈建议用环境变量覆盖默认值。
GATEWAY_TOKEN = os.environ.get("GATEWAY_TOKEN", "CHANGE_ME_LOCAL_TOKEN")

# 单账号并发 SMTP 连接上限（防告警风暴瞬间开太多连接触发服务端限流/封禁）。
SMTP_MAX_CONCURRENCY = int(os.environ.get("GATEWAY_SMTP_MAX_CONCURRENCY", "5"))
# 发送失败后的自动重试次数（不含首次尝试）。瞬时连接抖动/超时导致的丢信可自动补发。
SMTP_MAX_RETRIES = int(os.environ.get("GATEWAY_SMTP_MAX_RETRIES", "2"))
# 重试前等待时长(秒)，给 SMTP/TCP 抖动留缓冲。
SMTP_RETRY_BACKOFF = float(os.environ.get("GATEWAY_SMTP_RETRY_BACKOFF", "0.8"))
# 全局信号量：限制同时进行的 SMTP 会话数。线程安全，跨所有 HTTP 请求线程共享。
_SMTP_SEM = threading.BoundedSemaphore(SMTP_MAX_CONCURRENCY)


# ---------------------------------------------------------------------------
# 多 Profile SMTP 配置
# ---------------------------------------------------------------------------
# profile 名称->SMTP 配置。每个 profile 用独立前缀的环境变量覆盖，缺省落到
# 顶层 GATEWAY_SMTP_*（即 local 默认值），保证旧配置零改动即兼容。
# 预置两个 profile：local(本地) / remote(远端外部 Zabbix)。
PROFILE_NAMES = ("local", "remote")


# SMTP 凭据安全默认：用户/密码/发件人不落默认值（避免机密硬编码进代码）。
# 必须由环境变量 GATEWAY_SMTP_USER/PASS/FROM（或 profile 前缀版本）显式提供，
# 缺省回落安全占位符，启动时若仍是占位符会告警提示配置缺失。
_PLACEHOLDER_CRED = "UNSET_PLS_SET_ME"


def _load_smtp_defaults():
    return {
        "host": os.environ.get("GATEWAY_SMTP_HOST", "smtp.qiye.aliyun.com"),
        "port": int(os.environ.get("GATEWAY_SMTP_PORT", "465")),
        "user": os.environ.get("GATEWAY_SMTP_USER", _PLACEHOLDER_CRED),
        "pass": os.environ.get("GATEWAY_SMTP_PASS", _PLACEHOLDER_CRED),
        "from": os.environ.get("GATEWAY_SMTP_FROM", _PLACEHOLDER_CRED),
        "helo": os.environ.get("GATEWAY_SMTP_HELO", "localhost"),
    }


_SMTP_DEFAULTS = _load_smtp_defaults()


def _build_profiles():
    profiles = {}
    for name in PROFILE_NAMES:
        base = _SMTP_DEFAULTS
        prefix = "GATEWAY_%s_SMTP_" % name.upper()
        profiles[name] = {
            "host": os.environ.get(prefix + "HOST", base["host"]),
            "port": int(os.environ.get(prefix + "PORT", str(base["port"]))),
            "user": os.environ.get(prefix + "USER", base["user"]),
            "pass": os.environ.get(prefix + "PASS", base["pass"]),
            "from": os.environ.get(prefix + "FROM", base["from"]),
            "helo": os.environ.get(prefix + "HELO", base["helo"]),
        }
    return profiles


PROFILES = _build_profiles()

# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("gateway")


# ---------------------------------------------------------------------------
# 邮件发送核心
# ---------------------------------------------------------------------------
class NullHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理：仅支持 POST /send。"""

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _check_token(self) -> bool:
        authorization = self.headers.get("Authorization", "")
        # 支持 "Bearer <token>" 或裸 token
        if authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        else:
            token = authorization.strip()
        if token == GATEWAY_TOKEN:
            return True
        # 兼容查询参数 ?token=xxx
        from urllib.parse import urlparse, parse_qs
        qs = parse_qs(urlparse(self.path).query)
        if qs.get("token") and qs["token"][0] == GATEWAY_TOKEN:
            return True
        return False

    def _read_body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_POST(self):
        if self.path.split("?")[0] != "/send":
            self._send_json(404, {"ok": False, "error": "not found"})
            return
        if not self._check_token():
            self._send_json(401, {"ok": False, "error": "unauthorized"})
            return

        data = self._read_body()
        to = data.get("to")
        subject = data.get("subject", "")
        body = data.get("body", "")
        profile = data.get("profile", "local")

        if profile not in PROFILES:
            self._send_json(400, {"ok": False, "error": "unknown profile: %s" % profile})
            return

        if not to:
            self._send_json(400, {"ok": False, "error": "missing 'to'"})
            return

        try:
            self._send_mail(profile, to, subject, body)
            log.info("邮件已发送 [%-6s] -> %s", profile, to)
            self._send_json(200, {"ok": True, "to": to, "profile": profile})
        except Exception as exc:  # noqa: BLE001
            log.error("发送失败[%s]: %s", profile, exc)
            self._send_json(502, {"ok": False, "error": str(exc)})

    def _send_mail(self, profile, to, subject, body):
        """限流 + 自动重试的发送编排（线程安全）。

        - 先获取全局信号量：限制同时进行的 SMTP 连接数，防止告警风暴瞬间
          开太多 465 连接触发服务端限流/封禁。
        - 签名/调用方式保持不变(profile, to, subject, body)，对外完全兼容。
        """
        cfg = PROFILES[profile]
        _SMTP_SEM.acquire()
        try:
            last_exc = None
            for attempt in range(1, SMTP_MAX_RETRIES + 2):  # 首次 + 重试次数
                try:
                    self._send_mail_once(profile, cfg, to, subject, body)
                    return
                except Exception as exc:  # noqa: BLE001
                    last_exc = exc
                    log.warning("SMTP 发送失败[%s] 第%d次: %s", profile, attempt, exc)
                    if attempt <= SMTP_MAX_RETRIES:
                        log.info("SMTP 重试[%s] 第%d/共%d次 (%ss后)", profile,
                                 attempt, SMTP_MAX_RETRIES, SMTP_RETRY_BACKOFF)
                        time.sleep(SMTP_RETRY_BACKOFF)
            raise last_exc
        finally:
            _SMTP_SEM.release()

    def _send_mail_once(self, profile, cfg, to, subject, body):
        """单次 SMTP 会话：建连 + 登录 + 发信 + 关闭。"""
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = formataddr((str(Header(cfg["helo"], "utf-8")), cfg["from"]))
        msg["To"] = to
        # 生成 Message-ID，便于端到端追踪（可到发信邮箱后台核对投递明细）。
        msg["Message-ID"] = "<%s@%s>" % (uuid4().hex, cfg["helo"] or "zabbix-gateway")
        msg["Date"] = formatdate(localtime=True)
        msg["X-Zabbix-Profile"] = profile

        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=30)
        try:
            server.login(cfg["user"], cfg["pass"])
            # 记录 SMTP 服务器的 EHLO 身份标识(MTA 名)，便于判断是否真的连到了阿里云。
            ehlo_info = getattr(server, "ehlo_resp", None) or getattr(server, "ehlo_msg", None) or ""
            mid = msg["Message-ID"]
            log.info("SMTP 会话[%s] MTA=%r MessageID=%s", profile, ehlo_info, mid)
            # sendmail() 返回"被拒收件人字典"；只要有一个收件人被接受就不抛异常，
            # 因此必须显式检查返回值，否则被拒时会静默误报"邮件已发送"。
            refused = server.sendmail(cfg["from"], [to], msg.as_string())
            if refused:
                raise RuntimeError("SMTP 服务器拒绝收件: %r" % (refused,))
            log.info("SMTP 外发成功[%s] MessageID=%s -> %s", profile, mid, to)
        finally:
            server.quit()

    def log_message(self, format, *args):  # noqa: A002
        # 让日志走统一 logger，避免重复打印到 stderr
        log.info("%s - %s", self.address_string(), format % args)


class ThreadingHTTPServerX(ThreadingHTTPServer):
    daemon_threads = True


def main():
    try:
        server = ThreadingHTTPServerX((HOST, PORT), NullHandler)
        log.info("SMTP 网关已启动: http://%s:%s/send (profiles=%s)",
                 HOST, PORT, ",".join(PROFILES.keys()))
        for name, cfg in PROFILES.items():
            log.info("  profile[%s] SMTP->%s:%s from=%s",
                     name, cfg["host"], cfg["port"], cfg["from"])
            missing = [k for k in ("user", "pass", "from")
                       if not cfg.get(k) or cfg.get(k) == _PLACEHOLDER_CRED]
            if missing:
                log.warning("  profile[%s] SMTP 凭据缺失(%s)，发信将失败，"
                            "请设置 GATEWAY_%s_SMTP_%s 环境变量",
                            name, ",".join(missing), name.upper(),
                            "/".join(missing))
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("收到中断，退出")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        log.error("网关启动失败: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()