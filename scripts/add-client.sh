#!/usr/bin/env bash
# =============================================================================
# Добавление нового клиента к существующему XRay серверу
# Редактирует config.json через jq и перезапускает контейнер (~1 сек).
#
# Использование:
#   bash add-client.sh [email]
#   bash add-client.sh alice@example.com
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}   $*"; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
die()  { echo -e "${RED}[ERR]${NC}  $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Запустите от root"

INSTALL_DIR="${INSTALL_DIR:-/opt/xray-reality}"
SECRETS_FILE="$INSTALL_DIR/server-secrets.env"
CONFIG_FILE="$INSTALL_DIR/config/config.json"

[[ -f "$SECRETS_FILE" ]] || die "server-secrets.env не найден: $SECRETS_FILE"
[[ -f "$CONFIG_FILE"  ]] || die "config.json не найден: $CONFIG_FILE"

# shellcheck disable=SC1090
source "$SECRETS_FILE"

CLIENT_EMAIL="${1:-user-$(date +%s)@vpn}"
NEW_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')

info "Добавляю клиента: $CLIENT_EMAIL / UUID: $NEW_UUID"

# Добавляем в config.json через jq
TEMP=$(mktemp)
jq --arg uuid "$NEW_UUID" --arg email "$CLIENT_EMAIL" \
    '.inbounds[0].settings.clients += [{"id": $uuid, "flow": "xtls-rprx-vision", "email": $email}]' \
    "$CONFIG_FILE" > "$TEMP"

mv "$TEMP" "$CONFIG_FILE"

# Перезапускаем контейнер чтобы применить изменения
info "Перезапускаю XRay..."
cd "$INSTALL_DIR"
docker compose restart xray

# Генерируем конфиг для нового клиента
VLESS_URI="vless://${NEW_UUID}@${SERVER_IP}:${XRAY_PORT}"
VLESS_URI+="?encryption=none&flow=xtls-rprx-vision&security=reality"
VLESS_URI+="&sni=${REALITY_SNI}&fp=chrome&pbk=${PUBLIC_KEY}&sid=${SHORT_ID}"
VLESS_URI+="&type=tcp&headerType=none#REALITY-${CLIENT_EMAIL}"

CLIENT_DIR="$INSTALL_DIR/clients/${CLIENT_EMAIL}"
mkdir -p "$CLIENT_DIR"
echo "$VLESS_URI" > "$CLIENT_DIR/client.uri"

cat > "$CLIENT_DIR/manual-params.txt" <<EOF
UUID:       ${NEW_UUID}
Email:      ${CLIENT_EMAIL}
Server:     ${SERVER_IP}:${XRAY_PORT}
Public Key: ${PUBLIC_KEY}
Short ID:   ${SHORT_ID}
SNI:        ${REALITY_SNI}
URI:        ${VLESS_URI}
EOF

ok "Клиент добавлен. Конфиги в: $CLIENT_DIR/"
echo ""
echo "$VLESS_URI"

if command -v qrencode &>/dev/null; then
    echo ""
    qrencode -t ANSIUTF8 "$VLESS_URI"
fi
