import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def generate_script(topic: str, industry: str, region: str = "") -> str:
    region_str = f" для региона {region}" if region else ""
    prompt = f"""Ты — профессиональный сценарист коротких вирусных видеороликов (Reels/Shorts).

Напиши сценарий для видеоролика на тему: «{topic}»
Отрасль клиента: {industry}{region_str}

Требования:
- Длительность: 30–60 секунд
- Формат: вертикальное видео (Reels/Shorts)
- Стиль: динамичный, актуальный, цепляющий
- Структура: крючок (0–3 сек) → основная часть → призыв к действию

Предоставь:
1. ОПИСАНИЕ РОЛИКА (2–3 предложения — суть и подача)
2. СЦЕНАРИЙ (текст за кадром / титры / действия на экране по секундам)
3. ВИЗУАЛЬНЫЕ ИДЕИ (что показываем на экране)
4. ХЭШТЕГИ (5–7 актуальных)

Пиши живо, конкретно, без воды."""

    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def generate_topics(industries: list[str], region: str = "") -> list[str]:
    industry_str = ", ".join(industries) if industries else "общая тематика"
    region_str = f" (регион: {region})" if region else ""
    prompt = f"""Ты — контент-стратег. Сгенерируй 10 актуальных тем для видеороликов (Reels/Shorts).

Отрасли клиента: {industry_str}{region_str}
Дата: актуальные темы на текущую неделю.

Темы должны быть:
- Привязаны к реальным новостям, трендам, событиям
- Релевантны указанным отраслям
- Подходить для короткого вирусного видео (30–60 сек)
- Разнообразны по формату (новость, тренд, лайфхак, инфоповод)

Формат ответа — нумерованный список, каждая тема в одну строку.
Только список, без пояснений."""

    message = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    lines = message.content[0].text.strip().split("\n")
    topics = []
    for line in lines:
        line = line.strip()
        if line and (line[0].isdigit() or line.startswith("-")):
            cleaned = line.lstrip("0123456789.-) ").strip()
            if cleaned:
                topics.append(cleaned)
    return topics[:10]
