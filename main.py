import asyncio
import active
from shared.logger import bot_logger as logger
import os
import sys
from aiogram.types import CallbackQuery, Message
from aiogram import Dispatcher
from aiogram.dispatcher import FSMContext
from aiogram import Bot
from aiogram import executor
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
from aiogram.utils.exceptions import BotBlocked, ChatNotFound
from aiogram.types import Message
import aioschedule
from config import *
from keyboards import *
import utils
import crosspost
from shared.db import get_connection
from aiogram.utils import executor
import aioschedule
import asyncio
import pytz
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from datetime import datetime
from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.utils import executor
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import asyncio
import config
from aiogram.dispatcher.filters import Filter
from config import MAX_WOMEN
ekaterinburg_tz = pytz.timezone("Asia/Yekaterinburg")
class ShowList(StatesGroup):
  waiting = State()
  waiting2 = State()

class UserState(StatesGroup):
  Sbor = State()
  del1 = State()

class UserState1(StatesGroup):  
  id = State()
  id1 = State()
# 1. Новое состояние для ожидания выбора пола
class AddPersonState(StatesGroup):
    waiting_gender = State()
#------- Подключение токена к Telegram -------

from shared.logger import bot_logger as logger
# logger setup moved to shared.logger

# Настройка файлового обработчика
# file_handler setup moved to shared.logger
# file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
# logger.addHandler(file_handler)
bot = Bot(token=API)
dp = Dispatcher(bot, storage=MemoryStorage())
SKIP_NEXT_FIN_FILE = "skip_next_fin_message.flag"


def mark_next_fin_message_cancelled():
    with open(SKIP_NEXT_FIN_FILE, "w", encoding="utf-8") as file:
        file.write(datetime.now(ekaterinburg_tz).isoformat())


def consume_next_fin_message_cancelled():
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
#---------------------------------------------
async def check_and_handle_block(message: types.Message):
    user_id = message.from_user.id
    if active.check_user_in_block(user_id):
        print(f"Пользователь {user_id} заблокирован.")
        await message.answer("Вы заблокированы")
        return True  # Возвращаем True, если пользователь заблокирован
    return False # Возвращаем False, если пользователь не заблокирован

async def log_action(message: types.Message, action_type: str):
    """Логирует действия пользователя."""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"{timestamp} - User ID: {user_id} Username: {username} First Name: {first_name} - Action: {action_type}")


def is_private_chat(event) -> bool:
    """True, если событие пришло из личного чата с ботом.

    Добавление/удаление друзей (+/-) разрешено только в личке;
    в группе эти кнопки и команды игнорируются.
    """
    message = getattr(event, "message", None)
    if message is None:
        message = event
    chat = getattr(message, "chat", None)
    return chat is not None and chat.type == "private"


async def id(message: types.Message):
  id = message.from_user.id
  return id

async def add(call: types.CallbackQuery, username, group_id):
    if utils.nomer() == 0:
        await bot.send_message(chat_id=group_id, text=f"Список пуст")
    else:
        await bot.send_message(chat_id=group_id, text=f"Записано: {utils.nomer()}")

# Добавляем новую команду /admin
@dp.message_handler(commands=['admin1'])
async def admin(message: types.Message):
    await log_action(message, "Command: /admin1")
    #Проверяем есть ли айди пользователя в списке admins
    if message.from_user.id in admins:
        #Если есть, то открываем панель
        await message.answer("Вы открыли панель администратора", parse_mode="HTML", reply_markup=admin_panel1)
    else:
        #Если нет, то говорим об этом
        await message.answer("Вы не администратор", parse_mode="HTML", reply_markup=None)

@dp.message_handler(commands=['start'])
async def start(message: types.Message): # Use types.Message here
    if message.from_user.id in pol:
        if await check_and_handle_block(message):
            return
        await log_action(message, "Command: /start")
        if message.chat.type == "private":
            await message.answer(text='🏐 Запись на тренировку 🏐', reply_markup=start_kb_private)
        else:
            await message.answer(text='🏐 Запись на тренировку 🏐', reply_markup=start_kb)
        user_id = message.from_user.id # Get user ID from message
        username = message.from_user.username
        first_name = message.from_user.first_name
        gender = active.gender(user_id)
        active.add_user(user_id, username, first_name, gender)
    else:
        #Если нет, то говорим об этом
        await message.answer("У вас нету доступа к боту", parse_mode="HTML", reply_markup=None)

@dp.callback_query_handler(text='pm_список')
async def show_list_private(call: types.CallbackQuery):
    if call.from_user.id not in pol:
        return
    if await check_and_handle_block(call):
        return
    await log_action(call, "Кнопка Список в личке")
    await call.answer()
    list_text = utils.select()
    await call.message.answer(list_text, parse_mode="Markdown")

@dp.message_handler(commands=['admin'])
async def admin_command(message: types.Message):
    if await check_and_handle_block(message):
        return
    user_id = message.from_user.id
    await log_action(message, "Command: /admin")
    if user_id in admins:
        await message.reply("Добро пожаловать в админ-панель!", reply_markup=admin_panel)
    else:
        await message.reply("Вы не являетесь администратором.")


@dp.message_handler(lambda message: message.text and message.text.strip().casefold() == "отмена", state="*")
async def cancel_next_fin_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    if await check_and_handle_block(message):
        return

    mark_next_fin_message_cancelled()
    await state.finish()
    await log_action(message, "Отмена ближайшего сообщения спасибо за тренировку")
    await message.answer("Ближайшее сообщение «Всем спасибо за игру!» не будет отправлено.")


@dp.message_handler(lambda message: message.text and message.text.strip().casefold() == "отмена отмены", state="*")
async def restore_next_fin_message(message: types.Message, state: FSMContext):
    if message.from_user.id not in admins:
        return
    if await check_and_handle_block(message):
        return

    await state.finish()
    if clear_next_fin_message_cancelled():
        await log_action(message, "Отмена отмены ближайшего сообщения спасибо за тренировку")
        await message.answer("Отмена снята. Ближайшее сообщение «Всем спасибо за игру!» отправится по расписанию.")
    else:
        await message.answer("Сейчас нет активной отмены для ближайшего сообщения.")

@dp.callback_query_handler(text="Я иду")
async def buy1(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка я иду")
    await call.answer()
    
    user_id = call.from_user.id
    first_name = call.from_user.first_name
    last_name = call.from_user.last_name
    username = f"{first_name}"
    
    if last_name and last_name != "None":
        username += f" {last_name}"
    
    # Берем пол из ОСНОВНОЙ базы database.db
    gender_value = active.gender(user_id)

    # УБРАНА ПРОВЕРКА ОГРАНИЧЕНИЯ НА ЖЕНЩИН
    if utils.check_user_exists(username):
        # Уже записан: обновляем мессенджер-источник (значок в списке)
        utils.set_source(username, "tg")
    else:
        # Добавляем в временную базу sbor.db
        utils.add(username, gender_value, "tg")
    
    # Отправляем обновленный список
    await send_updated_list(GROUP_ID)

@dp.callback_query_handler(text="Я не иду")
async def not_going(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка 'Я не иду'")
    await call.answer()
    
    user_name = call.from_user.first_name
    last_name = call.from_user.last_name
    username = f"{user_name}"
    
    if last_name and last_name != "None":
        username += f" {last_name}"
    
    # Проверяем, есть ли основной пользователь в списке
    if utils.check_user_exists(username):
        utils.del_one(username)
        
        
        # Отправляем обновленный список
        await send_updated_list(GROUP_ID)
    else:
        return

async def send_updated_list(chat_id):
    """Отправляет обновленный список в группы Telegram и MAX."""
    # Удаляем предыдущее сообщение в TG-группе (ID общий для обоих ботов)
    previous_id = utils.get_state("tg_list_message_id")
    if previous_id:
        try:
            await bot.delete_message(chat_id, int(previous_id))
        except Exception:
            pass

    # Получаем новый список участников
    list_text = utils.select()
    # ИЗМЕНЕНО: Добавлен parse_mode для поддержки Markdown
    sent_message = await bot.send_message(chat_id, list_text, parse_mode="Markdown")
    utils.set_state("tg_list_message_id", sent_message.message_id)

    # Кросс-пост: обновляем список в MAX-группе (в фоне, чтобы не задерживать событие)
    crosspost.spawn(crosspost.post_to_max(list_text))
from config import MAX_WOMEN

@dp.callback_query_handler(text="+ Мужчина")
async def add_male_friend(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка + Муж")
    await call.answer()
    
    user_name = call.from_user.first_name
    last_name = call.from_user.last_name
    if last_name and last_name != "None":
        user_name += f" {last_name}"
    
    friend_name = utils.get_user_friend_name(user_name, 'Муж')
    
    # Просто добавляем без проверки на дубликаты
    utils.add(friend_name, "Муж", "tg")
    
    
    # Отправляем обновленный список
    await send_updated_list(GROUP_ID)

@dp.callback_query_handler(text="+ Девушка")
async def add_female_friend(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка + Дев")
    await call.answer()
    
    # УБРАНА ПРОВЕРКА ОГРАНИЧЕНИЯ НА ЖЕНЩИН
    user_name = call.from_user.first_name
    last_name = call.from_user.last_name
    if last_name and last_name != "None":
        user_name += f" {last_name}"
    
    friend_name = utils.get_user_friend_name(user_name, 'Дев')
    
    # Просто добавляем без проверки на дубликаты
    utils.add(friend_name, "Дев", "tg")
    
    
    # Отправляем обновленный список
    await send_updated_list(GROUP_ID)

@dp.callback_query_handler(text="- Мужчина")
async def remove_male_friend(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка - Муж")
    await call.answer()
    
    user_name = call.from_user.first_name
    last_name = call.from_user.last_name
    if last_name and last_name != "None":
        user_name += f" {last_name}"
    
    friend_name = utils.get_user_friend_name(user_name, 'Муж')
    
    # Удаляем только ОДНУ запись мужчины этого пользователя
    if utils.check_friend_exists(user_name, 'Муж'):
        utils.delete_one_friend(user_name, 'Муж')
        
    else:
        return
    
    # Отправляем обновленный список
    await send_updated_list(GROUP_ID)

@dp.callback_query_handler(text="- Девушка")
async def remove_female_friend(call: types.CallbackQuery):
    if await check_and_handle_block(call):
        return
    
    await log_action(call, "Кнопка - Дев")
    await call.answer()
    
    user_name = call.from_user.first_name
    last_name = call.from_user.last_name
    if last_name and last_name != "None":
        user_name += f" {last_name}"
    
    friend_name = utils.get_user_friend_name(user_name, 'Дев')
    
    # Удаляем только ОДНУ запись женщины этого пользователя
    if utils.check_friend_exists(user_name, 'Дев'):
        utils.delete_one_friend(user_name, 'Дев')
        
    else:
        return
    # Отправляем обновленный список
    await send_updated_list(GROUP_ID)


# ---------- Кнопки в личных сообщениях (pm_*) ----------
# Вызывают те же действия, что и групповые кнопки, но список дополнительно
# приходит в личный чат (группа обновляется внутри самих функций).
@dp.callback_query_handler(text='pm_я иду')
async def pm_buy(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await buy1(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.callback_query_handler(text='pm_я не иду')
async def pm_not_going(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await not_going(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.callback_query_handler(text='pm_+ муж')
async def pm_add_male_friend(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await add_male_friend(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.callback_query_handler(text='pm_- муж')
async def pm_remove_male_friend(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await remove_male_friend(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.callback_query_handler(text='pm_+ дев')
async def pm_add_female_friend(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await add_female_friend(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.callback_query_handler(text='pm_- дев')
async def pm_remove_female_friend(call: types.CallbackQuery):
    if call.from_user.id not in pol or active.check_user_in_block(call.from_user.id):
        return
    await remove_female_friend(call)
    await call.message.answer(utils.select(), parse_mode="Markdown")


@dp.message_handler(lambda msg: msg.text.strip().startswith('+') and len(msg.text.strip()) > 1, state=None)
async def handle_add_person(message: types.Message, state: FSMContext):
    if message.from_user.id not in pol:
        return
        
    await log_action(message, f"Запрос на добавление: {message.text.strip()}")
    
    name = message.text.strip()[1:].strip()
    name, source = utils.parse_source(name, "tg")
    await state.update_data(name=name, source=source)
    
    await message.answer(f"📝 Выберите пол для: <b>{name}</b>", reply_markup=drug, parse_mode="HTML")
    await AddPersonState.waiting_gender.set()

        
@dp.callback_query_handler(lambda c: c.data in ['+drug_boy', '+drug_girl'], state=AddPersonState.waiting_gender)
async def process_gender_selection(call: types.CallbackQuery, state: FSMContext):
    await call.answer()
    data = await state.get_data()
    name = data['name']
    source = data.get('source', 'tg')
    gender = "Муж" if call.data == "+drug_boy" else "Дев"
    
    await log_action(call, f"Выбран пол ({gender}) для: {name}")
    
    utils.add(name, gender, source)
    await call.message.answer(f"✅ <b>{name}</b> ({gender}) успешно добавлен!", parse_mode="HTML")
    await send_updated_list(GROUP_ID)
    logger.info(f"✅ Успешно добавлен: {name} | Пол: {gender}")

    await state.finish()


@dp.message_handler(lambda msg: msg.text.strip().startswith('-') and len(msg.text.strip()) > 1, state=None)
async def handle_remove_person(message: types.Message):
    if message.from_user.id not in pol:
        return
        
    name = message.text.strip()[1:].strip()
    await log_action(message, f"Запрос на удаление: {message.text.strip()}")
    
    if utils.check_user_exists(name):
        utils.delete_one(name)
        await message.answer(f"❌ <b>{name}</b> удален из списка.", parse_mode="HTML")
        await send_updated_list(GROUP_ID)
        logger.info(f"❌ Удален: {name} (по команде пользователя {message.from_user.id})")
    else:
        await message.answer(f"⚠️ <b>{name}</b> не найден в списке.", parse_mode="HTML")
        logger.warning(f"⚠️ Попытка удаления несуществующего пользователя: {name}")

@dp.callback_query_handler(text="Оплатил")
async def oplata1(call: types.CallbackQuery, state: FSMContext):
    await call.answer()

    first_name = call.from_user.first_name
    last_name = call.from_user.last_name
    username = f"{first_name}"

    if last_name and last_name != "None":
        username += f" {last_name}"

    await log_action(call, f"Нажал 'Оплатил', username: {username}")

    if utils.check_user_exists(username):
        utils.delete(username)
        await call.message.answer("Спасибо! Ваша запись удалена.")
        await log_action(call, f"Удалил {username}")
    elif utils.check_user_exists(username + " + 1"):  # ИЗМЕНЕНО: Добавляем пробел
        utils.delete(username + " + 1") # ИЗМЕНЕНО: Добавляем пробел
        await call.message.answer("Спасибо! Ваша запись (+1) удалена.")
        await log_action(call, f"Удалил {username} + 1")
    else:
        await call.message.answer("Вас нет в списке")

# Обработка кнопки "👨‍👩‍👦‍👦 Пользователи"
@dp.callback_query_handler(text="users")
async def users(call: types.CallbackQuery):
    #Вызываем написанную ранее функцию, которая возвращает строку с выводом пользователей бота
    await call.message.answer(active.show_users())
    await call.answer()

# Обработка кнопки "📊 Статистика"
@dp.callback_query_handler(text="statistics")
async def statistics(call: types.CallbackQuery):
    #Вызываем написанную ранее функцию, которая возвращает количество пользователей
    await call.message.answer(f"Количество пользователей: {active.show_statistics()}")
    await call.answer()

#Обработчик кнопки "⛔️ Блокировка"
@dp.callback_query_handler(text="block_user")
async def block_user(call: types.CallbackQuery):
    #Просим ввести id пользователя для блокировки
    await call.message.answer(f"Введите id пользователя для блокировки")
    #Запоминаем ответ пользователя
    await UserState1.id.set()
    await call.answer()

#Обработчик введённого администратором id
@dp.message_handler(state = UserState1.id)
async def fsm_handler(message: types.Message, state: FSMContext):
    #Получаем введённое пользователем сообщение
    input_id = message.text
    #Вызываем функцию для блокировки
    active.add_user_to_block(input_id)
    #Отвечаем, что пользователь был заблокирован
    await message.answer(f"Пользователь с id: {input_id}, был заблокирован")
    #Закрываем машину состояний
    await state.finish()

#Обработчик кнопки "✅ Разблокировка"
@dp.callback_query_handler(text="unlock_user")
async def unlock_user(call: types.CallbackQuery):
    #Просим ввести id пользователя
    await call.message.answer(f"Введите id пользователя для разблокировки")
    #Запоминаем в машину состояний
    await UserState1.id1.set()
    await call.answer()

#Обработчик введённого администратором id
@dp.message_handler(state = UserState1.id1)
async def fsm_handler(message: types.Message, state: FSMContext):
    #Получаем введённое пользователем сообщение
    input_id = message.text
    #Вызывааем функцию для разблокировки
    active.unlock_users(input_id)
    #Сообщаем о успешной разблокировке
    await message.answer(f"Пользователь с id: {input_id}, был разблокирован")
    #Закрываем машину состояний
    await state.finish()

# Декоратор с проверкой на блокировку, выполненной в виде лямбда-функции
@dp.message_handler(lambda message: active.check_user_in_block(message.from_user.id))
async def repeat(message: types.Message):
    # Отправляем сообщение о блокировке
    await message.answer("Вы были заблокированы")

async def sbor11(send_other=False):
    text = crosspost.SBOR_THURSDAY_TEXT
    await bot.send_message(chat_id = GROUP_ID, text = text, reply_markup=start_kb)
    if send_other:
        crosspost.spawn(crosspost.send_max_message(text, buttons=crosspost.START_BUTTONS))

async def sbor22(send_other=False):
    text = crosspost.SBOR_SUNDAY_TEXT
    await bot.send_message(chat_id = GROUP_ID, text = text, reply_markup=start_kb)
    if send_other:
        crosspost.spawn(crosspost.send_max_message(text, buttons=crosspost.START_BUTTONS))

async def fin1(send_other=False):
    text = crosspost.FIN_TEXT
    await bot.send_message(chat_id = GROUP_ID, text = text)
    if send_other:
        crosspost.spawn(crosspost.send_max_message(text))


async def scheduled_fin1():
    if consume_next_fin_message_cancelled():
        logger.info("Пропущено ближайшее сообщение спасибо за тренировку по команде Отмена")
        return

    await fin1()
    # Тренировка состоялась — отправляем список с кнопкой оплаты каждому админу
    await send_payment_request_to_admins()

async def spisok1():
    await bot.send_message(chat_id = 858672279, text = f"Вот кто был: {utils.select()}")

# Кнопка оплаты для админов
payment_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплатить", callback_data="oplata_done"),
        ]
    ]
)

async def send_payment_request_to_admins():
    """Отправляет список участников и кнопку оплаты каждому админу."""
    list_text = utils.select()
    for admin_id in admins:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"📋 Список участников тренировки:\n\n{list_text}\n\n💳 Не забудьте оплатить!\n+79222694226\n(Сбер, ВТБ, Альфа) 170 руб.",
                reply_markup=payment_keyboard
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить сообщение об оплате админу {admin_id}: {e}")

@dp.callback_query_handler(text="oplata_done")
async def payment_done(call: types.CallbackQuery):
    """При нажатии 'Оплатить' — удаляет сообщение и пишет подтверждение."""
    await call.answer()
    try:
        await call.message.delete()
    except Exception as e:
        logger.warning(f"Не удалось удалить сообщение об оплате: {e}")
    await bot.send_message(
        chat_id=call.from_user.id,
        text="✅ Оплата прошла!"
    )

async def del1():
    await bot.send_message(chat_id = 5485142636, text = "Сброс сделан")
    await bot.send_message(chat_id = 858672279, text = "Сброс сделан")
    utils.usersdel()

@dp.callback_query_handler(text = "Пользователи")
async def start(call: types.CallbackQuery):
    await call.message.answer(f'Вот список: ')
    await call.message.answer(f'{active.select()}')
    await call.answer()

@dp.callback_query_handler(text = "Сбросить таблицу")
async def start(call: types.CallbackQuery):
    await call.message.answer('Таблица обновлена')
    await spisok1()
    utils.usersdel()
    await call.answer()

@dp.callback_query_handler(text = "Все функции")
async def start(call: types.CallbackQuery):
    await call.message.answer('Вот все функции', reply_markup = Def)
    await call.answer()

@dp.callback_query_handler(text = "Перед тренеровки")
async def start(call: types.CallbackQuery):
    await call.message.answer('Выберети день', reply_markup= sbor)
    await call.answer()

@dp.callback_query_handler(text = "В четверг")
async def start(call: types.CallbackQuery):
    await call.message.answer('Действие выполнено')
    await sbor11(send_other=True)
    await call.answer() 

@dp.callback_query_handler(text = "В воскресенье")
async def start(call: types.CallbackQuery):
    await call.message.answer('Действие выполнено')
    await sbor22(send_other=True)
    await call.answer()

@dp.callback_query_handler(text = "После тренеровки")
async def start(call: types.CallbackQuery):
    await call.message.answer('Какой день?', reply_markup= tren)
    await call.answer()

@dp.callback_query_handler(text = "Отправить")
async def start(call: types.CallbackQuery):
    await call.message.answer('Действие выполнено')
    await fin1(send_other=True)
    await send_payment_request_to_admins()
    await call.answer()

@dp.callback_query_handler(text="Добавить пользователя")
async def add_user_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer('Напишите имя пользователя')
    await state.set_state(ShowList.waiting) # Correctly set the state
    await call.answer()

@dp.callback_query_handler(text="Удалить пользователя")
async def del_user_start(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer('Напишите имя пользователя')
    await state.set_state(ShowList.waiting2)
    await call.answer()

@dp.message_handler(state=ShowList.waiting) # Remove the () - use the State object directly
async def add_user_by_name(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    data = await state.get_data()
    username = data['username']
    if utils.check_user_exists(username):
        await bot.send_message(chat_id=message.from_user.id, text="Такие данные уже есть")
    else:
        utils.add(username, "unknown", "tg")
        await bot.send_message(chat_id=message.from_user.id, text=f"{utils.select()}")
    await state.finish()

@dp.message_handler(state=ShowList.waiting2) # Call the function
async def del_user_by_name(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    data = await state.get_data()
    username = data['username']
    if utils.check_user_exists(username):
        utils.delete(username)
        await bot.send_message(chat_id=message.from_user.id, text=f"{utils.select()}")
    else:
        await bot.send_message(chat_id=message.from_user.id, text="Таких данных нет.")
    await state.finish()

# ---------- Пробное оповещение (пятница 19:30 ЕКБ) ----------
async def probe():
    """Отправить тестовое сообщение в TG-группу."""
    await bot.send_message(GROUP_ID, "🔔 Проверка: оповещение работает (пятница 19:30 ЕКБ)")


async def probe_loop():
    """Одноразовая проверка в пятницу 19:30-19:34 по Екатеринбургу."""
    while True:
        now = datetime.now(ekaterinburg_tz)
        if (
            now.weekday() == 4
            and now.hour == 19
            and 30 <= now.minute <= 34
            and not utils.get_state("probe_sent_tg")
        ):
            await probe()
            utils.set_state("probe_sent_tg", now.date().isoformat())
            logger.info("Пробное оповещение (TG) отправлено")
        await asyncio.sleep(5)


# время -2 часа от тюмени
async def scheduler():
    aioschedule.every().monday.at("09:00").do(del1)
    aioschedule.every().friday.at("09:00").do(del1) 
    aioschedule.every().wednesday.at("08:00").do(sbor11) 
    aioschedule.every().saturday.at("08:00").do(sbor22) 
    aioschedule.every().sunday.at("18:30").do(scheduled_fin1) 
    aioschedule.every().thursday.at("19:30").do(scheduled_fin1) 
    aioschedule.every().sunday.at("18:35").do(spisok1) 
    aioschedule.every().thursday.at("19:35").do(spisok1)   
    while True:
        now = datetime.now(ekaterinburg_tz)
        await aioschedule.run_pending()
        await asyncio.sleep(1)

async def on_startup(dp):
    asyncio.create_task(scheduler())
    asyncio.create_task(probe_loop())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)