import os
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatType
from openai import AsyncOpenAI

# ================= КОНФИГУРАЦИЯ =================
BOT_TOKEN = "8481958068:AAFE9J7kNfhDCxcmuez6luH-sC-Zii9YQyo"
GLM_API_KEY = "sk-2RXG2ZoxbkDyDSv1ECu8xUX773eEIR06X4VkWqSsi3Qup5Yo"
MODEL_ID = "claude-opus-4-8"  # Укажи нужный ID модели
# ===============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключение к API
glm_client = AsyncOpenAI(
    api_key=GLM_API_KEY,
    base_url="https://tabitoken.com/v1"
)

# Память последних 10 сообщений для каждого чата
CHAT_HISTORY = defaultdict(list)
MAX_HISTORY_LEN = 10

def load_system_prompt() -> str:
    """Динамически считывает лор и правила из файла arena_lore.md."""
    try:
        with open("arena_lore.md", "r", encoding="utf-8") as f:
            lore = f.read()
    except FileNotFoundError:
        lore = "База знаний временно недоступна. Ты ассистент чата арены."
        
    return f"""Ты — официальный ИИ-ассистент и участник чата арены пруфбатлов.
Ниже представлена официальная база знаний, история арены, создатели и правила:

---
{lore}
---

Инструкции для общения:
- Строго придерживайся базы знаний.
"""

async def get_glm_response(chat_id: int, user_message: str, username: str) -> str:
    system_prompt = load_system_prompt()
    
    # Формируем системный промпт и контекст
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(CHAT_HISTORY[chat_id])
    
    # Добавляем текущую реплику
    current_entry = f"[{username}]: {user_message}"
    messages.append({"role": "user", "content": current_entry})

    # Запрос к нейросети с указанной моделью
    response = await glm_client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        temperature=0.7,
        max_tokens=800
    )
    
    reply_text = response.choices[0].message.content
    
    # Сохраняем диалог в память
    CHAT_HISTORY[chat_id].append({"role": "user", "content": current_entry})
    CHAT_HISTORY[chat_id].append({"role": "assistant", "content": reply_text})
    
    # Ограничиваем глубину контекста
    if len(CHAT_HISTORY[chat_id]) > MAX_HISTORY_LEN * 2:
        CHAT_HISTORY[chat_id] = CHAT_HISTORY[chat_id][-MAX_HISTORY_LEN * 2:]
        
    return reply_text

@dp.message(F.text)
async def handle_messages(message: types.Message):
    bot_info = await bot.get_me()
    
    # Проверка триггеров: ЛС, ответ на сообщение бота или упоминание @юзернейма
    is_pm = message.chat.type == ChatType.PRIVATE
    is_reply_to_bot = (
        message.reply_to_message is not None 
        and message.reply_to_message.from_user.id == bot_info.id
    )
    is_mentioned = f"@{bot_info.username}" in (message.text or "")

    if is_pm or is_reply_to_bot or is_mentioned:
        clean_text = message.text.replace(f"@{bot_info.username}", "").strip()
        user_name = message.from_user.first_name or message.from_user.username or "Участник"
        
        # Индикатор набора текста
        await bot.send_chat_action(message.chat.id, "typing")
        
        try:
            answer = await get_glm_response(message.chat.id, clean_text, user_name)
            await message.reply(answer)
        except Exception as e:
            await message.reply(f"⚠️ Ошибка запроса к нейросети ({MODEL_ID}): {str(e)}")

async def main():
    print(f"Бот арены запущен. Используемая модель: {MODEL_ID}")
    # Сбрасываем все накопившиеся старые сообщения перед стартом
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
