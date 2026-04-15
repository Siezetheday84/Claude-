# VLESS+REALITY Anti-DPI VPN

Self-hosted VPN на базе [XRay-core](https://github.com/XTLS/Xray-core) с протоколом **VLESS+REALITY**.  
Обходит ТСПУ/DPI в России (2025–2026): трафик неотличим от легитимного HTTPS к microsoft.com.

## Почему REALITY работает там, где другие нет

| Механизм ТСПУ | Обычный VPN | VLESS+REALITY |
|---------------|-------------|---------------|
| Protocol fingerprinting | Детектируется (WireGuard: 148 байт, OpenVPN handshake) | Не детектируется: handshake идентичен TLS 1.3 к реальному сайту |
| TLS fingerprinting | Детектируется (нестандартный ClientHello) | Fingerprint = chrome/safari (настраивается через uTLS) |
| Active probing | Сервер отвечает как VPN → блокировка | Сервер форвардит в `microsoft.com` → выглядит легитимно |
| SNI блокировка | SNI раскрывает VPN-домен | SNI = `microsoft.com` — не блокируется |
| IP-блокировка диапазонов | Коммерческие VPN заблокированы целыми ASN | Личный VPS на нестандартном IP |
| UDP-блокировка | WireGuard (UDP) ненадёжен с лета 2025 | TCP 443 — стандартный HTTPS-порт |

---

## Два режима работы

| Режим | Когда использовать | Скрипт |
|-------|-------------------|--------|
| **VLESS+REALITY** (основной) | IP сервера не заблокирован | `server/setup.sh` |
| **VLESS+WS+TLS** (CDN-фронтинг) | IP сервера заблокирован, есть домен в Cloudflare | `server/setup-cdn.sh` |

---

## Структура проекта

```
├── server/
│   ├── setup.sh                        # Основная установка (VLESS+REALITY)
│   ├── setup-cdn.sh                    # CDN-фронтинг через Cloudflare (VLESS+WS+TLS)
│   ├── docker-compose.yml              # Docker Compose для XRay
│   └── config/
│       ├── config.json.template        # Шаблон REALITY конфига
│       └── config-ws-tls.json.template # Шаблон WS+TLS конфига (CDN)
├── scripts/
│   ├── generate-keys.sh                # Генерация x25519 ключей и UUID
│   ├── generate-client-config.sh       # Генерация клиентских конфигов из secrets
│   ├── add-client.sh                   # Добавление нового клиента
│   └── revoke-client.sh                # Отзыв UUID клиента
└── client/
    ├── android/README.md               # Настройка v2rayNG / Hiddify (Android)
    └── ios/README.md                   # Настройка Streisand / Hiddify (iOS)
```

---

## Быстрый старт

### 1. Требования к VPS

- Ubuntu 22.04 / 24.04 или Debian 12
- Минимум: 1 vCPU, 512 MB RAM
- Внешний IP, **не** входящий в заблокированные диапазоны РКН
- Рекомендуемые хостинги: Hetzner, Contabo, OVH, Vultr (локации: Германия, Нидерланды, Финляндия)

### 2. Установка одной командой

```bash
curl -fsSL https://raw.githubusercontent.com/YOUR-REPO/main/server/setup.sh | sudo bash
```

Или клонируйте репозиторий:

```bash
git clone https://github.com/YOUR-REPO.git
cd xray-reality
sudo bash server/setup.sh
```

Скрипт автоматически:
1. Установит Docker
2. Сгенерирует x25519 ключи REALITY и UUID клиента
3. Создаст и запустит XRay-контейнер на порту 443
4. Настроит ufw (открыты только SSH + 443/tcp)
5. Сохранит клиентские конфиги в `/opt/xray-reality/clients/`
6. Выведет VLESS URI и QR-код для импорта в приложение

### 3. Настройка клиента

После установки в `/opt/xray-reality/clients/` появятся файлы:

| Файл | Назначение |
|------|-----------|
| `client.uri` | **VLESS URI** — основной файл для импорта (v2rayNG, Hiddify, Streisand) |
| `qr-code.png` | QR-код для сканирования в мобильном приложении |
| `singbox-outbound.json` | Outbound-блок для sing-box / Hiddify Next |
| `xray-client-config.json` | Полный конфиг XRay-core для десктопа (NekoBox, Nekoray) |
| `manual-params.txt` | Все параметры для ручной настройки |

**Android:** Откройте v2rayNG → **+** → **Импорт из буфера** → вставьте содержимое `client.uri`.  
Или: [Hiddify Next](https://github.com/hiddify/hiddify-next) → **+** → **Добавить по ссылке**.

**iOS:** [Streisand](https://apps.apple.com/app/streisand/id6450534064) → **+** → вставьте VLESS URI.  
Или: [Hiddify Next](https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532).

Подробные инструкции: [`client/android/README.md`](client/android/README.md) и [`client/ios/README.md`](client/ios/README.md).

---

## Настройка переменных (опционально)

Перед запуском `setup.sh` можно переопределить параметры:

```bash
export XRAY_PORT=443                    # порт (лучше оставить 443)
export REALITY_DEST="apple.com:443"     # сайт-«донор» TLS (должен быть TLS 1.3 + H2)
export REALITY_SNI="apple.com"          # SNI для клиентов
export INSTALL_DIR="/opt/xray-reality"  # директория установки
sudo bash server/setup.sh
```

**Хорошие сайты-доноры для REALITY_DEST:**
- `microsoft.com:443` — стабильно, не будет заблокирован
- `apple.com:443`
- `dl.google.com:443`
- `cloudflare.com:443`

---

## Управление сервером

```bash
cd /opt/xray-reality

# Статус
docker compose ps

# Логи в реальном времени
docker compose logs -f xray

# Перезапуск
docker compose restart xray

# Остановка
docker compose stop

# Обновление XRay до новой версии
docker compose pull && docker compose up -d

# Добавить нового клиента (редактирует config.json + перезапуск ~1 сек)
sudo bash scripts/add-client.sh user@example.com

# Отозвать клиента по UUID
sudo bash scripts/revoke-client.sh a1b2c3d4-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Пересоздать клиентские конфиги из secrets
bash scripts/generate-client-config.sh /opt/xray-reality/server-secrets.env
```

---

## Режим CDN-фронтинга (если IP сервера заблокирован)

Если прямой IP вашего VPS попал под блокировку — подключите CDN-фронтинг через Cloudflare. Трафик идёт через Cloudflare CDN, IP которого не блокируется.

**Требования:** домен, делегированный в Cloudflare (DNS-запись должна быть Proxied — оранжевое облако).

```bash
# Установить CDN-режим поверх основного
export CDN_DOMAIN="vpn.yourdomain.com"
sudo bash server/setup-cdn.sh
```

Скрипт:
1. Устанавливает Nginx + certbot
2. Получает TLS-сертификат от Let's Encrypt
3. Настраивает Nginx как TLS-терминатор с проксированием на XRay
4. Запускает XRay в WS-режиме на localhost
5. Генерирует клиентский конфиг для CDN-режима

Клиентские конфиги CDN режима сохраняются в `/opt/xray-reality/clients/cdn/`.

---

## Генерация ключей вручную

Если нужно пересоздать ключи (например, при компрометации):

```bash
bash scripts/generate-keys.sh --env
```

После получения новых значений обновите `/opt/xray-reality/config/config.json` и перезапустите сервер.

---

## Устранение неполадок

### VPN подключается, но Telegram не работает

Убедитесь, что VPN поднят **до** старта Telegram. В Android включите **Always-On VPN** (см. `client/android/README.md`).

### Active probing — сервер продолжает блокироваться

Смените `REALITY_DEST` и `REALITY_SNI` на другой крупный домен. Домен должен:
- Поддерживать TLS 1.3
- Поддерживать HTTP/2
- Быть физически доступен с вашего VPS (проверьте: `curl -v https://microsoft.com`)

### Как проверить, что XRay корректно маскируется

С машины в России:
```bash
# Если видите ответ microsoft.com без VPN-признаков — отлично
curl -v --resolve microsoft.com:443:YOUR_VPS_IP https://microsoft.com 2>&1 | grep -E "TLS|ssl|Server"
```

### Логи

```bash
docker exec xray-reality cat /var/log/xray/error.log
```

---

## Безопасность

- `server-secrets.env` содержит приватный ключ — **chmod 600**, не коммитьте в git
- Смените `SHORT_ID` при подозрении на компрометацию (без смены ключей): `scripts/generate-keys.sh --env`
- Отзывайте UUID клиента через `scripts/revoke-client.sh <uuid>` — не удаляйте вручную из config.json
- Порт 443 открыт публично — это норма, сервер выглядит как HTTPS-сайт
- Firewall: открыты только SSH и 443/tcp, всё остальное заблокировано

---

## Технические детали

**REALITY** (разработка XTLS) — расширение TLS, которое:
1. Использует реальный TLS-хендшейк с сертификатом `microsoft.com` (сервер форвардит соединение туда для нераспознанных клиентов)
2. Клиент аутентифицируется через x25519 ECDH + `shortId` — без изменения внешнего вида трафика
3. `xtls-rprx-vision` flow добавляет padding-рандомизацию размеров пакетов
4. `uTLS fingerprint: chrome` — ClientHello идентичен Chrome 120+

**Результат:** пассивный DPI видит стандартный TLS 1.3 хендшейк к microsoft.com. Active probing получает валидный HTTPS-ответ от microsoft.com.

---

## Альтернатива: Amnezia VPN

Если нужен GUI-клиент с минимальной настройкой — [Amnezia VPN](https://amnezia.org/) поддерживает:
- AmneziaWG (обфусцированный WireGuard)
- OpenVPN over Cloak
- Работает с тем же VPS

Установка: `docker run -d amneziavpn/amnezia-server` и используйте десктопный клиент для настройки.
