import asyncio
import sqlite3
import json
import logging
from aiogram import Bot, Dispatcher, types, F
from openai import AsyncOpenAI
import os

# Считываем токены из безопасной памяти сервера
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Ты — экспертный клинический психолог (КПТ). Специализация: ГТР, паника, депрессия и ипохондрия.
Помогай выявлять когнитивные искажения, не давай мед. заверений, будь эмпатичен.

ТВОЙ АЛГОРИТМ:
1. Анализируй сообщение на когнитивные искажения (катастрофизация, черно-белое мышление).
2. При ипохондрии: НЕ давай медицинских заверений ("ты точно здоров"). Вместо этого работай со страхом неопределенности.
3. При депрессии: проявляй валидацию чувств и предлагай методы поведенческой активации (микро-шаги).
4. Задавай наводящие вопросы. Помогай пользователю самому прийти к рациональным выводам.
5. Будь профессионален, эмпатичен и лаконичен.
6. Розмовляй на укр мові.
"""

# 2. БАЗА ДАННЫХ (ИСПРАВЛЕННАЯ)
def init_db():
    conn = sqlite3.connect('bot_memory.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS history (user_id INTEGER PRIMARY KEY, messages TEXT)')
    conn.commit()
    conn.close()

def load_history(user_id):
    conn = sqlite3.connect('bot_memory.db')
    cursor = conn.cursor()
    cursor.execute('SELECT messages FROM history WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    if result and result[0]: # Проверяем, что результат есть и он не пустой
        return json.loads(result[0]) # Достаем строку из кортежа через [0]
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def save_history(user_id, messages):
    conn = sqlite3.connect('bot_memory.db')
    cursor = conn.cursor()
    
    if len(messages) > 15:
        trimmed = [messages[0]] + messages[-14:]
    else:
        trimmed = messages
        
    # ДОБАВЛЕНО ensure_ascii=False — это разрешит сохранение кириллицы как есть
    json_data = json.dumps(trimmed, ensure_ascii=False)
    
    cursor.execute('INSERT OR REPLACE INTO history (user_id, messages) VALUES (?, ?)', 
                   (user_id, json_data))
    conn.commit()
    conn.close()

# 3. ЛОГИКА
async def get_ai_response(user_id, user_text):
    history = load_history(user_id)
    history.append({"role": "user", "content": user_text})

    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=history,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        history.append({"role": "assistant", "content": answer})
        save_history(user_id, history)
        return answer
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        return "Произошла ошибка. Попробуй еще раз через минуту."

@dp.message(F.text)
async def handle_message(message: types.Message):
    await bot.send_chat_action(message.chat.id, "typing")
    answer = await get_ai_response(message.from_user.id, message.text)
    await message.answer(answer)

async def main():
    init_db()
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
