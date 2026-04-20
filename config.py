import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///video_service.db")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
ADMIN_IDS = [
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
]

INDUSTRIES = [
    "Недвижимость",
    "Авто",
    "Ритейл",
    "Финансы",
    "Медицина и здоровье",
    "Образование",
    "Технологии",
    "Туризм и путешествия",
    "Мода и красота",
    "Спорт",
    "Строительство",
    "Юридические услуги",
    "Ресторанный бизнес",
    "Маркетинг и реклама",
    "Другое",
]

REGIONS = [
    "Москва",
    "Санкт-Петербург",
    "Екатеринбург",
    "Новосибирск",
    "Казань",
    "Нижний Новгород",
    "Краснодар",
    "Ростов-на-Дону",
    "Вся Россия",
    "СНГ",
    "Международный",
]

TOPICS_SEND_DAY = 0      # Monday
TOPICS_SEND_HOUR = 11
TOPICS_SEND_MINUTE = 0
TOPIC_DEADLINE_DAY = 1   # Tuesday
TOPIC_DEADLINE_HOUR = 10
TOPIC_DEADLINE_MINUTE = 0
PRODUCTION_HOURS = 48
