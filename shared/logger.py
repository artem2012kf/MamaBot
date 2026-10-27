import logging

# Configure bot logger
bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.INFO)
# mode='a': оба бота (main.py и max_main.py) пишут в один файл из разных процессов —
# mode='w' обрезал бы лог при старте второго процесса
handler = logging.FileHandler('bot.log', mode='a', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
bot_logger.addHandler(handler)
