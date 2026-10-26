"""max_main.py — бот для мессенджера MAX (maxapi), полный аналог main.py (Telegram).

Работает с базами данных sbor.db и database.db. Сейчас запущен ЕДИНСТВЕННЫМ
(Telegram-бот выключен): python max_main.py. Когда Telegram-бот снова включится,
оба процесса будут читать те же общие базы — настройка WAL/busy_timeout в
shared/db.py это уже поддерживает.

Особенности API MAX (в отличие от Telegram/aiogram):
- события подписываются через @dp.message_created(...) и @dp.message_callback(...);
- инлайн-клавиатура передаётся вложением (см. keyboards_max.py);
- удаление сообщения — только по message_id, без chat_id;
- форматирование текста — через параметр format (Format.MARKDOWN / Format.HTML).

Устойчивость:
- polling перезапускается после сетевых сбоев с экспоненциальной задержкой;
- глобальный обработчик ошибок (@dp.errors) не даёт одному хэндлеру уронить бота;
- graceful shutdown по SIGTERM/SIGINT (остановит планировщик и закроет сессию).
"""
import asyncio
import os
import signal
import sys
from datetime import datetime

import aioschedule

from maxapi import Bot, Dispatcher, F
from maxapi.enums.chat_type import ChatType
from maxapi.exceptions import InvalidToken, MaxApiError, MaxError
from maxapi.filters import BaseFilter
from maxapi.filters.command import Command
from maxapi.types.error_event import ErrorEvent as MaxErrorEvent
from maxapi.types.updates.message_callback import MessageCallback
from maxapi.types.updates.message_created import MessageCreated

try:
    from config import API_MAX, GROUP_ID_MAX, admins_max, pol_max
except ImportError:
    # config.py не обязателен: значения можно передать переменными окружения
    # (удобно на хостинге, где секреты хранят в env, а не в файле).
    def _env_ints(name: str) -> list[int]:
        raw = os.environ.get(name, "")
        return [int(x) for x in raw.replace(";", ",").split(",") if x.strip()]

    API_MAX = os.environ.get("MAX_TOKEN", "")
    GROUP_ID_MAX = int(os.environ.get("MAX_GROUP_ID", "0"))
    admins_max = _env_ints("MAX_ADMIN_IDS")
    pol_max = _env_ints("MAX_POL_IDS")

    if not API_MAX:
        sys.exit(
            "MAX-бот: нет config.py и не задан токен. Скопируйте "
            "config.example.py в config.py ИЛИ задайте переменные окружения "
            "MAX_TOKEN, MAX_GROUP_ID, MAX_ADMIN_IDS (см. run_max.py)."
        )
from keyboards_max import (
    Def,
    admin_panel,
    admin_panel1,
    drug,
    payment_keyboard,
    sbor_kb,
    start_kb,
    start_kb_private,
    tren,
)
import utils
import active
from shared.logger import bot_logger as logger

from maxapi.context.base import BaseContext
from maxapi.context.state_machine import State, StatesGroup


class ShowList(StatesGroup):
    waiting = State()
    waiting2 = State()


class UserState1(StatesGroup):
    id = State()
    id1 = State()


class AddPersonState(StatesGroup):
    waiting_gender = State()


# ---------------------------------------------
bot = Bot(token=API_MAX)
dp = Dispatcher()
SKIP_NEXT_FIN_FILE = "skip_next_fin_message.flag"


def mark_next_fin_message_cancelled():
    with open(SKIP_NEXT_FIN_FILE, "w", encoding="utf-8") as file:
        file.write(datetime.now().isoformat())


def consume_next_fin_message_cancelled():
    """Проверяет флаг отмены и УДАЛЯЕТ его (одноразовое потребление).

    Пока Telegram-бот выключен, MAX-бот — единственный потребитель флага,
    поэтому он сам очищает файл после проверки. Иначе «Отмена» повлияла бы
    на все последующие рассылки, а не только на ближайшую.
    """
    if not os.path.exists(SKIP_NEXT_FIN_FILE):
        return False

    try:
        os.remove(SKIP_NEXT_FIN_FILE)
    except OSError as error:
        logger.warning(f"Не удалось удалить файл отмены сообщения об оплате: {error}")

    return True


def clear_next_fin_message_cancelled():
    if not os.path.exists(SKIP_NEXT_FIN_FILE):
        return False

    os.remove(SKIP_NEXT_FIN_FILE)
    return True


# ---------- Вспомогательные функции и фильтры ----------
class TextEquals(BaseFilter):
    """Фильтр: текст сообщения равен одному из значений (без учёта регистра)."""

    def __init__(self, *values: str):
        self.values = [v.strip().casefold() for v in values]

    async def __call__(self, event):
        if not isinstance(event, MessageCreated):
            return False
        body = event.message.body
        text = body.text if body is not None else None
        if not text:
            return False
        return text.strip().casefold() in self.values


class TextStartsWith(BaseFilter):
    """Фильтр: текст сообщения начинается с префикса и длиннее одного символа."""

    def __init__(self, prefix: str):
        self.prefix = prefix

    async def __call__(self, event):
        if not isinstance(event, MessageCreated):
            return False
        body = event.message.body
        text = body.text if body is not None else None
        if not text:
            return False
        text = text.strip()
        return text.startswith(self.prefix) and len(text) > 1


class BlockedUserFilter(BaseFilter):
    """Фильтр: отправитель сообщения заблокирован (регистрируется последним)."""

    async def __call__(self, event):
        if not isinstance(event, MessageCreated):
            return False
        sender = event.message.sender
        if sender is None:
            return False
        return active.check_user_in_block(id_max=sender.user_id)


def full_name(user) -> str:
    """Имя пользователя в том же формате, что и в Telegram-боте.

    TG-бот (main.py) формирует имя только из first_name (+ last_name),
    без username — поэтому здесь тоже first_name: имена в sbor.db и Users
    остаются одинаковыми для одного человека в обоих мессенджерах.
    """
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return name


def get_gender_max(user) -> str | None:
    """Определяет пол пользователя MAX по общей таблице Users.

    Порядок поиска (в MAX нет юзернеймов, поэтому ссылаемся на id_max):
      1. по id_max — если человек уже регистрировался через MAX-бота;
      2. по полному имени (first_name + last_name) — если он записан только
         через Telegram-бота; найденную запись при этом привязываем к id_max;
      3. иначе None (пол неизвестен).
    """
    g = active.gender(id_max=user.user_id)
    if g is not None:
        return g
    name = full_name(user)
    row = utils.find_user_by_name(name)
    if row is not None:
        # Привязываем MAX-id к существующей записи пользователя из Telegram
        # (username из строки TG не трогаем — в MAX юзернеймов нет).
        active.add_user(id_tg=row[0], id_max=user.user_id)
        return active.gender(id_max=user.user_id)
    return None


async def cb_dismiss(cb: MessageCallback):
    """Закрывает "часики" на кнопке (аналог call.answer() в aiogram)."""
    try:
        await bot.send_callback(callback_id=cb.callback.callback_id, message=None)
    except Exception as e:
        logger.warning(f"Не удалось ответить на callback: {e}")


async def cb_notify(cb: MessageCallback, text: str):
    """Показывает уведомление при нажатии кнопки (аналог call.answer(text))."""
    try:
        await bot.send_callback(
            callback_id=cb.callback.callback_id, notification=text
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление callback: {e}")


async def reply_to_cb(cb: MessageCallback, text: str, attachments=None):
    """Отвечает в чат, где нажата кнопка.

    Если исходное сообщение уже удалено (cb.message is None), пишет в личку.
    """
    if cb.message is not None:
        await cb.message.answer(text, attachments=attachments)
    else:
        await bot.send_message(
            user_id=cb.callback.user.user_id, text=text, attachments=attachments
        )


async def check_and_handle_block_user(user_id: int, event) -> bool:
    """Проверка блокировки: отправляет сообщение и возвращает True, если заблокирован."""
    if active.check_user_in_block(id_max=user_id):
        logger.info(f"Пользователь {user_id} заблокирован.")
        if isinstance(event, MessageCreated):
            await event.message.answer("Вы заблокированы")
        else:
            await cb_notify(event, "Вы заблокированы")
        return True
    return False


async def log_action(event, action_type: str):
    """Логирует действие пользователя (для сообщений и колбэков)."""
    if isinstance(event, MessageCreated):
        user = event.message.sender
    else:
        user = event.callback.user
    if user is None:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(
        f"{timestamp} - User ID: {user.user_id} Username: {user.username} "
        f"First Name: {user.first_name} - Action: {action_type} [MAX]"
    )


# Хранилище ID последних сообщений со списком (message_id в MAX — строка)
last_list_messages = {}


async def send_updated_list(chat_id: int | None):
    """Отправляет обновлённый список в чат и удаляет предыдущий."""
    if chat_id is None:
        logger.warning("GROUP_ID_MAX не задан — список не отправлен")
        return

    if chat_id in last_list_messages:
        try:
            await bot.delete_message(last_list_messages[chat_id])
        except Exception:
            pass

    # Список отправляется без форматирования: разметка Markdown в MAX
    # отличается от Telegram и может ломаться на именах участников
    list_text = utils.select()
    sent = await bot.send_message(chat_id=chat_id, text=list_text)
    if sent.message is not None and sent.message.body is not None:
        last_list_messages[chat_id] = sent.message.body.mid


def require_group_chat_id():
    """Возвращает GROUP_ID_MAX или None с предупреждением в лог."""
    if GROUP_ID_MAX is None:
        logger.warning(
            "GROUP_ID_MAX не задан в config.py! "
            "Добавьте бота в групповой чат MAX и запустите get_max_chats.py"
        )
    return GROUP_ID_MAX


# ---------- Команды ----------
@dp.message_created(Command("start"))
async def start(event: MessageCreated):
    msg = event.message
    sender = msg.sender
    if sender is None:
        return
    if sender.user_id in pol_max:
        if await check_and_handle_block_user(sender.user_id, event):
            return
        await log_action(event, "Command: /start")
        if msg.recipient.chat_type == ChatType.DIALOG:
            await msg.answer("🏐 Запись на тренировку 🏐", attachments=[start_kb_private])
        else:
            await msg.answer("🏐 Запись на тренировку 🏐", attachments=[start_kb])
        gender = get_gender_max(sender)
        # В MAX нет юзернеймов — username остаётся только у Telegram-записей.
        active.add_user(id_max=sender.user_id, first_name=full_name(sender), gender=gender)
    else:
        await msg.answer("У вас нету доступа к боту")


@dp.message_created(Command("myid"))
async def myid(event: MessageCreated):
    """Вспомогательная команда: узнать свой MAX-идентификатор для config.py."""
    msg = event.message
    sender = msg.sender
    if sender is None:
        return
    await msg.answer(f"Ваш ID в MAX: {sender.user_id}")


@dp.message_created(Command("admin"))
async def admin_command(event: MessageCreated):
    msg = event.message
    sender = msg.sender
    if sender is None:
        return
    if await check_and_handle_block_user(sender.user_id, event):
        return
    await log_action(event, "Command: /admin")
    if sender.user_id in admins_max:
        await msg.answer("Добро пожаловать в админ-панель!", attachments=[admin_panel])
    else:
        await msg.answer("Вы не являетесь администратором.")


@dp.message_created(Command("admin1"))
async def admin1(event: MessageCreated):
    msg = event.message
    sender = msg.sender
    if sender is None:
        return
    if await check_and_handle_block_user(sender.user_id, event):
        return
    await log_action(event, "Command: /admin1")
    if sender.user_id in admins_max:
        await msg.answer("Вы открыли панель администратора", attachments=[admin_panel1])
    else:
        await msg.answer("Вы не администратор")


# ---------- Отмена сообщения "спасибо за тренировку" ----------
@dp.message_created(TextEquals("отмена"))
async def cancel_next_fin_message(event: MessageCreated, context: BaseContext):
    msg = event.message
    sender = msg.sender
    if sender is None or sender.user_id not in admins_max:
        return
    if await check_and_handle_block_user(sender.user_id, event):
        return

    mark_next_fin_message_cancelled()
    await context.clear()
    await log_action(event, "Отмена ближайшего сообщения спасибо за тренировку")
    await msg.answer("Ближайшее сообщение «Всем спасибо за игру!» не будет отправлено.")


@dp.message_created(TextEquals("отмена отмены"))
async def restore_next_fin_message(event: MessageCreated, context: BaseContext):
    msg = event.message
    sender = msg.sender
    if sender is None or sender.user_id not in admins_max:
        return
    if await check_and_handle_block_user(sender.user_id, event):
        return

    await context.clear()
    if clear_next_fin_message_cancelled():
        await log_action(event, "Отмена отмены ближайшего сообщения спасибо за тренировку")
        await msg.answer(
            "Отмена снята. Ближайшее сообщение «Всем спасибо за игру!» отправится по расписанию."
        )
    else:
        await msg.answer("Сейчас нет активной отмены для ближайшего сообщения.")


# ---------- Запись на тренировку ----------
@dp.message_callback(F.callback.payload == "Я иду")
async def buy1(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка я иду")
    await cb_dismiss(cb)

    username = full_name(user)
    gender_value = get_gender_max(user)

    if utils.check_user_exists(username):
        return
    utils.add(username, gender_value)
    await send_updated_list(require_group_chat_id())


@dp.message_callback(F.callback.payload == "Я не иду")
async def not_going(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка 'Я не иду'")
    await cb_dismiss(cb)

    username = full_name(user)
    if utils.check_user_exists(username):
        utils.del_one(username)
        await send_updated_list(require_group_chat_id())


# ---------- Управление друзьями ----------
@dp.message_callback(F.callback.payload == "+ Мужчина")
async def add_male_friend(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка + Муж")
    await cb_dismiss(cb)

    user_name = full_name(user)
    friend_name = utils.get_user_friend_name(user_name, "Муж")
    utils.add(friend_name, "Муж")
    await send_updated_list(require_group_chat_id())


@dp.message_callback(F.callback.payload == "+ Девушка")
async def add_female_friend(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка + Дев")
    await cb_dismiss(cb)

    user_name = full_name(user)
    friend_name = utils.get_user_friend_name(user_name, "Дев")
    utils.add(friend_name, "Дев")
    await send_updated_list(require_group_chat_id())


@dp.message_callback(F.callback.payload == "- Мужчина")
async def remove_male_friend(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка - Муж")
    await cb_dismiss(cb)

    user_name = full_name(user)
    if utils.check_friend_exists(user_name, "Муж"):
        utils.delete_one_friend(user_name, "Муж")
        await send_updated_list(require_group_chat_id())


@dp.message_callback(F.callback.payload == "- Девушка")
async def remove_female_friend(cb: MessageCallback):
    user = cb.callback.user
    if await check_and_handle_block_user(user.user_id, cb):
        return

    await log_action(cb, "Кнопка - Дев")
    await cb_dismiss(cb)

    user_name = full_name(user)
    if utils.check_friend_exists(user_name, "Дев"):
        utils.delete_one_friend(user_name, "Дев")
        await send_updated_list(require_group_chat_id())


# ---------- Добавление/удаление человека текстом "+ Имя" / "- Имя" ----------
@dp.message_created(TextStartsWith("+"), states=[None])
async def handle_add_person(event: MessageCreated, context: BaseContext):
    msg = event.message
    sender = msg.sender
    if sender is None or sender.user_id not in pol_max:
        return

    name = msg.body.text.strip()[1:].strip()
    await log_action(event, f"Запрос на добавление: {name}")

    await context.update_data(name=name)
    await msg.answer(f"📝 Выберите пол для: {name}", attachments=[drug])
    await context.set_state(AddPersonState.waiting_gender)


@dp.message_callback(
    F.callback.payload.in_({"+drug_boy", "+drug_girl"}),
    states=[AddPersonState.waiting_gender],
)
async def process_gender_selection(cb: MessageCallback, context: BaseContext):
    await cb_dismiss(cb)
    data = await context.get_data()
    name = data.get("name", "")
    gender = "Муж" if cb.callback.payload == "+drug_boy" else "Дев"

    await log_action(cb, f"Выбран пол ({gender}) для: {name}")

    utils.add(name, gender)
    await reply_to_cb(cb, f"✅ {name} ({gender}) успешно добавлен!")
    await send_updated_list(require_group_chat_id())
    logger.info(f"✅ Успешно добавлен: {name} | Пол: {gender}")

    await context.clear()


@dp.message_created(TextStartsWith("-"), states=[None])
async def handle_remove_person(event: MessageCreated):
    msg = event.message
    sender = msg.sender
    if sender is None or sender.user_id not in pol_max:
        return

    name = msg.body.text.strip()[1:].strip()
    await log_action(event, f"Запрос на удаление: {name}")

    if utils.check_user_exists(name):
        utils.delete(name)
        await msg.answer(f"❌ {name} удален из списка.")
        await send_updated_list(require_group_chat_id())
        logger.info(f"❌ Удален: {name} (по команде пользователя {sender.user_id})")
    else:
        await msg.answer(f"⚠️ {name} не найден в списке.")
        logger.warning(f"⚠️ Попытка удаления несуществующего пользователя: {name}")


# ---------- Оплата ----------
@dp.message_callback(F.callback.payload == "Оплатил")
async def oplata1(cb: MessageCallback):
    await cb_dismiss(cb)

    username = full_name(cb.callback.user)
    await log_action(cb, f"Нажал 'Оплатил', username: {username}")

    if utils.check_user_exists(username):
        utils.delete(username)
        await reply_to_cb(cb, "Спасибо! Ваша запись удалена.")
        await log_action(cb, f"Удалил {username}")
    elif utils.check_user_exists(username + " + 1"):
        utils.delete(username + " + 1")
        await reply_to_cb(cb, "Спасибо! Ваша запись (+1) удалена.")
        await log_action(cb, f"Удалил {username} + 1")
    else:
        await reply_to_cb(cb, "Вас нет в списке")


@dp.message_callback(F.callback.payload == "oplata_done")
async def payment_done(cb: MessageCallback):
    """При нажатии 'Оплатить' — удаляет сообщение и пишет подтверждение."""
    await cb_dismiss(cb)
    if cb.message is not None:
        try:
            await cb.message.delete()
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение об оплате: {e}")
    await bot.send_message(user_id=cb.callback.user.user_id, text="✅ Оплата прошла!")


# ---------- Информация о пользователях ----------
@dp.message_callback(F.callback.payload == "users")
async def users(cb: MessageCallback):
    await reply_to_cb(cb, active.show_users())
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "statistics")
async def statistics(cb: MessageCallback):
    await reply_to_cb(cb, f"Количество пользователей: {active.show_statistics()}")
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Пользователи")
async def show_users_list(cb: MessageCallback):
    await reply_to_cb(cb, "Вот список: ")
    await reply_to_cb(cb, active.show_users())
    await cb_dismiss(cb)


# ---------- Блокировка / разблокировка ----------
@dp.message_callback(F.callback.payload == "block_user")
async def block_user(cb: MessageCallback, context: BaseContext):
    await reply_to_cb(cb, "Введите id пользователя для блокировки (Telegram или MAX)")
    await context.set_state(UserState1.id)
    await cb_dismiss(cb)


@dp.message_created(states=[UserState1.id])
async def fsm_block(event: MessageCreated, context: BaseContext):
    msg = event.message
    input_id = msg.body.text if msg.body else None
    if input_id:
        if active.add_user_to_block(input_id):
            await msg.answer(f"Пользователь с id: {input_id.strip()}, был заблокирован")
        else:
            await msg.answer(f"Пользователь с id: {input_id.strip()} не найден в базе.")
    await context.clear()


@dp.message_callback(F.callback.payload == "unlock_user")
async def unlock_user(cb: MessageCallback, context: BaseContext):
    await reply_to_cb(cb, "Введите id пользователя для разблокировки (Telegram или MAX)")
    await context.set_state(UserState1.id1)
    await cb_dismiss(cb)


@dp.message_created(states=[UserState1.id1])
async def fsm_unlock(event: MessageCreated, context: BaseContext):
    msg = event.message
    input_id = msg.body.text if msg.body else None
    if input_id:
        if active.unlock_users(input_id):
            await msg.answer(f"Пользователь с id: {input_id.strip()}, был разблокирован")
        else:
            await msg.answer(f"Пользователь с id: {input_id.strip()} не найден в базе.")
    await context.clear()


# ---------- Админ-панель: действия ----------
@dp.message_callback(F.callback.payload == "Сбросить таблицу")
async def reset_table(cb: MessageCallback):
    await reply_to_cb(cb, "Таблица обновлена")
    await spisok1()
    utils.usersdel()
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Все функции")
async def all_functions(cb: MessageCallback):
    await reply_to_cb(cb, "Вот все функции", attachments=[Def])
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Перед тренеровки")
async def before_training(cb: MessageCallback):
    await reply_to_cb(cb, "Выберети день", attachments=[sbor_kb])
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "В четверг")
async def thursday(cb: MessageCallback):
    await reply_to_cb(cb, "Действие выполнено")
    await sbor11()
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "В воскресенье")
async def sunday(cb: MessageCallback):
    await reply_to_cb(cb, "Действие выполнено")
    await sbor22()
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "После тренеровки")
async def after_training(cb: MessageCallback):
    await reply_to_cb(cb, "Какой день?", attachments=[tren])
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Отправить")
async def send_now(cb: MessageCallback):
    await reply_to_cb(cb, "Действие выполнено")
    await fin1()
    await send_payment_request_to_admins()
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Добавить пользователя")
async def add_user_start(cb: MessageCallback, context: BaseContext):
    await reply_to_cb(cb, "Напишите имя пользователя")
    await context.set_state(ShowList.waiting)
    await cb_dismiss(cb)


@dp.message_callback(F.callback.payload == "Удалить пользователя")
async def del_user_start(cb: MessageCallback, context: BaseContext):
    await reply_to_cb(cb, "Напишите имя пользователя")
    await context.set_state(ShowList.waiting2)
    await cb_dismiss(cb)


@dp.message_created(states=[ShowList.waiting])
async def add_user_by_name(event: MessageCreated, context: BaseContext):
    msg = event.message
    username = msg.body.text if msg.body else ""
    if utils.check_user_exists(username):
        await bot.send_message(user_id=msg.sender.user_id, text="Такие данные уже есть")
    else:
        # В Telegram-версии здесь была ошибка (utils.add без пола) — добавляем с полом unknown
        utils.add(username, "unknown")
        await bot.send_message(user_id=msg.sender.user_id, text=f"{utils.select()}")
    await context.clear()


@dp.message_created(states=[ShowList.waiting2])
async def del_user_by_name(event: MessageCreated, context: BaseContext):
    msg = event.message
    username = msg.body.text if msg.body else ""
    if utils.check_user_exists(username):
        utils.delete(username)
        await bot.send_message(user_id=msg.sender.user_id, text=f"{utils.select()}")
    else:
        await bot.send_message(user_id=msg.sender.user_id, text="Таких данных нет.")
    await context.clear()


# ---------- Список в личных сообщениях ----------
@dp.message_callback(F.callback.payload == "pm_список")
async def show_list_private(cb: MessageCallback):
    if cb.callback.user.user_id not in pol_max:
        return
    if await check_and_handle_block_user(cb.callback.user.user_id, cb):
        return
    await log_action(cb, "Кнопка Список в личке")
    await cb_dismiss(cb)
    list_text = utils.select()
    await reply_to_cb(cb, list_text)


# ---------- Сообщения заблокированных пользователей (регистрируется последним!) ----------
@dp.message_created(BlockedUserFilter())
async def repeat(event: MessageCreated):
    await event.message.answer("Вы были заблокированы")


# ---------- Планировщик: рассылки (вызываются из run_both.py) ----------
async def sbor11():
    chat_id = require_group_chat_id()
    if chat_id is None:
        return
    await bot.send_message(chat_id=chat_id, text="Всем привет! Начинаем сбор на тренировку в четверг 19:00", attachments=[start_kb])


async def sbor22():
    chat_id = require_group_chat_id()
    if chat_id is None:
        return
    await bot.send_message(chat_id=chat_id, text="Всем привет! Начинаем сбор на тренировку в воскресенье 18:00", attachments=[start_kb])


async def fin1():
    chat_id = require_group_chat_id()
    if chat_id is None:
        return
    await bot.send_message(
        chat_id=chat_id,
        text="Всем спасибо за игру! Не забываем про оплату 😎.\n+79222694226\n(Сбер, ВТБ, Альфа) 170 руб.",
    )


async def scheduled_fin1():
    if consume_next_fin_message_cancelled():
        logger.info("Пропущено ближайшее сообщение спасибо за тренировку по команде Отмена")
        return

    await fin1()
    # Тренировка состоялась — отправляем список с кнопкой оплаты каждому админу
    await send_payment_request_to_admins()


async def spisok1():
    """Отправляет админу список тех, кто был на тренировке."""
    if len(admins_max) > 1:
        target = admins_max[1]
    else:
        target = admins_max[0]
    try:
        await bot.send_message(user_id=target, text=f"Вот кто был: {utils.select()}")
    except Exception as e:
        logger.warning(f"Не удалось отправить список админу {target}: {e}")


async def send_payment_request_to_admins():
    """Отправляет список участников и кнопку оплаты каждому админу."""
    list_text = utils.select()
    for admin_id in admins_max:
        try:
            await bot.send_message(
                user_id=admin_id,
                text=(
                    f"📋 Список участников тренировки:\n\n{list_text}\n\n"
                    "💳 Не забудьте оплатить!\n+79222694226\n(Сбер, ВТБ, Альфа) 170 руб."
                ),
                attachments=[payment_keyboard],
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение об оплате админу {admin_id}: {e}")


async def del1():
    utils.usersdel()
    for admin_id in admins_max[:2]:
        try:
            await bot.send_message(user_id=admin_id, text="Сброс сделан")
        except Exception as e:
            logger.warning(f"Не удалось отправить 'Сброс сделан' админу {admin_id}: {e}")


# ---------- Запуск ----------
async def register_scheduler():
    """Регистрация периодических задач MAX-бота.

    Сейчас работает только MAX-бот (Telegram-бот выключен), поэтому время
    рассылок совпадает с исходным расписанием из main.py. Когда Telegram-бот
    снова включится, сдвиньте эти времена на 1 минуту, чтобы два процесса не
    писали в общие базы SQLite в одну секунду.
    """
    aioschedule.every().monday.at("09:00").do(del1)
    aioschedule.every().friday.at("09:00").do(del1)
    aioschedule.every().wednesday.at("08:00").do(sbor11)
    aioschedule.every().saturday.at("08:00").do(sbor22)
    aioschedule.every().sunday.at("18:30").do(scheduled_fin1)
    aioschedule.every().thursday.at("19:30").do(scheduled_fin1)
    aioschedule.every().sunday.at("18:35").do(spisok1)
    aioschedule.every().thursday.at("19:35").do(spisok1)


async def scheduler_loop():
    """Фоновая задача планировщика.

    Каждая итерация обёрнута в try/except: ошибка одной рассылки (например,
    временный сбой API MAX или блокировка SQLite) не должна убивать цикл —
    иначе бот остался бы без напоминаний до самой перезагрузки процесса.
    """
    while True:
        try:
            await aioschedule.run_pending()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"Ошибка в планировщике MAX-бота: {e!r}", exc_info=True)
        try:
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise


@dp.errors()
async def global_error_handler(event: MaxErrorEvent):
    """Глобальный перехват ошибок обработчиков.

    Без него исключение внутри одного хэндлера могло привести к остановке
    всего polling; теперь ошибка пишется в bot.log, а бот продолжает работать
    (в том числе и Telegram-бот — они изолированы процессами).
    """
    logger.error(
        f"[MAX] Необработанная ошибка в обработчике: {event.exception!r} "
        f"(update={type(event.update).__name__})",
        exc_info=event.exception,
    )


def install_signal_handlers(stop_event: asyncio.Event) -> None:
    """Graceful shutdown по SIGINT/SIGTERM (остановка на хостинге, `systemctl stop`,
    завершение супервизором run_both.py)."""
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows: add_signal_handler не поддерживается — полагаемся на
            # KeyboardInterrupt в asyncio.run.
            pass


async def run_max():
    """Запуск MAX-бота отдельно (python max_main.py) или из run_both.py.

    Устойчив к сбоям: polling перезапускается с экспоненциальной задержкой,
    если цикл завершился из-за сетевой ошибки; при неверном токене бот
    останавливается сразу (перезапуск ничего не исправит).
    """
    stop_event = asyncio.Event()
    install_signal_handlers(stop_event)

    scheduler_task = asyncio.create_task(scheduler_loop())
    delay = 5
    try:
        while not stop_event.is_set():
            await register_scheduler()
            try:
                await dp.start_polling(bot, skip_updates=True)
            except InvalidToken:
                # Неверный токен — бесконечный перезапуск ничего не исправит,
                # но и выходить с кодом 1 не будем (иначе супервизор будет
                # спамить в лог). Ждём сигнала остановки или изменения конфига.
                logger.critical(
                    "[MAX] Неверный токен API_MAX — проверьте config.py "
                    "или переменную окружения MAX_TOKEN. Бот ждёт остановки; "
                    "после исправления токена перезапустите процесс."
                )
                await stop_event.wait()
                break
            except asyncio.CancelledError:
                raise
            except (MaxApiError, MaxError, OSError) as e:
                if stop_event.is_set():
                    break
                logger.error(
                    f"[MAX] Polling аварийно завершился: {e!r}. "
                    f"Перезапуск через {delay} c.",
                    exc_info=True,
                )
            else:
                # start_polling вернулся без ошибки — значит, например,
                # был вызван stop_polling; выходим из цикла.
                break

            if stop_event.is_set():
                break
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(delay * 2, 300)
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        try:
            await bot.close_session()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(run_max())
    except KeyboardInterrupt:
        print("\n[MAX-бот] Остановлен пользователем.")
