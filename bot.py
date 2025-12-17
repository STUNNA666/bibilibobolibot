import os
import sys
import logging
import asyncio
import sqlite3
import io

# ==========================================
# 🛡️ БЛОК ЗАЩИТЫ ОТ ОШИБОК КОДИРОВКИ WINDOWS
# ==========================================
# Жестко переключаем стандартный вывод на UTF-8
if sys.platform.startswith('win'):
    # Пытаемся перенастроить вывод консоли
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        # Для старых версий Python
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Настраиваем логгер так, чтобы он писал в файл (безопасно) и в консоль
# Если консоль не может отобразить эмодзи, она просто пропустит символ, а не упадет
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        # Пишем в файл (тут всегда UTF-8, ничего не сломается)
        logging.FileHandler("bot.log", encoding='utf-8'),
        # Пишем в консоль (с обработкой ошибок)
        logging.StreamHandler(sys.stdout)
    ]
)
# ==========================================

from google import genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    logging.error("CRITICAL: Ключи не найдены в .env! Проверьте файл.")
    exit()

# Читаем системный промпт с защитой
try:
    with open('system_prompt.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
    logging.info("System prompt loaded successfully (UTF-8).")
except UnicodeDecodeError:
    logging.error("ERROR: Файл system_prompt.txt сохранен не в UTF-8! Пожалуйста, пересохраните его в кодировке UTF-8.")
    exit()
except FileNotFoundError:
    logging.error("ERROR: Файл system_prompt.txt не найден.")
    exit()

# Настройка клиента
client = genai.Client(api_key=GEMINI_API_KEY)

# Актуальная модель (из твоего списка)
MODEL_NAME = "gemini-2.5-flash"

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
    logging.info("Database connected.")

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Корневой Координатор ЕДИП на связи.**\n\n"
        f"Ядро системы: `{MODEL_NAME}`\n"
        "Жду вводные данные для начала работы."
    )

@dp.message()
async def process_message(message: types.Message):
    user_text = message.text
    
    # Логгируем в файл, чтобы не засорять консоль эмодзи, которые могут крашить Windows
    logging.info(f"New message from user {message.from_user.id}")
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    full_prompt = f"{SYSTEM_PROMPT}\n\n--- ВХОДНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ ---\n{user_text}"
    
    try:
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
        logging.info("Response sent successfully.")
        
    except Exception as e:
        # Ловим ошибку, но пишем её безопасно (ascii), чтобы консоль не умерла
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        logging.error(f"API Error: {error_msg}")
        await message.answer("⚠️ Произошла ошибка обработки. Попробуйте позже.")

async def main():
    init_db()
    logging.info("Bot started via polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    # Исправление для Windows (SelectorEventLoop)
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())