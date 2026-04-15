#!/usr/bin/env bash
# =============================================================================
# VLESS+WebSocket+TLS — CDN fronting через Cloudflare
#
# Когда использовать: прямой IP сервера заблокирован, REALITY не помогает.
# Схема: клиент → Cloudflare CDN (IP не блокируется) → ваш VPS → интернет
#
# Требования:
#   - Домен, добавленный в Cloudflare (с DNS-проксированием, оранжевое облако)
#   - Порт 80/443 не занят другим сервисом
#   - Запустить ПОСЛЕ setup.sh или как отдельную установку
# =============================================================================
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
die()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Запустите от root: sudo bash setup-cdn.sh"

# --------------------------------------------------------------------------- #
# Параметры                                                                    #
# --------------------------------------------------------------------------- #
CDN_DOMAIN="${CDN_DOMAIN:-}"        # ваш домен в Cloudflare, напр. vpn.example.com
WS_PATH="${WS_PATH:-}"              # случайный путь для WS, напр. /a8f3k2
XRAY_WS_PORT="${XRAY_WS_PORT:-8443}" # внутренний порт XRay (localhost)
INSTALL_DIR="${INSTALL_DIR:-/opt/xray-reality}"

# --------------------------------------------------------------------------- #
# Интерактивный ввод если параметры не заданы                                 #
# --------------------------------------------------------------------------- #
if [[ -z "$CDN_DOMAIN" ]]; then
    read -rp "Введите домен (в Cloudflare с проксированием): " CDN_DOMAIN
fi
if [[ -z "$WS_PATH" ]]; then
    WS_PATH="/$(openssl rand -hex 6)"
    info "Сгенерирован случайный путь: $WS_PATH"
fi

[[ -n "$CDN_DOMAIN" ]] || die "CDN_DOMAIN не задан"

# --------------------------------------------------------------------------- #
# Зависимости                                                                  #
# --------------------------------------------------------------------------- #
install_deps() {
    apt-get update -qq
    apt-get install -y -qq nginx certbot python3-certbot-nginx uuid-runtime jq
    ok "Зависимости установлены"
}

# --------------------------------------------------------------------------- #
# UUID клиента (новый или из существующего secrets.env)                        #
# --------------------------------------------------------------------------- #
load_or_generate_params() {
    if [[ -f "$INSTALL_DIR/server-secrets.env" ]]; then
        # shellcheck disable=SC1090
        source "$INSTALL_DIR/server-secrets.env"
        info "Загружены параметры из $INSTALL_DIR/server-secrets.env"
    else
        CLIENT_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
        warn "server-secrets.env не найден, генерирую новый UUID: $CLIENT_UUID"
        warn "Сначала запустите setup.sh для основного режима REALITY"
    fi
}

# --------------------------------------------------------------------------- #
# Конфиг XRay для WS-режима                                                   #
# --------------------------------------------------------------------------- #
write_ws_config() {
    mkdir -p "$INSTALL_DIR/config-cdn"

    cat > "$INSTALL_DIR/config-cdn/config.json" <<EOF
{
  "log": { "loglevel": "warning",
           "access": "/var/log/xray/access-cdn.log",
           "error":  "/var/log/xray/error-cdn.log" },
  "inbounds": [
    {
      "listen":   "127.0.0.1",
      "port":     ${XRAY_WS_PORT},
      "protocol": "vless",
      "settings": {
        "clients": [{ "id": "${CLIENT_UUID}", "flow": "", "email": "cdn-user@vpn" }],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "ws",
        "security": "none",
        "wsSettings": { "path": "${WS_PATH}", "headers": {} }
      },
      "sniffing": { "enabled": true, "destOverride": ["http","tls","quic"] }
    }
  ],
  "outbounds": [
    { "protocol": "freedom", "tag": "direct",
      "settings": { "domainStrategy": "UseIPv4" } },
    { "protocol": "blackhole", "tag": "block" }
  ],
  "routing": {
    "rules": [{ "type": "field", "ip": ["geoip:private"], "outboundTag": "block" }]
  }
}
EOF
    ok "XRay WS конфиг → $INSTALL_DIR/config-cdn/config.json"
}

# --------------------------------------------------------------------------- #
# Docker Compose для WS-контейнера                                             #
# --------------------------------------------------------------------------- #
write_ws_compose() {
    cat > "$INSTALL_DIR/docker-compose-cdn.yml" <<EOF
version: "3.8"
services:
  xray-cdn:
    image: ghcr.io/xtls/xray-core:latest
    container_name: xray-cdn
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./config-cdn:/etc/xray:ro
      - xray-logs:/var/log/xray
    command: ["xray", "run", "-c", "/etc/xray/config.json"]
    ulimits:
      nofile: { soft: 65536, hard: 65536 }
    healthcheck:
      test: ["CMD-SHELL", "pgrep -x xray > /dev/null || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  xray-logs:
    driver: local
EOF
    ok "docker-compose-cdn.yml создан"
}

# --------------------------------------------------------------------------- #
# Nginx: TLS-терминация + проксирование на XRay WS                            #
# --------------------------------------------------------------------------- #
configure_nginx() {
    info "Настраиваю Nginx..."

    # Временный конфиг для получения сертификата
    cat > "/etc/nginx/sites-available/xray-cdn" <<EOF
server {
    listen 80;
    server_name ${CDN_DOMAIN};
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl http2;
    server_name ${CDN_DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${CDN_DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${CDN_DOMAIN}/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # Скрываем заголовки, выдающие proxy
    proxy_hide_header X-Powered-By;
    server_tokens off;

    # Путь для XRay WebSocket
    location ${WS_PATH} {
        proxy_pass         http://127.0.0.1:${XRAY_WS_PORT};
        proxy_http_version 1.1;
        proxy_set_header   Upgrade \$http_upgrade;
        proxy_set_header   Connection "upgrade";
        proxy_set_header   Host \$host;
        proxy_set_header   X-Real-IP \$remote_addr;
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }

    # Все остальные запросы — фейковая страница (защита от active probing)
    location / {
        root /var/www/html;
        try_files \$uri \$uri/ =404;
    }
}
EOF

    ln -sf /etc/nginx/sites-available/xray-cdn /etc/nginx/sites-enabled/xray-cdn
    rm -f /etc/nginx/sites-enabled/default
    ok "Nginx конфиг создан"
}

# --------------------------------------------------------------------------- #
# TLS-сертификат через Let's Encrypt                                           #
# --------------------------------------------------------------------------- #
obtain_certificate() {
    info "Получаю TLS-сертификат для $CDN_DOMAIN ..."

    # Временно даём Nginx работать на 80 без SSL для certbot
    cat > "/etc/nginx/sites-available/xray-cdn-temp" <<EOF
server {
    listen 80;
    server_name ${CDN_DOMAIN};
    root /var/www/html;
}
EOF
    ln -sf /etc/nginx/sites-available/xray-cdn-temp /etc/nginx/sites-enabled/xray-cdn
    nginx -t && systemctl reload nginx

    certbot certonly --nginx -d "$CDN_DOMAIN" --non-interactive --agree-tos \
        --email "admin@${CDN_DOMAIN}" --no-eff-email

    ok "Сертификат получен"

    # Устанавливаем финальный конфиг
    ln -sf /etc/nginx/sites-available/xray-cdn /etc/nginx/sites-enabled/xray-cdn
    nginx -t && systemctl reload nginx

    # Авторенев сертификата
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet && systemctl reload nginx") | crontab -
    ok "Автообновление сертификата настроено"
}

# --------------------------------------------------------------------------- #
# Запуск                                                                       #
# --------------------------------------------------------------------------- #
start_xray_cdn() {
    cd "$INSTALL_DIR"
    docker compose -f docker-compose-cdn.yml pull -q
    docker compose -f docker-compose-cdn.yml up -d
    sleep 2
    docker compose -f docker-compose-cdn.yml ps | grep -q "Up" && ok "XRay CDN запущен" || {
        docker compose -f docker-compose-cdn.yml logs --tail=20
        die "XRay CDN не стартовал"
    }
}

# --------------------------------------------------------------------------- #
# Клиентский конфиг                                                            #
# --------------------------------------------------------------------------- #
write_cdn_client() {
    CDN_CLIENT_DIR="$INSTALL_DIR/clients/cdn"
    mkdir -p "$CDN_CLIENT_DIR"

    # VLESS URI для CDN-режима (WebSocket + TLS через Cloudflare)
    CDN_URI="vless://${CLIENT_UUID}@${CDN_DOMAIN}:443"
    CDN_URI+="?encryption=none"
    CDN_URI+="&flow="
    CDN_URI+="&security=tls"
    CDN_URI+="&sni=${CDN_DOMAIN}"
    CDN_URI+="&fp=chrome"
    CDN_URI+="&type=ws"
    CDN_URI+="&path=$(python3 -c "import urllib.parse; print(urllib.parse.quote('${WS_PATH}'))")"
    CDN_URI+="&host=${CDN_DOMAIN}"
    CDN_URI+="#CDN-${CDN_DOMAIN}"

    echo "$CDN_URI" > "$CDN_CLIENT_DIR/client.uri"

    cat > "$CDN_CLIENT_DIR/manual-params.txt" <<EOF
=== VLESS+WS+TLS (CDN режим) ===

Адрес:          ${CDN_DOMAIN}
Порт:           443
UUID:           ${CLIENT_UUID}
Шифрование:     none
Flow:           (пусто — vision не нужен для WS)
Транспорт:      WebSocket
Path:           ${WS_PATH}
Host:           ${CDN_DOMAIN}
TLS:            tls (НЕ reality)
SNI:            ${CDN_DOMAIN}
Fingerprint:    chrome

ВАЖНО: В Cloudflare DNS запись для ${CDN_DOMAIN} должна быть Proxied (оранжевое облако)
EOF

    ok "CDN клиентские конфиги → $CDN_CLIENT_DIR/"

    if command -v qrencode &>/dev/null; then
        qrencode -t PNG -o "$CDN_CLIENT_DIR/qr-code.png" "$CDN_URI"
        echo ""
        info "QR для CDN режима:"
        qrencode -t ANSIUTF8 "$CDN_URI"
    else
        echo ""
        info "CDN VLESS URI:"
        echo "$CDN_URI"
    fi
}

# --------------------------------------------------------------------------- #
# MAIN                                                                         #
# --------------------------------------------------------------------------- #
main() {
    echo ""
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  VLESS+WS+TLS CDN Fronting Setup  |  Cloudflare режим    ${NC}"
    echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    info "Домен: $CDN_DOMAIN"
    info "WS путь: $WS_PATH"
    echo ""

    install_deps
    load_or_generate_params
    write_ws_config
    write_ws_compose
    configure_nginx
    obtain_certificate
    start_xray_cdn
    write_cdn_client

    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║         VLESS+WS+TLS CDN развёрнут успешно!             ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Cloudflare CDN:  ${CYAN}${CDN_DOMAIN}:443${NC}"
    echo -e "  WS Path:         ${CYAN}${WS_PATH}${NC}"
    echo -e "  Режим:           ${CYAN}VLESS + WebSocket + TLS (Cloudflare)${NC}"
    echo ""
    echo -e "  ${YELLOW}Убедитесь что в Cloudflare DNS:${NC}"
    echo -e "  A  ${CDN_DOMAIN}  →  ${SERVER_IP:-YOUR_VPS_IP}  (Proxied = оранжевое облако)${NC}"
    echo ""
}

main "$@"
