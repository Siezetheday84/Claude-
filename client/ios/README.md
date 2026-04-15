# iOS-клиент — Streisand / Hiddify

## Рекомендуемые приложения

| Приложение | Ссылка | Особенности |
|------------|--------|-------------|
| **Streisand** | App Store | Платное, лучший UX, поддержка REALITY |
| **Hiddify Next** | App Store | Бесплатное, sing-box, REALITY |
| **FoXray** | App Store | Платное, v2ray-based |
| **V2Box** | App Store | Бесплатное |

---

## Streisand — настройка

1. Откройте Streisand → вкладка **Серверы** → **+**
2. Выберите **Сканировать QR** или **Вставить из буфера**
3. Вставьте VLESS URI из `clients/client.uri`
4. Нажмите **Подключиться**

Streisand автоматически распознаёт VLESS+REALITY и выставляет правильные параметры.

---

## Hiddify Next — настройка

1. **+** → **Добавить по ссылке**
2. Вставьте VLESS URI

---

## Ручная настройка (Streisand / FoXray)

Создайте новый сервер с типом **VLESS** и укажите параметры из `clients/manual-params.txt`:

| Параметр | Значение |
|----------|---------|
| Host | `SERVER_IP` |
| Port | `443` |
| UUID | `CLIENT_UUID` |
| Flow | `xtls-rprx-vision` |
| Transport | `tcp` |
| Security | `reality` |
| SNI | `microsoft.com` |
| Fingerprint | `chrome` |
| Public Key | `PUBLIC_KEY` |
| Short ID | `SHORT_ID` |

---

## Always-On VPN на iOS

iOS поддерживает Always-On VPN только через MDM-профили (корпоративные устройства).  
Для личных устройств: **Настройки → VPN** → переключайте VPN вручную перед запуском Telegram.

Альтернатива: используйте **Streisand с виджетом** на экране блокировки для быстрого включения.

---

## Проверка

- `https://whoer.net` — IP должен быть вашим VPS
- `https://2ip.ru` — российского IP быть не должно
- Telegram открывается без каких-либо прокси внутри приложения
