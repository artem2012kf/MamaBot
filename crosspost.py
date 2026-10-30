"""crosspost.py — обновление списка сбора сразу в группах Telegram и MAX.

Telegram- и MAX-боты работают в разных процессах и используют несовместимые
библиотеки (aiogram 2 / maxapi), поэтому чужой мессенджер обновляется напрямую
через его HTTP API. ID последних сообщений со списком хранятся в общей таблице
bot_state (sbor.db), чтобы каждый процесс мог удалить предыдущий список,
отправленный другим процессом.

Сценарий:
- событие в Telegram: main.py обновляет сообщение в TG-группе, затем
  post_to_max() удаляет/отправляет список в MAX-группе;
- событие в MAX: max_main.py обновляет сообщение в MAX-группе, затем
  post_to_telegram() удаляет/отправляет список в TG-группе.
"""
import asyncio

import aiohttp

import utils
from config import API, API_MAX, GROUP_ID, GROUP_ID_MAX
from shared.logger import bot_logger as logger

MAX_API_URL = "https://platform-api.max.ru"
TELEGRAM_API_URL = "https://api.telegram.org"

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=15)

# Фоновые задачи кросс-поста: не блокируем обработчик события, если чужой
# мессенджер недоступен (например, Telegram API из этой сети отвечает таймаутом).
_background_tasks: set = set()


def spawn(coro) -> None:
    """Запустить кросс-пост в фоне, сохранив ссылку на задачу."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


# Кнопки анонса сбора: подписи и payload одинаковы для TG и MAX.
START_BUTTONS = [
    [("Я иду", "Я иду"), ("Я не иду", "Я не иду")],
    [("+ Мужчина", "+ Мужчина"), ("- Мужчина", "- Мужчина")],
    [("+ Девушка", "+ Девушка"), ("- Девушка", "- Девушка")],
]

# Тексты оповещений — общие для обоих ботов, чтобы не расходились.
SBOR_THURSDAY_TEXT = "Всем привет! Начинаем сбор на тренировку в четверг 19:00"
SBOR_SUNDAY_TEXT = "Всем привет! Начинаем сбор на тренировку в воскресенье 18:00"
FIN_TEXT = (
    "Всем спасибо за игру! Не забываем про оплату 😎.\n"
    "+79222694226\n(Сбер, ВТБ, Альфа) 170 руб."
)


def _telegram_markup(buttons):
    """Inline-клавиатура для Telegram API."""
    return {
        "inline_keyboard": [
            [{"text": text, "callback_data": payload} for text, payload in row]
            for row in buttons
        ]
    }


def _max_attachments(buttons):
    """Вложение inline_keyboard для MAX API."""
    return [
        {
            "type": "inline_keyboard",
            "payload": {
                "buttons": [
                    [
                        {"type": "callback", "text": text, "payload": payload}
                        for text, payload in row
                    ]
                    for row in buttons
                ]
            },
        }
    ]


async def send_telegram_message(text: str, buttons=None) -> int | None:
    """Отправить сообщение в Telegram-группу, вернуть message_id."""
    if not GROUP_ID:
        logger.warning("GROUP_ID не задан — отправка в Telegram пропущена")
        return None

    url = f"{TELEGRAM_API_URL}/bot{API}/sendMessage"
    payload = {"chat_id": GROUP_ID, "text": text, "parse_mode": "Markdown"}
    if buttons:
        payload["reply_markup"] = _telegram_markup(buttons)
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json(content_type=None)
                if not data.get("ok"):
                    description = data.get("description", "")
                    logger.warning(f"Telegram: не удалось отправить список: {description}")
                    # Markdown может сломаться на имени с '_' или '*' — повторяем без разметки
                    if "parse" in description.lower():
                        payload.pop("parse_mode", None)
                        async with session.post(url, json=payload) as retry:
                            retry_data = await retry.json(content_type=None)
                            if retry_data.get("ok"):
                                return retry_data.get("result", {}).get("message_id")
                    return None
                return data.get("result", {}).get("message_id")
    except Exception as error:
        logger.warning(
            f"Telegram: ошибка отправки списка: {type(error).__name__}: {error!r}"
        )
        return None


async def delete_telegram_message(message_id: int | str) -> None:
    """Удалить сообщение из Telegram-группы."""
    if not GROUP_ID:
        return

    url = f"{TELEGRAM_API_URL}/bot{API}/deleteMessage"
    payload = {"chat_id": GROUP_ID, "message_id": message_id}
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(url, json=payload) as response:
                data = await response.json(content_type=None)
                if not data.get("ok"):
                    logger.warning(
                        f"Telegram: не удалось удалить сообщение {message_id}: "
                        f"{data.get('description')}"
                    )
    except Exception as error:
        logger.warning(
            f"Telegram: ошибка удаления сообщения {message_id}: "
            f"{type(error).__name__}: {error!r}"
        )


async def send_max_message(text: str, buttons=None) -> str | None:
    """Отправить сообщение в MAX-группу, вернуть message_id (mid)."""
    if GROUP_ID_MAX is None:
        logger.warning("GROUP_ID_MAX не задан — отправка в MAX пропущена")
        return None

    headers = {"Authorization": API_MAX}
    params = {"chat_id": GROUP_ID_MAX}
    payload = {
        "text": text,
        "attachments": _max_attachments(buttons) if buttons else [],
    }
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.post(
                f"{MAX_API_URL}/messages",
                params=params,
                json=payload,
                headers=headers,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.warning(
                        f"MAX: не удалось отправить список (HTTP {response.status}): "
                        f"{body[:200]}"
                    )
                    return None
                data = await response.json(content_type=None)
                return data.get("message", {}).get("body", {}).get("mid")
    except Exception as error:
        logger.warning(f"MAX: ошибка отправки списка: {type(error).__name__}: {error!r}")
        return None


async def delete_max_message(message_id: str) -> None:
    """Удалить сообщение из MAX-группы."""
    if GROUP_ID_MAX is None:
        return

    headers = {"Authorization": API_MAX}
    params = {"message_id": message_id}
    try:
        async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
            async with session.delete(
                f"{MAX_API_URL}/messages",
                params=params,
                headers=headers,
            ) as response:
                if response.status not in (200, 204):
                    body = await response.text()
                    logger.warning(
                        f"MAX: не удалось удалить сообщение {message_id} "
                        f"(HTTP {response.status}): {body[:200]}"
                    )
    except Exception as error:
        logger.warning(
            f"MAX: ошибка удаления сообщения {message_id}: "
            f"{type(error).__name__}: {error!r}"
        )


async def post_to_max(list_text: str) -> None:
    """Обновить список в MAX-группе (вызывается из Telegram-бота)."""
    previous_mid = utils.get_state("max_list_message_mid")
    if previous_mid:
        await delete_max_message(previous_mid)

    mid = await send_max_message(list_text)
    if mid:
        utils.set_state("max_list_message_mid", mid)


async def post_to_telegram(list_text: str) -> None:
    """Обновить список в Telegram-группе (вызывается из MAX-бота)."""
    previous_id = utils.get_state("tg_list_message_id")
    if previous_id:
        await delete_telegram_message(previous_id)

    message_id = await send_telegram_message(list_text)
    if message_id:
        utils.set_state("tg_list_message_id", message_id)
