import logging

# Configure bot logger
bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.INFO)
# mode='a': Telegram-бот и MAX-бот работают двумя процессами и пишут в один
# bot.log. В режиме 'w' второй стартующий процесс затирал бы весь лог первого.
handler = logging.FileHandler('bot.log', mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
bot_logger.addHandler(handler)
