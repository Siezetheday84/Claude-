# Android-клиент — v2rayNG / Hiddify

## Рекомендуемые приложения

| Приложение | Ссылка | Особенности |
|------------|--------|-------------|
| **v2rayNG** | Google Play / GitHub Releases | Классика, стабильно |
| **Hiddify Next** | Google Play / GitHub | Современный UI, sing-box внутри |
| **NekoBox** | GitHub Releases | Поддержка REALITY |

---

## v2rayNG — настройка через QR-код

1. Откройте `clients/qr-code.png` на сервере или получите его любым способом
2. В v2rayNG нажмите **+** → **Сканировать QR-код**
3. Готово — нажмите значок самолёта для подключения

## v2rayNG — настройка через URI

1. Скопируйте содержимое файла `clients/client.uri` (строка `vless://...`)
2. В v2rayNG: **+** → **Импортировать конфигурацию из буфера обмена**

## v2rayNG — ручная настройка

**+** → **Ввести вручную** → выбрать **VLESS**

| Поле | Значение из `manual-params.txt` |
|------|---------------------------------|
| Адрес | `SERVER_IP` |
| Порт | `443` |
| UUID | `CLIENT_UUID` |
| Flow | `xtls-rprx-vision` |
| Транспорт | `tcp` |
| TLS | `reality` |
| SNI | `microsoft.com` |
| uTLS/Fingerprint | `chrome` |
| Public Key | `PUBLIC_KEY` |
| Short ID | `SHORT_ID` |

---

## Hiddify Next — настройка

1. Нажмите **+** → **Добавить по ссылке**
2. Вставьте VLESS URI из `clients/client.uri`

---

## Проверка работы

После подключения убедитесь, что:
- `https://whoer.net` показывает IP вашего VPS, а не российский
- `https://web.telegram.org` открывается без proxy
- Telegram в фоне работает через VPN (убедитесь, что VPN поднят **до** запуска Telegram)

---

## Важно: VPN должен стартовать до Telegram

В v2rayNG: **Настройки** → **VPN Mode** → включить **Always-On VPN** в системных настройках Android:

`Настройки → Сеть → VPN → v2rayNG → Всегда включён VPN`

Это гарантирует, что Telegram никогда не пойдёт в обход VPN.
