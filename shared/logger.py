import logging

# Configure bot logger
bot_logger = logging.getLogger('bot')
bot_logger.setLevel(logging.INFO)
handler = logging.FileHandler('bot.log', mode='w', encoding='utf-8')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
bot_logger.addHandler(handler)
