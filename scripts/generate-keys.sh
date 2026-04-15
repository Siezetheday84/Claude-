#!/usr/bin/env bash
# =============================================================================
# Генерация ключей REALITY + UUID клиента
# Требует: Docker (для запуска xray x25519)
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()  { echo -e "${GREEN}[OK]${NC}  $*"; }
die() { echo -e "${RED}[ERR]${NC} $*" >&2; exit 1; }

command -v docker &>/dev/null || die "Docker не установлен"
command -v uuidgen &>/dev/null || die "uuidgen не найден (apt install uuid-runtime)"

# Генерируем пару x25519 через официальный XRay образ
KEYPAIR=$(docker run --rm ghcr.io/xtls/xray-core:latest xray x25519)
PRIVATE_KEY=$(echo "$KEYPAIR" | grep 'Private key:' | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYPAIR"  | grep 'Public key:'  | awk '{print $3}')

CLIENT_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
SHORT_ID=$(openssl rand -hex 4)

echo ""
echo -e "${CYAN}══════════════ Сгенерированные параметры ══════════════${NC}"
echo ""
echo -e "  Private Key : ${GREEN}${PRIVATE_KEY}${NC}  (только сервер, не передавать клиенту!)"
echo -e "  Public Key  : ${GREEN}${PUBLIC_KEY}${NC}"
echo -e "  Client UUID : ${GREEN}${CLIENT_UUID}${NC}"
echo -e "  Short ID    : ${GREEN}${SHORT_ID}${NC}"
echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════${NC}"

# Если передан аргумент --env — выводим в формате .env
if [[ "${1:-}" == "--env" ]]; then
    echo ""
    echo "# Вставьте в ваш .env или server-secrets.env:"
    echo "PRIVATE_KEY=${PRIVATE_KEY}"
    echo "PUBLIC_KEY=${PUBLIC_KEY}"
    echo "CLIENT_UUID=${CLIENT_UUID}"
    echo "SHORT_ID=${SHORT_ID}"
fi

ok "Готово"
