import asyncio
from maxapi import Bot
import config

async def main() -> None:
    bot = Bot(token=config.API_MAX)
    
    # Информация о боте
    me = await bot.get_me()
    print(f"Бот: {me.first_name} (@{me.username}) id={me.user_id}")
    print("-" * 60)

    chat_id = -80520423238305  # Замените на реальный ID, если нужно
    
    try:
        members_obj = await bot.get_chat_members(chat_id)
        members_list = members_obj.members
        
        print(f"Найдено участников: {len(members_list)}")
        print(f"Участники группы {chat_id}:\n")
        
        for m in members_list:
            name = f"{m.first_name or ''} {m.last_name or ''}".strip()
            username = f" (@{m.username})" if m.username else ""
            bot_mark = " 🤖" if m.is_bot else ""
            print(f"  • {name}{username}{bot_mark} (id={m.user_id})")
            
    except Exception as exc:
        print(f"Ошибка при получении участников: {exc}")

    await bot.close_session()

if __name__ == "__main__":
    asyncio.run(main())