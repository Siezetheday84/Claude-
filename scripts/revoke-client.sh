#!/usr/bin/env bash
# =============================================================================
# Отзыв клиентского UUID из XRay конфига
#
# Использование:
#   bash revoke-client.sh <uuid>
#   bash revoke-client.sh a1b2c3d4-...
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
ok()   { echo -e "${GREEN}[OK]${NC}   $*"; }
info() { echo -e "${CYAN}[INFO]${NC} $*"; }
die()  { echo -e "${RED}[ERR]${NC}  $*" >&2; exit 1; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }

[[ $EUID -eq 0 ]] || die "Запустите от root"
command -v jq &>/dev/null || die "jq не найден: apt install jq"

TARGET_UUID="${1:-}"
[[ -n "$TARGET_UUID" ]] || die "Укажите UUID: bash revoke-client.sh <uuid>"

INSTALL_DIR="${INSTALL_DIR:-/opt/xray-reality}"
CONFIG_FILE="$INSTALL_DIR/config/config.json"
[[ -f "$CONFIG_FILE" ]] || die "config.json не найден: $CONFIG_FILE"

# Проверяем, есть ли такой UUID
COUNT=$(jq --arg uuid "$TARGET_UUID" '[.inbounds[0].settings.clients[] | select(.id == $uuid)] | length' "$CONFIG_FILE")
[[ "$COUNT" -gt 0 ]] || die "UUID не найден в конфиге: $TARGET_UUID"

# Показываем текущих клиентов
info "Клиенты до удаления:"
jq -r '.inbounds[0].settings.clients[] | "  id: \(.id)  email: \(.email // "n/a")"' "$CONFIG_FILE"

# Удаляем
TEMP=$(mktemp)
jq --arg uuid "$TARGET_UUID" \
    '.inbounds[0].settings.clients = [.inbounds[0].settings.clients[] | select(.id != $uuid)]' \
    "$CONFIG_FILE" > "$TEMP"
mv "$TEMP" "$CONFIG_FILE"

info "Клиенты после удаления:"
jq -r '.inbounds[0].settings.clients[] | "  id: \(.id)  email: \(.email // "n/a")"' "$CONFIG_FILE"

# Перезапускаем XRay
info "Перезапускаю XRay..."
cd "$INSTALL_DIR"
docker compose restart xray
ok "UUID $TARGET_UUID отозван. XRay перезапущен."

# Удаляем клиентские файлы если есть
CLIENT_DIRS=$(find "$INSTALL_DIR/clients" -name "manual-params.txt" -exec grep -l "$TARGET_UUID" {} \; 2>/dev/null || true)
if [[ -n "$CLIENT_DIRS" ]]; then
    for f in $CLIENT_DIRS; do
        DIR=$(dirname "$f")
        warn "Удаляю клиентские файлы: $DIR"
        rm -rf "$DIR"
    done
fi
