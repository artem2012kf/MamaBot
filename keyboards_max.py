"""Клавиатуры для MAX-бота (maxapi).

В MAX инлайн-клавиатура передаётся как вложение типа inline_keyboard,
поэтому каждая клавиатура — это Attachment с ButtonsPayload.
"""
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.intent import Intent
from maxapi.types.attachments.attachment import Attachment, ButtonsPayload
from maxapi.types.attachments.buttons.callback_button import CallbackButton


def btn(text: str, payload: str, intent: Intent | None = None) -> CallbackButton:
    """Создаёт callback-кнопку."""
    if intent is not None:
        return CallbackButton(text=text, payload=payload, intent=intent)
    return CallbackButton(text=text, payload=payload)


def inline_keyboard(*rows) -> Attachment:
    """Собирает клавиатуру из рядов кнопок: inline_keyboard(ряд1, ряд2, ...)."""
    return Attachment(
        type=AttachmentType.INLINE_KEYBOARD,
        payload=ButtonsPayload(buttons=[list(row) for row in rows]),
    )


# Клавиатура старта (для группового чата) — только запись/отмена.
# Добавление/удаление друзей доступно только в личных сообщениях (start_kb_private).
start_kb = inline_keyboard(
    [
        btn("Я иду", "Я иду", Intent.POSITIVE),
        btn("Я не иду", "Я не иду", Intent.NEGATIVE),
    ],
)

# Клавиатура старта (для личных сообщений) — аналог start_kb_private
start_kb_private = inline_keyboard(
    [
        btn("Я иду", "pm_я иду", Intent.POSITIVE),
        btn("Я не иду", "pm_я не иду", Intent.NEGATIVE),
    ],
    [
        btn("+ Мужчина", "pm_+ муж"),
        btn("- Мужчина", "pm_- муж"),
    ],
    [
        btn("+ Девушка", "pm_+ дев"),
        btn("- Девушка", "pm_- дев"),
    ],
    [
        btn("📋 Список", "pm_список"),
    ],
)

# Выбор пола при добавлении человека через текст "+ Имя" — аналог drug
drug = inline_keyboard(
    [
        btn("Мужчина", "+drug_boy"),
        btn("Женщина", "+drug_girl"),
    ],
)

# Кнопки "Все функции" — аналог Def
Def = inline_keyboard(
    [
        btn("Перед тренеровкой", "Перед тренеровки"),
    ],
    [
        btn("После тренеровки", "После тренеровки"),
    ],
)

# Выбор дня для старта сбора — аналог sbor
sbor_kb = inline_keyboard(
    [
        btn("В четверг", "В четверг"),
    ],
    [
        btn("В воскресенье", "В воскресенье"),
    ],
)

# Отправка сообщения после тренировки — аналог tren
tren = inline_keyboard(
    [
        btn("Отправить", "Отправить"),
    ],
)

# Панель администратора (/admin) — аналог admin_panel
admin_panel = inline_keyboard(
    [
        btn("Сбросить таблицу", "Сбросить таблицу"),
    ],
    [
        btn("Все функции", "Все функции"),
    ],
    [
        btn("Удалить пользователя", "Удалить пользователя"),
    ],
    [
        btn("Добавить пользователя", "Добавить пользователя"),
    ],
)

# Панель администратора (/admin1) — аналог admin_panel1
admin_panel1 = inline_keyboard(
    [
        btn("👨‍👩‍👦‍👦 Пользователи", "users"),
    ],
    [
        btn("📊 Статистика", "statistics"),
    ],
    [
        btn("⛔️ Блокировка", "block_user", Intent.NEGATIVE),
        btn("✅ Разблокировка", "unlock_user", Intent.POSITIVE),
    ],
)

# Кнопка оплаты для админов — аналог payment_keyboard
payment_keyboard = inline_keyboard(
    [
        btn("💳 Оплатить", "oplata_done", Intent.POSITIVE),
    ],
)
