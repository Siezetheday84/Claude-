#!/usr/bin/env bash
# =============================================================================
# Генерация клиентских конфигов из server-secrets.env
#
# Использование:
#   bash generate-client-config.sh /opt/xray-reality/server-secrets.env
#   bash generate-client-config.sh          # читает из текущей директории
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}   $*"; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
die()  { echo -e "${RED}[ERR]${NC}  $*" >&2; exit 1; }

SECRETS_FILE="${1:-./server-secrets.env}"
[[ -f "$SECRETS_FILE" ]] || die "Файл секретов не найден: $SECRETS_FILE"

# shellcheck disable=SC1090
source "$SECRETS_FILE"

# Проверяем обязательные переменные
for var in SERVER_IP XRAY_PORT CLIENT_UUID PUBLIC_KEY SHORT_ID REALITY_SNI; do
    [[ -n "${!var:-}" ]] || die "Переменная $var не задана в $SECRETS_FILE"
done

OUT_DIR="$(dirname "$SECRETS_FILE")/clients"
mkdir -p "$OUT_DIR"

# --------------------------------------------------------------------------- #
# VLESS URI                                                                    #
# --------------------------------------------------------------------------- #
VLESS_URI="vless://${CLIENT_UUID}@${SERVER_IP}:${XRAY_PORT}"
VLESS_URI+="?encryption=none"
VLESS_URI+="&flow=xtls-rprx-vision"
VLESS_URI+="&security=reality"
VLESS_URI+="&sni=${REALITY_SNI}"
VLESS_URI+="&fp=chrome"
VLESS_URI+="&pbk=${PUBLIC_KEY}"
VLESS_URI+="&sid=${SHORT_ID}"
VLESS_URI+="&type=tcp"
VLESS_URI+="&headerType=none"
VLESS_URI+="#REALITY-${SERVER_IP}"

echo "$VLESS_URI" > "$OUT_DIR/client.uri"
ok "VLESS URI → $OUT_DIR/client.uri"

# --------------------------------------------------------------------------- #
# v2rayNG / Hiddify JSON (vmess-share формат v2)                              #
# --------------------------------------------------------------------------- #
cat > "$OUT_DIR/v2rayng-config.json" <<EOF
{
  "v":    "2",
  "ps":   "REALITY-${SERVER_IP}",
  "add":  "${SERVER_IP}",
  "port": "${XRAY_PORT}",
  "id":   "${CLIENT_UUID}",
  "aid":  "0",
  "scy":  "none",
  "net":  "tcp",
  "type": "none",
  "host": "",
  "path": "",
  "tls":  "reality",
  "sni":  "${REALITY_SNI}",
  "alpn": "",
  "fp":   "chrome",
  "pbk":  "${PUBLIC_KEY}",
  "sid":  "${SHORT_ID}",
  "spx":  "",
  "flow": "xtls-rprx-vision"
}
EOF
ok "v2rayNG конфиг → $OUT_DIR/v2rayng-config.json"

# --------------------------------------------------------------------------- #
# Sing-box outbound (для Hiddify Next / sing-box)                             #
# --------------------------------------------------------------------------- #
cat > "$OUT_DIR/singbox-outbound.json" <<EOF
{
  "type":       "vless",
  "tag":        "REALITY-${SERVER_IP}",
  "server":     "${SERVER_IP}",
  "server_port": ${XRAY_PORT},
  "uuid":        "${CLIENT_UUID}",
  "flow":        "xtls-rprx-vision",
  "tls": {
    "enabled":     true,
    "server_name": "${REALITY_SNI}",
    "utls": {
      "enabled":     true,
      "fingerprint": "chrome"
    },
    "reality": {
      "enabled":    true,
      "public_key": "${PUBLIC_KEY}",
      "short_id":   "${SHORT_ID}"
    }
  }
}
EOF
ok "sing-box outbound → $OUT_DIR/singbox-outbound.json"

# --------------------------------------------------------------------------- #
# Читаемый текстовый файл для ручной настройки                                #
# --------------------------------------------------------------------------- #
cat > "$OUT_DIR/manual-params.txt" <<EOF
=== VLESS+REALITY — параметры для ручной настройки ===

Адрес (Host):     ${SERVER_IP}
Порт:             ${XRAY_PORT}
Протокол:         VLESS
UUID:             ${CLIENT_UUID}
Шифрование:       none
Flow:             xtls-rprx-vision
Транспорт:        TCP
TLS тип:          REALITY
SNI:              ${REALITY_SNI}
Fingerprint:      chrome
Public Key:       ${PUBLIC_KEY}
Short ID:         ${SHORT_ID}

VLESS URI:
${VLESS_URI}
EOF
ok "Параметры вручную → $OUT_DIR/manual-params.txt"

# --------------------------------------------------------------------------- #
# QR-код                                                                       #
# --------------------------------------------------------------------------- #
if command -v qrencode &>/dev/null; then
    qrencode -t PNG -o "$OUT_DIR/qr-code.png" "$VLESS_URI"
    ok "QR PNG → $OUT_DIR/qr-code.png"
    echo ""
    info "QR-код в терминале:"
    qrencode -t ANSIUTF8 "$VLESS_URI"
else
    echo ""
    echo -e "${YELLOW}[HINT]${NC} Установите qrencode для генерации QR: apt install qrencode"
    echo ""
    info "VLESS URI для импорта:"
    echo "$VLESS_URI"
fi

echo ""
ok "Все конфиги в: $OUT_DIR/"
