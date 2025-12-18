import os
import sys
import logging
import asyncio
import sqlite3
import io

# ==========================================
# 🛡️ БЛОК ЗАЩИТЫ ОТ ОШИБОК КОДИРОВКИ WINDOWS
# ==========================================
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
# ==========================================

from google import genai
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest # Импортируем для обработки ошибок телеграма
from dotenv import load_dotenv

# --- ЗАГРУЗКА КОНФИГУРАЦИИ ---
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not GEMINI_API_KEY:
    logging.error("CRITICAL: Ключи не найдены в .env! Проверьте файл.")
    exit()

try:
    with open('system_prompt.txt', 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read()
    logging.info("System prompt loaded successfully (UTF-8).")
except Exception as e:
    logging.error(f"ERROR: Ошибка чтения system_prompt.txt: {e}")
    # Создадим пустой промпт, чтобы бот не падал, если файла нет
    SYSTEM_PROMPT = "Ты полезный ассистент."

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-2.5-flash"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

# --- ФУНКЦИЯ БЕЗОПАСНОЙ ОТПРАВКИ ---
async def safe_send_message(message: types.Message, text: str):
    """
    Разбивает длинный текст и пробует отправить его с Markdown.
    Если Markdown ломается (ошибка парсинга), отправляет чистый текст.
    """
    # Лимит телеграма 4096, берем с запасом 4000
    CHUNK_SIZE = 4000 
    
    # Разбиваем текст на куски
    for i in range(0, len(text), CHUNK_SIZE):
        chunk = text[i:i + CHUNK_SIZE]
        
        try:
            # Попытка 1: Отправить красиво (Markdown)
            # Используем "Markdown", он чуть менее строгий, чем "MarkdownV2"
            await message.answer(chunk, parse_mode="Markdown")
        except TelegramBadRequest as e:
            error_text = str(e)
            # Если ошибка именно в парсинге (can't parse entities), шлем без форматирования
            if "parse entities" in error_text or "can't find end" in error_text:
                logging.warning(f"Markdown parsing failed for chunk. Sending as plain text. Error: {error_text}")
                await message.answer(chunk, parse_mode=None)
            else:
                logging.error(f"Telegram API Error: {error_text}")
                await message.answer(f"⚠️ Ошибка отправки части сообщения: {error_text}")
        except Exception as e:
            logging.error(f"Unexpected error sending message: {e}")
            await message.answer(chunk, parse_mode=None)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Корневой Координатор ЕДИП на связи.**\n\n"
        f"Ядро системы: `{MODEL_NAME}`\n"
        "Жду вводные данные для начала работы.",
        parse_mode="Markdown"
    )

@dp.message()
async def process_message(message: types.Message):
    user_text = message.text
    
    logging.info(f"New message from user {message.from_user.id}")
    
    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    
    full_prompt = f"{SYSTEM_PROMPT}\n\n--- ВХОДНЫЕ ДАННЫЕ ОТ ПОЛЬЗОВАТЕЛЯ ---\n{user_text}"
    
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=full_prompt
        )
        
        ai_answer = response.text
        
        # Сохранение в БД
        conn = sqlite3.connect('edip_history.db')
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_log (user_id, username, user_input, full_prompt_sent, ai_response) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, message.from_user.username, user_text, full_prompt, ai_answer)
        )
        conn.commit()
        conn.close()
        
        # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ ОТПРАВКИ
        await safe_send_message(message, ai_answer)
        
        logging.info("Response sent successfully.")
        
    except Exception as e:
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        logging.error(f"API Error: {error_msg}")
        await message.answer("⚠️ Произошла ошибка генерации ответа. Попробуйте позже.")

async def main():
    init_db()
    logging.info("Bot started via polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())