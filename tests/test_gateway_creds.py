# -*- coding: utf-8 -*-
"""
gateway.py 凭据安全默认 回归测试
================================
覆盖本次"移除 SMTP 凭据明文兜底默认"改动：
  1. 无环境变量时，user/pass/from 回落安全占位符（不暴露真实账号/密码）。
  2. 显式设置 GATEWAY_SMTP_* 环境变量时，正确覆盖占位符。
  3. host/port/helo 等非机密键保留合理缺省值。
  4. 每个 named profile 的凭据同源继承，未显式覆盖时保持安全占位符。

测试均针对纯函数 `_load_smtp_defaults()`（每次调用重新读 os.environ），
不启动网关、不触碰真实 SMTP，隔离于运行时已有的 GATEWAY_* 环境变量。
"""

import os

import pytest

# gateway 是 sys.path 下的顶层模块（项目根目录在 conftest/setup 中注册）。
import gateway as gw


# ---------------------------------------------------------------------------
# fixture：隔离运行时 GATEWAY_SMTP_* 环境变量，避免宿主机已配置的凭据干扰
# ---------------------------------------------------------------------------
_GATEWAY_SMTP_ENV_KEYS = [
    "GATEWAY_SMTP_HOST",
    "GATEWAY_SMTP_PORT",
    "GATEWAY_SMTP_USER",
    "GATEWAY_SMTP_PASS",
    "GATEWAY_SMTP_FROM",
    "GATEWAY_SMTP_HELO",
]


@pytest.fixture(autouse=True)
def _isolate_gateway_smtp_env(monkeypatch):
    """任何 test 前，剔除所有 GATEWAY_SMTP_* 顶层变量，并把模块级
    `_SMTP_DEFAULTS` 重置为一个占位符快照，保证缺省分支与 profile 继承
    可复现、不受宿主机已导出凭据/固化值影响。"""
    for key in _GATEWAY_SMTP_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    # 让 _build_profiles() 以"无凭据"状态为基准，而非宿主机的固化账号。
    monkeypatch.setattr(gw, "_SMTP_DEFAULTS", gw._load_smtp_defaults())


# ---------------------------------------------------------------------------
# 1) 无 env 时安全占位符回落
# ---------------------------------------------------------------------------
def test_defaults_without_env_fall_back_to_placeholder():
    cfg = gw._load_smtp_defaults()
    assert cfg["user"] == gw._PLACEHOLDER_CRED
    assert cfg["pass"] == gw._PLACEHOLDER_CRED
    assert cfg["from"] == gw._PLACEHOLDER_CRED


def test_placeholder_does_not_leak_real_credentials():
    """占位符必须不等于任何真实账号/密码，且不含 '@' 域名痕迹。"""
    cfg = gw._load_smtp_defaults()
    for key in ("user", "pass", "from"):
        value = cfg[key]
        # 占位符不应包含真实邮箱的 @ 域（如 example.com 等）
        assert "@" not in value, f"{key} 泄露了邮箱格式: {value!r}"
        assert "username" not in value.lower(), f"{key} 疑似泄露实名账号: {value!r}"


def test_non_secret_keys_keep_reasonable_defaults():
    cfg = gw._load_smtp_defaults()
    assert cfg["host"] == "smtp.qiye.aliyun.com"
    assert cfg["port"] == 465
    assert cfg["helo"] == "localhost"


# ---------------------------------------------------------------------------
# 2) 显式设置 env 时正确覆盖
# ---------------------------------------------------------------------------
def test_defaults_override_via_env(monkeypatch):
    monkeypatch.setenv("GATEWAY_SMTP_USER", "alice@example.com")
    monkeypatch.setenv("GATEWAY_SMTP_PASS", "s3cret")
    monkeypatch.setenv("GATEWAY_SMTP_FROM", "noreply@example.com")
    cfg = gw._load_smtp_defaults()
    assert cfg["user"] == "alice@example.com"
    assert cfg["pass"] == "s3cret"
    assert cfg["from"] == "noreply@example.com"
    # 未设置的 host/port/helo 仍为缺省
    assert cfg["host"] == "smtp.qiye.aliyun.com"
    assert cfg["port"] == 465


def test_partial_env_only_overrides_supplied_keys(monkeypatch):
    """只设 PASS，user/from 仍回落占位符（安全缺省不被意外覆盖）。"""
    monkeypatch.setenv("GATEWAY_SMTP_PASS", "only-pass-set")
    cfg = gw._load_smtp_defaults()
    assert cfg["pass"] == "only-pass-set"
    assert cfg["user"] == gw._PLACEHOLDER_CRED
    assert cfg["from"] == gw._PLACEHOLDER_CRED


# ---------------------------------------------------------------------------
# 3) named profile 同源继承
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("profile", gw.PROFILE_NAMES)
def test_profile_placeholder_when_untouched(monkeypatch, profile):
    """未以 <PROFILE> 前缀覆盖时，profile 凭据回落安全占位符（同源继承）。"""
    cfg = gw._build_profiles()[profile]
    assert cfg["user"] == gw._PLACEHOLDER_CRED
    assert cfg["pass"] == gw._PLACEHOLDER_CRED
    assert cfg["from"] == gw._PLACEHOLDER_CRED
    assert cfg["host"] == "smtp.qiye.aliyun.com"
    assert cfg["helo"] == "localhost"


def test_profile_can_override_via_profile_specific_env(monkeypatch):
    """remote profile 前缀变量优先级高于顶层缺省占位符。"""
    monkeypatch.setenv("GATEWAY_REMOTE_SMTP_USER", "remote-ops@example.com")
    cfg = gw._build_profiles()["remote"]
    assert cfg["user"] == "remote-ops@example.com"


# ---------------------------------------------------------------------------
# 4) 告警校验逻辑：缺失凭据被正确识别（与 main() 内联逻辑同源）
# ---------------------------------------------------------------------------
def test_missing_cred_detection_matches_main_logic():
    """
    复刻 main() 内联的告警判定条件，验证：
      - 占位符值 -> 判为缺失
      - 空串     -> 判为缺失
      - 真实值   -> 不判为缺失
    这段镜像了 main() 里 `if not cfg.get(k) or cfg.get(k)==_PLACEHOLDER_CRED` 分支。
    """
    placeholder_cfg = dict.fromkeys(("user", "pass", "from"), gw._PLACEHOLDER_CRED)
    empty_cfg = dict.fromkeys(("user", "pass", "from"), "")
    real_cfg = {
        "user": "real@example.com",
        "pass": "realpass",
        "from": "real@example.com",
    }

    def missing(cfg):
        return [k for k in ("user", "pass", "from")
                if not cfg.get(k) or cfg.get(k) == gw._PLACEHOLDER_CRED]

    assert missing(placeholder_cfg) == ["user", "pass", "from"]
    assert missing(empty_cfg) == ["user", "pass", "from"]
    assert missing(real_cfg) == []