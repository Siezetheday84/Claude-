#!/usr/bin/env bash
# =============================================================================
# VLESS+REALITY VPN Server Setup
# XRay-core · порт 443 · маскировка под microsoft.com
# Поддерживаемые ОС: Ubuntu 20.04/22.04/24.04, Debian 11/12
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()      { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()     { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# --------------------------------------------------------------------------- #
# Параметры — можно переопределить через env перед запуском                   #
# --------------------------------------------------------------------------- #
XRAY_PORT="${XRAY_PORT:-443}"
REALITY_DEST="${REALITY_DEST:-microsoft.com:443}"          # сайт-«донор» TLS
REALITY_SNI="${REALITY_SNI:-microsoft.com}"                # SNI для клиентов
INSTALL_DIR="${INSTALL_DIR:-/opt/xray-reality}"
XRAY_VERSION="${XRAY_VERSION:-latest}"

# --------------------------------------------------------------------------- #
# Проверка прав                                                                #
# --------------------------------------------------------------------------- #
[[ $EUID -eq 0 ]] || die "Запустите скрипт от root: sudo bash setup.sh"

# --------------------------------------------------------------------------- #
# Зависимости                                                                  #
# --------------------------------------------------------------------------- #
install_deps() {
    info "Устанавливаю зависимости..."
    apt-get update -qq
    apt-get install -y -qq curl wget uuid-runtime qrencode jq ufw \
        ca-certificates gnupg lsb-release 2>/dev/null || true
    ok "Зависимости установлены"
}

# --------------------------------------------------------------------------- #
# Docker                                                                       #
# --------------------------------------------------------------------------- #
install_docker() {
    if command -v docker &>/dev/null; then
        ok "Docker уже установлен: $(docker --version)"
        return
    fi
    info "Устанавливаю Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    ok "Docker установлен"
}

# --------------------------------------------------------------------------- #
# XRay: генерация ключей REALITY                                              #
# --------------------------------------------------------------------------- #
generate_keys() {
    info "Генерирую ключи REALITY через XRay..."

    # Запускаем одноразовый контейнер для генерации ключей
    # Entrypoint образа уже = "xray", поэтому передаём только "x25519"
    KEYPAIR=$(docker run --rm ghcr.io/xtls/xray-core:latest x25519)
    # Новый формат (XRay >= 25.x): "PrivateKey: ..." / "Password (PublicKey): ..."
    # Старый формат:               "Private key: ..." / "Public key: ..."
    PRIVATE_KEY=$(echo "$KEYPAIR" | grep -i 'privatekey:'         | awk '{print $NF}')
    PUBLIC_KEY=$(echo "$KEYPAIR"  | grep -i 'publickey\|Password' | awk '{print $NF}')

    [[ -n "$PRIVATE_KEY" ]] || die "Не удалось сгенерировать ключи"
    ok "Ключи REALITY сгенерированы"
}

# --------------------------------------------------------------------------- #
# UUID клиента                                                                 #
# --------------------------------------------------------------------------- #
generate_uuid() {
    CLIENT_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
    # Генерируем случайный short ID (16 hex символов = 8 байт, максимум по спеке REALITY)
    SHORT_ID=$(openssl rand -hex 8)
    ok "UUID клиента: $CLIENT_UUID"
    ok "Short ID:     $SHORT_ID"
}

# --------------------------------------------------------------------------- #
# Конфигурация XRay                                                            #
# --------------------------------------------------------------------------- #
write_server_config() {
    info "Записываю конфигурацию сервера..."
    mkdir -p "$INSTALL_DIR/config"

    cat > "$INSTALL_DIR/config/config.json" <<EOF
{
  "log": {
    "loglevel": "warning",
    "access": "/var/log/xray/access.log",
    "error":  "/var/log/xray/error.log"
  },
  "inbounds": [
    {
      "listen":   "0.0.0.0",
      "port":     ${XRAY_PORT},
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id":   "${CLIENT_UUID}",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network":  "tcp",
        "security": "reality",
        "realitySettings": {
          "show":        false,
          "dest":        "${REALITY_DEST}",
          "xver":        0,
          "serverNames": ["${REALITY_SNI}", "www.${REALITY_SNI}"],
          "privateKey":  "${PRIVATE_KEY}",
          "minClientVer": "",
          "maxClientVer": "",
          "maxTimeDiff": 0,
          "shortIds":    ["${SHORT_ID}", ""]
        }
      },
      "sniffing": {
        "enabled":     true,
        "destOverride": ["http", "tls", "quic"],
        "routeOnly":   false
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag":      "direct",
      "settings": {
        "domainStrategy": "UseIPv4"
      }
    },
    {
      "protocol": "blackhole",
      "tag":      "block"
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      {
        "type":        "field",
        "ip":          ["geoip:private"],
        "outboundTag": "block"
      }
    ]
  }
}
EOF
    ok "Конфигурация записана в $INSTALL_DIR/config/config.json"
}

# --------------------------------------------------------------------------- #
# Docker Compose                                                                #
# --------------------------------------------------------------------------- #
write_compose() {
    cat > "$INSTALL_DIR/docker-compose.yml" <<EOF
version: "3.8"
services:
  xray:
    image: ghcr.io/xtls/xray-core:latest
    container_name: xray-reality
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config:/etc/xray:ro
      - xray-logs:/var/log/xray
    command: ["xray", "run", "-c", "/etc/xray/config.json"]
    ulimits:
      nofile:
        soft: 65536
        hard: 65536
    healthcheck:
      test: ["CMD-SHELL", "pgrep -x xray > /dev/null || exit 1"]
      interval: 30s
      timeout:  10s
      retries:  3
      start_period: 10s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  xray-logs:
    driver: local
EOF
    ok "docker-compose.yml создан"
}

# --------------------------------------------------------------------------- #
# Firewall                                                                     #
# --------------------------------------------------------------------------- #
configure_firewall() {
    info "Настраиваю ufw..."

    # Определяем текущий SSH-порт из sshd_config, чтобы не заблокировать себя
    SSH_PORT=$(ss -tlnp 2>/dev/null | awk '/sshd/{match($4, /:([0-9]+)$/, a); if(a[1]) print a[1]}' | head -1)
    SSH_PORT="${SSH_PORT:-22}"

    # НЕ делаем reset: добавляем правила поверх существующих,
    # чтобы не снести правила других сервисов и не потерять доступ
    ufw --force default deny incoming  >/dev/null
    ufw --force default allow outgoing >/dev/null

    # Разрешаем SSH на обнаруженном порту
    if [[ "$SSH_PORT" != "22" ]]; then
        ufw allow "${SSH_PORT}/tcp" >/dev/null
        info "SSH: порт $SSH_PORT (нестандартный)"
    fi
    ufw allow ssh >/dev/null  # правило для порта 22 + любой sshd

    ufw allow "${XRAY_PORT}/tcp" >/dev/null

    # Включаем только если ufw ещё не активен
    if ! ufw status | grep -q "Status: active"; then
        ufw --force enable >/dev/null
    else
        ufw reload >/dev/null
    fi

    ok "Firewall настроен: SSH($SSH_PORT) и порт ${XRAY_PORT}/tcp открыты"
}

# --------------------------------------------------------------------------- #
# Запуск контейнера                                                            #
# --------------------------------------------------------------------------- #
start_xray() {
    info "Запускаю XRay..."
    cd "$INSTALL_DIR"
    docker compose pull
    docker compose up -d
    sleep 2
    if docker compose ps | grep -q "Up"; then
        ok "XRay запущен"
    else
        docker compose logs --tail=30
        die "XRay не запустился — см. логи выше"
    fi
}

# --------------------------------------------------------------------------- #
# Получаем внешний IP                                                          #
# --------------------------------------------------------------------------- #
get_server_ip() {
    SERVER_IP=$(curl -s4 https://api.ipify.org 2>/dev/null || \
                curl -s4 https://ifconfig.me  2>/dev/null || \
                hostname -I | awk '{print $1}')
    [[ -n "$SERVER_IP" ]] || die "Не удалось определить IP сервера"
}

# --------------------------------------------------------------------------- #
# Генерация клиентских конфигов                                                #
# --------------------------------------------------------------------------- #
write_client_configs() {
    CLIENT_DIR="$INSTALL_DIR/clients"
    mkdir -p "$CLIENT_DIR"

    # --- VLESS URI (универсальный для v2rayNG, Hiddify, Nekoray) ----------- #
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

    # Сохраняем URI
    echo "$VLESS_URI" > "$CLIENT_DIR/client.uri"

    # --- Полный XRay клиентский конфиг (для NekoBox / Nekoray / десктоп) --- #
    # v2rayNG/Hiddify импортируют VLESS через URI — используйте client.uri   #
    cat > "$CLIENT_DIR/xray-client-config.json" <<EOF
{
  "log": { "loglevel": "warning" },
  "inbounds": [
    {
      "listen": "127.0.0.1", "port": 10808,
      "protocol": "socks", "settings": { "udp": true }, "tag": "socks-in"
    },
    {
      "listen": "127.0.0.1", "port": 10809,
      "protocol": "http", "tag": "http-in"
    }
  ],
  "outbounds": [
    {
      "protocol": "vless",
      "settings": {
        "vnext": [{
          "address": "${SERVER_IP}",
          "port": ${XRAY_PORT},
          "users": [{"id": "${CLIENT_UUID}", "flow": "xtls-rprx-vision", "encryption": "none"}]
        }]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "serverName": "${REALITY_SNI}",
          "fingerprint": "chrome",
          "publicKey": "${PUBLIC_KEY}",
          "shortId": "${SHORT_ID}",
          "spiderX": ""
        }
      },
      "tag": "proxy"
    },
    { "protocol": "freedom", "tag": "direct" },
    { "protocol": "blackhole", "tag": "block" }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch",
    "rules": [
      { "type": "field", "ip": ["geoip:private"], "outboundTag": "direct" }
    ]
  }
}
EOF

    # --- Hiddify / Sing-box совместимый share link ------------------------- #
    echo "$VLESS_URI" > "$CLIENT_DIR/hiddify-import.txt"

    # --- QR-код ------------------------------------------------------------- #
    if command -v qrencode &>/dev/null; then
        qrencode -t PNG -o "$CLIENT_DIR/qr-code.png" "$VLESS_URI"
        ok "QR-код сохранён в $CLIENT_DIR/qr-code.png"
    fi

    # --- Все параметры для ручной настройки --------------------------------- #
    cat > "$CLIENT_DIR/manual-params.txt" <<EOF
=== Параметры для ручной настройки клиента ===

Протокол:   VLESS
Адрес:      ${SERVER_IP}
Порт:       ${XRAY_PORT}
UUID:       ${CLIENT_UUID}
Шифрование: none
Flow:       xtls-rprx-vision
Транспорт:  tcp
TLS:        REALITY
SNI:        ${REALITY_SNI}
Fingerprint: chrome
Public Key: ${PUBLIC_KEY}
Short ID:   ${SHORT_ID}
EOF

    ok "Клиентские конфиги сохранены в $CLIENT_DIR/"
}

# --------------------------------------------------------------------------- #
# Сохраняем серверные секреты                                                  #
# --------------------------------------------------------------------------- #
save_server_secrets() {
    cat > "$INSTALL_DIR/server-secrets.env" <<EOF
# Сгенерировано setup.sh — храните в безопасном месте
SERVER_IP=${SERVER_IP}
XRAY_PORT=${XRAY_PORT}
CLIENT_UUID=${CLIENT_UUID}
PRIVATE_KEY=${PRIVATE_KEY}
PUBLIC_KEY=${PUBLIC_KEY}
SHORT_ID=${SHORT_ID}
REALITY_SNI=${REALITY_SNI}
REALITY_DEST=${REALITY_DEST}
EOF
    chmod 600 "$INSTALL_DIR/server-secrets.env"
    ok "Секреты сохранены в $INSTALL_DIR/server-secrets.env (chmod 600)"
}

# --------------------------------------------------------------------------- #
# Финальный вывод                                                              #
# --------------------------------------------------------------------------- #
print_summary() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║        VLESS+REALITY успешно развёрнут!              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Сервер:     ${CYAN}${SERVER_IP}:${XRAY_PORT}${NC}"
    echo -e "  Протокол:   ${CYAN}VLESS + REALITY (имитирует ${REALITY_SNI})${NC}"
    echo -e "  UUID:       ${CYAN}${CLIENT_UUID}${NC}"
    echo -e "  Public Key: ${CYAN}${PUBLIC_KEY}${NC}"
    echo -e "  Short ID:   ${CYAN}${SHORT_ID}${NC}"
    echo ""
    echo -e "  ${YELLOW}VLESS URI (для импорта в клиент):${NC}"
    cat "$INSTALL_DIR/clients/client.uri"
    echo ""
    echo -e "  Файлы клиентов: ${CYAN}$INSTALL_DIR/clients/${NC}"
    echo -e "  Управление:     ${CYAN}cd $INSTALL_DIR && docker compose [logs|restart|stop]${NC}"
    echo ""

    # QR в терминале (если поддерживается)
    if command -v qrencode &>/dev/null; then
        echo -e "  ${YELLOW}QR-код для импорта:${NC}"
        qrencode -t ANSIUTF8 "$(cat "$INSTALL_DIR/clients/client.uri")"
    fi
}

# --------------------------------------------------------------------------- #
# MAIN                                                                         #
# --------------------------------------------------------------------------- #
main() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  VLESS+REALITY Setup  |  XRay-core  |  Anti-DPI VPN   ${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════${NC}"
    echo ""

    install_deps
    install_docker
    generate_keys
    generate_uuid
    get_server_ip
    write_server_config
    write_compose
    configure_firewall
    start_xray
    write_client_configs
    save_server_secrets
    print_summary
}

main "$@"
