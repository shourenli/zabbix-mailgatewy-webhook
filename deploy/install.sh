#!/usr/bin/env bash
# ============================================================================
# SMTP 邮件网关一键安装脚本
# 用法: sudo bash install.sh
# 作用: 创建程序目录、配置目录、专用用户、拷贝 gateway.py、生成 env.conf
# ============================================================================
set -euo pipefail

APP_DIR="/opt/zabbix-ai-email"
CONF_DIR="/etc/zabbix-ai-email"
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="gateway"

if [[ $EUID -ne 0 ]]; then
  echo "请用 root 或 sudo 运行: sudo bash $0" >&2
  exit 1
fi

echo "[1/5] 创建目录与专用用户"
mkdir -p "$APP_DIR"
mkdir -p "$CONF_DIR"
if ! id "zabbix-ai-email" &>/dev/null; then
  useradd --system --no-create-home --shell /usr/sbin/nologin "zabbix-ai-email"
fi

echo "[2/5] 拷贝程序与 systemd unit"
cp "$SRC_DIR/../src/gateway.py" "$APP_DIR/gateway.py"
cp "$SRC_DIR/gateway.service" /etc/systemd/system/${SERVICE_NAME}.service

echo "[3/5] 生成环境配置（如已存在则跳过，避免覆盖你的 Token）"
if [[ ! -f "$CONF_DIR/env.conf" ]]; then
  cat > "$CONF_DIR/env.conf" <<'EOF'
# ====== 网关鉴权 Token（调用方必须用同一个）=======
GATEWAY_TOKEN=CHANGE_ME_LOCAL_TOKEN

# ====== SMTP 配置（默认 profile: local）=======
GATEWAY_HOST=127.0.0.1
GATEWAY_PORT=8025
GATEWAY_SMTP_HOST=smtp.example.com
GATEWAY_SMTP_PORT=465
GATEWAY_SMTP_USER=CHANGE_ME_SMTP_USER
GATEWAY_SMTP_PASS=CHANGE_ME_SMTP_PASS
GATEWAY_SMTP_FROM=CHANGE_ME_SMTP_FROM
GATEWAY_SMTP_HELO=my_mailer

# ====== 可选：remote profile 覆盖（按需配置）=======
# GATEWAY_REMOTE_SMTP_HOST=smtp.example.com
# GATEWAY_REMOTE_SMTP_PORT=465
# GATEWAY_REMOTE_SMTP_USER=CHANGE_ME
# GATEWAY_REMOTE_SMTP_PASS=CHANGE_ME
# GATEWAY_REMOTE_SMTP_FROM=CHANGE_ME
# GATEWAY_REMOTE_SMTP_HELO=my_remote
EOF
  chmod 600 "$CONF_DIR/env.conf"
else
  echo "   已存在 $CONF_DIR/env.conf，未覆盖。请手工核对 GATEWAY_TOKEN。"
fi

echo "[4/5] 权限与属主"
chown -R zabbix-ai-email:zabbix-ai-email "$APP_DIR"
chmod 755 "$APP_DIR/gateway.py"

echo "[5/5] 重载并启动"
systemctl daemon-reload
systemctl enable --now ${SERVICE_NAME}.service
systemctl status ${SERVICE_NAME}.service --no-pager

echo
echo "✅ 安装完成。请立即编辑 $CONF_DIR/env.conf 修改 GATEWAY_TOKEN 与 SMTP 凭据，然后:"
echo "   sudo systemctl restart ${SERVICE_NAME}.service"
echo
echo "测试发送:"
echo "curl -s -X POST http://127.0.0.1:8025/send \\"
echo "  -H 'Authorization: Bearer 你的TOKEN' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"to\":\"客户邮箱\",\"subject\":\"测试\",\"body\":\"<b>你好</b>\"}'"
