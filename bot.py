import os
import logging
import asyncio
import sqlite3
from google import genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Проверка ключей
if not BOT_TOKEN or not GEMINI_API_KEY:
    logging.error("❌ ОШИБКА: Ключи не найдены в .env! Проверь названия: BOT_TOKEN и GEMINI_API_KEY")
    exit()

# Читаем системный промпт
try:
    with open('system_prompt.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
    logging.info("✅ Системный промпт загружен.")
except FileNotFoundError:
    logging.error("❌ ОШИБКА: Файл system_prompt.txt не найден.")
    exit()

# Настройка клиента (новая библиотека)
client = genai.Client(api_key=GEMINI_API_KEY)

# --- ВЫБОР МОДЕЛИ ---
# В 2025 году gemini-1.5-flash может быть устаревшей.
# Используем актуальную версию 2.0.
MODEL_NAME = "gemini-2.5-flash"

# Функция для проверки доступных моделей (выводит в консоль при старте)
def check_available_models():
    try:
        logging.info("🔍 Проверяю доступные модели...")
        # Получаем список моделей
        models = client.models.list()
        # Ищем модели, содержащие 'gemini' и 'flash'
        available = [m.name for m in models if "gemini" in m.name]
        
        logging.info(f"📋 Доступные модели для твоего ключа: {available}")
        
        # Если нашей модели нет в списке, предупреждаем
        full_model_name = f"models/{MODEL_NAME}"
        if not any(MODEL_NAME in m for m in available):
            logging.warning(f"⚠️ ВНИМАНИЕ: Модель {MODEL_NAME} может не сработать. Попробуй одну из списка выше!")
            
    except Exception as e:
        logging.error(f"⚠️ Не удалось получить список моделей (не критично): {e}")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('edip_history.db')
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS chat_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            user_input TEXT,
            full_prompt_sent TEXT, 
            ai_response TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()
    logging.info("✅ База данных подключена.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Корневой Координатор ЕДИП на связи.**\n\n"
        "Я готов к работе. Использую протокол: `Gemini 2.0`.\n"
        "Введите вводные данные о бизнесе."
    )

@dp.message()
async def process_message(message: types.Message):
    user_text = message.text
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    full_prompt = f"{SYSTEM_PROMPT}\n\n--- ВХОДНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ ---\n{user_text}"
    
    try:
        # Запрос к Gemini
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt
        )
        
        ai_answer = response.text
        
        # Сохранение
        conn = sqlite3.connect('edip_history.db')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_log (user_id, username, user_input, full_prompt_sent, ai_response) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.username, user_text, full_prompt, ai_answer)
        )
        conn.commit()
        conn.close()
        
        await message.answer(ai_answer, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"❌ Ошибка генерации: {e}")
        error_msg = str(e)
        if "404" in error_msg:
            await message.answer(f"⚠️ Ошибка модели: `{MODEL_NAME}` не найдена. Посмотрите в консоль сервера, там выведен список доступных моделей.")
        else:
            await message.answer("⚠️ Ошибка обработки. Попробуйте позже.")

async def main():
    init_db()
    # Проверяем модели перед запуском
    check_available_models()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())