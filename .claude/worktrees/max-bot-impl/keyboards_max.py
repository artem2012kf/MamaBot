# keyboards_max.py
"""Клавиатуры для бота в мессенджере MAX.

Код почти идентичен `keyboards.py`, но использует типы из `maxapi.types`
(InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton,
ReplyKeyboardRemove)."""

from maxapi.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

# ---------------------------------------------------------------------------
# Основные inline‑клавиатуры (для группового чата и личных сообщений)
# ---------------------------------------------------------------------------

start_kb = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Я иду", callback_data="Я иду"),
            InlineKeyboardButton(text="Я не иду", callback_data="Я не иду"),
        ],
        [
            InlineKeyboardButton(text="+ Мужчина", callback_data="+ Мужчина"),
            InlineKeyboardButton(text="- Мужчина", callback_data="- Мужчина"),
        ],
        [
            InlineKeyboardButton(text="+ Девушка", callback_data="+ Девушка"),
            InlineKeyboardButton(text="- Девушка", callback_data="- Девушка"),
        ],
    ]
)

# ---------------------------------------------------------------------------
# Reply‑клавиатура (для приватных сообщений, если понадобится)
# ---------------------------------------------------------------------------

start_kb2 = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Я иду"), KeyboardButton(text="Я не иду")],
        [KeyboardButton(text="+ Муж"), KeyboardButton(text="- Муж")],
        [KeyboardButton(text="+ Дев"), KeyboardButton(text="- Дев")],
        [KeyboardButton(text="Список")],
    ],
    resize_keyboard=True,
)

# ---------------------------------------------------------------------------
# Inline‑клавиатура для личных сообщений (префикс «pm_» сохраняем)
# ---------------------------------------------------------------------------

start_kb_private = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Я иду", callback_data="pm_я иду"),
            InlineKeyboardButton(text="Я не иду", callback_data="pm_я не иду"),
        ],
        [
            InlineKeyboardButton(text="+ Мужчина", callback_data="pm_+ муж"),
            InlineKeyboardButton(text="- Мужчина", callback_data="pm_- муж"),
        ],
        [
            InlineKeyboardButton(text="+ Девушка", callback_data="pm_+ дев"),
            InlineKeyboardButton(text="- Девушка", callback_data="pm_- дев"),
        ],
        [
            InlineKeyboardButton(text="📋 Список", callback_data="pm_список"),
        ],
    ]
)

# ---------------------------------------------------------------------------
# Дополнительные клавиатуры, используемые в разных хэндлерах
# ---------------------------------------------------------------------------

drug = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Записать друга", callback_data="Записать друга")]]
)

drugdel = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Удалить друга", callback_data="Удалить друга")]]
)

Def = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Перед тренеровкой", callback_data="Перед тренеровки")],
        [InlineKeyboardButton(text="После тренеровки", callback_data="После тренировки")],
    ]
)

sbor = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="В четверг", callback_data="В четверг")],
        [InlineKeyboardButton(text="В воскресенье", callback_data="В воскресенье")],
    ]
)

tren = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Отправить", callback_data="Отправить")]]
)

admin_panel = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Сбросить таблицу", callback_data="Сбросить таблицу")],
        [InlineKeyboardButton(text="Все функции", callback_data="Все функции")],
        [InlineKeyboardButton(text="Удалить пользователя", callback_data="Удалить пользователя")],
        [InlineKeyboardButton(text="Добавить пользователя", callback_data="Добавить пользователя")],
    ]
)

admin_panel1 = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="👨‍👩‍👦‍👦 Пользователи", callback_data="users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="statistics")],
        [
            InlineKeyboardButton(text="⛔️ Блокировка", callback_data="block_user"),
            InlineKeyboardButton(text="✅ Разблокировка", callback_data="unlock_user"),
        ],
    ]
)

# Клавиатура для выбора пола при добавлении «друга»

drug_gender = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Мужчина", callback_data="+drug_boy"),
                      InlineKeyboardButton(text="Женщина", callback_data="+drug_girl")]]
)
