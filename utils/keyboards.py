from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from config import INDUSTRIES, REGIONS


def contract_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Договор", callback_data="contract:contract")],
        [InlineKeyboardButton(text="🔄 Подписка", callback_data="contract:subscription")],
    ])


def industries_kb(selected: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for industry in INDUSTRIES:
        mark = "✅ " if industry in selected else ""
        rows.append([InlineKeyboardButton(
            text=f"{mark}{industry}",
            callback_data=f"industry:{industry}"
        )])
    rows.append([InlineKeyboardButton(text="➡️ Продолжить", callback_data="industry:done")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def regions_kb() -> InlineKeyboardMarkup:
    rows = []
    for region in REGIONS:
        rows.append([InlineKeyboardButton(text=region, callback_data=f"region:{region}")])
    rows.append([InlineKeyboardButton(text="🌍 Без привязки к региону", callback_data="region:none")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topics_kb(topics: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for i, topic in enumerate(topics, 1):
        rows.append([InlineKeyboardButton(
            text=f"{i}. {topic[:60]}{'...' if len(topic) > 60 else ''}",
            callback_data=f"topic:{i}"
        )])
    rows.append([InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def script_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Согласовать", callback_data="script:approve")],
        [InlineKeyboardButton(text="✏️ Написать правки", callback_data="script:revise")],
        [InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")],
    ])


def assets_done_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Всё загружено, начать производство", callback_data="assets:done")],
        [InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")],
    ])


def video_review_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять ролик", callback_data="video:accept")],
        [InlineKeyboardButton(text="✏️ Внести правки", callback_data="video:revise")],
        [InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")],
    ])


def final_accept_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Принять финальную версию", callback_data="video:final_accept")],
        [InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")],
    ])


def support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🙋 Подключить менеджера", callback_data="support:connect")],
    ])


def admin_client_kb(client_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"admin:confirm_payment:{client_id}")],
        [InlineKeyboardButton(text="📤 Загрузить ролик", callback_data=f"admin:upload_video:{client_id}")],
        [InlineKeyboardButton(text="📋 Выслать акт", callback_data=f"admin:send_act:{client_id}")],
    ])
