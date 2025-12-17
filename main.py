import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем ключи из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Проверяем наличие ключей
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY не найден в переменных окружения")

# Настройка Google Gemini API
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# Загружаем системный промпт
SYSTEM_PROMPT_FILE = Path(__file__).parent / 'system_prompt.txt'
try:
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    logger.warning(f"Файл {SYSTEM_PROMPT_FILE} не найден. Используется стандартный промпт.")
    SYSTEM_PROMPT = "Ты полезный помощник. Отвечай на русском языке."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот с интеграцией Google Gemini.\n"
        "Напиши мне любое сообщение, и я помогу тебе! 🤖"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help"""
    help_text = """
📖 Доступные команды:
/start - Запустить бота
/help - Показать эту справку
/prompt - Показать текущий системный промпт

Просто напиши мне любое сообщение, и я отвечу с помощью Google Gemini!
    """
    await update.message.reply_text(help_text)


async def show_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /prompt - показывает текущий системный промпт"""
    await update.message.reply_text(f"📝 Текущий системный промпт:\n\n{SYSTEM_PROMPT}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик текстовых сообщений"""
    user_message = update.message.text
    user_id = update.effective_user.id
    
    logger.info(f"Сообщение от пользователя {user_id}: {user_message}")
    
    try:
        # Показываем индикатор "печатает..."
        await update.message.chat.send_action("typing")
        
        # Формируем запрос с системным промптом
        prompt = f"{SYSTEM_PROMPT}\n\nПользователь: {user_message}"
        
        # Получаем ответ от Gemini
        response = model.generate_content(prompt)
        ai_response = response.text
        
        logger.info(f"Ответ для пользователя {user_id}: {ai_response[:100]}...")
        
        # Отправляем ответ пользователю
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await update.message.reply_text(
            f"❌ Произошла ошибка: {str(e)}\n"
            "Пожалуйста, попробуйте снова."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок"""
    logger.error(f"Ошибка: {context.error}")


def main() -> None:
    """Запуск бота"""
    logger.info("Запуск Telegram бота...")
    
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("prompt", show_prompt))
    
    # Добавляем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Добавляем обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    logger.info("Бот запущен и готов к работе!")
    application.run_polling()


if __name__ == '__main__':
    main()
