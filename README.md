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

## Структура проекта

```
├── server/
│   ├── setup.sh                    # Полная автоматическая установка
│   ├── docker-compose.yml          # Docker Compose для XRay
│   └── config/
│       └── config.json.template    # Шаблон конфига (для ручной настройки)
├── scripts/
│   ├── generate-keys.sh            # Генерация x25519 ключей и UUID
│   ├── generate-client-config.sh   # Генерация клиентских конфигов из secrets
│   └── add-client.sh               # Добавление нового клиента
└── client/
    ├── android/README.md           # Настройка v2rayNG / Hiddify (Android)
    └── ios/README.md               # Настройка Streisand / Hiddify (iOS)
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

**Android:** Импортируйте QR или URI в [v2rayNG](https://github.com/2dust/v2rayNG) или [Hiddify](https://github.com/hiddify/hiddify-next).  
**iOS:** Используйте [Streisand](https://apps.apple.com/app/streisand/id6450534064) или [Hiddify](https://apps.apple.com/app/hiddify-proxy-vpn/id6596777532).

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

# Добавить нового клиента
sudo bash /opt/xray-reality/../scripts/add-client.sh user@example.com

# Пересоздать клиентские конфиги
bash scripts/generate-client-config.sh /opt/xray-reality/server-secrets.env
```

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
- Смените `SHORT_ID` при подозрении на компрометацию (без смены ключей)
- Ротируйте UUID клиента при необходимости отозвать доступ: `scripts/add-client.sh`
- Порт 443 открыт публично — это норма, сервер выглядит как HTTPS-сайт

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
