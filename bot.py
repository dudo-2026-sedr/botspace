import os
import asyncio
from collections import defaultdict
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ChatType
from openai import AsyncOpenAI

# ================= КОНФИГУРАЦИЯ =================
BOT_TOKEN = "8481958068:AAFE9J7kNfhDCxcmuez6luH-sC-Zii9YQyo"
GLM_API_KEY = "sk-usoNqhK6OKMBi8zBC9eGI4gbR6ZL4BeU1kzkJ47tWj5wF1Xf"
MODEL_ID = "gemini-3.7-flash-high"  # Укажи нужный ID: glm-4-plus, glm-4-air, glm-4v, glm-5.2 и т.д.
# ===============================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключение к API GLM
glm_client = AsyncOpenAI(
    api_key=GLM_API_KEY,
    base_url="https://api.now.cc/v1"
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
- Строго придерживайся фактов из базы знаний (история, создатели, роли).
- Общайся уверенно, лаконично, с уместным юмором и уважением к пруфам.
- Не пиши огромные простыни текста, если тебя об этом прямо не просят.
- Обращайся к пользователю естественно, как живой участник беседы.
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
