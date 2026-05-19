# Lira Search Bot

## Быстрый старт на Railway

1. Загрузи все файлы в GitHub репозиторий
2. Зайди на railway.app → New Project → Deploy from GitHub
3. Railway сам запустит бота (24/7 бесплатно на Hobby плане)

## Обязательно перед запуском

В файле `config.py`:
- `ADMIN_ID` — твой Telegram ID (узнай у @userinfobot)

В файле `handlers/cabinet.py`:
- `BOT_USERNAME` — реальный username бота (без @)

## Функции
- Поиск свободных ников (6-7 символов бесплатно, 5 только Premium)  
- Premium: prefix до 3 символов, suffix до 1 символа
- Система попыток (6 каждые 12 часов)
- Оплата через Telegram Stars и CryptoBot (USDT)
- Промокоды
- TikTok рефералы (только доверенные пользователи)
- Поддержка с ответами администратора (/reply_ID)
- Антифлуд защита
- Полная админ панель

## CryptoBot
Токен в config.py → CRYPTOPAY_TOKEN
Убедись что бот добавлен в @CryptoBot: /pay
