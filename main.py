# -*- coding: utf-8 -*-
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

user_conversations = {}
MAX_HISTORY = 10

SYSTEM_PROMPT_FILE = Path(__file__).parent / 'system_prompt.txt'
try:
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    warning_msg = "File " + str(SYSTEM_PROMPT_FILE) + " not found. Using default prompt."
    logger.warning(warning_msg)
    SYSTEM_PROMPT = "You are a helpful assistant. Reply in Russian."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    await update.message.reply_text(
        "Hello! I'm a bot with Google Gemini integration.\n"
        "Write me any message, and I'll help you!\n"
        "I will remember the context of our conversation."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help
/prompt - Show current system prompt
/clear - Clear chat history

I remember the context of our conversation and use it for answers!
    """
    await update.message.reply_text(help_text)


async def show_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Current system prompt:\n\n" + SYSTEM_PROMPT)


async def clear_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if user_id in user_conversations:
        user_conversations[user_id] = []
        await update.message.reply_text("Chat history cleared!")
    else:
        await update.message.reply_text("History was already empty.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_message = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    
    logger.info("Message from user " + str(user_id) + ": " + user_message)
    
    try:
        await update.message.chat.send_action("typing")
        
        user_conversations[user_id].append("User: " + user_message)
        
        history = "\n".join(user_conversations[user_id][-MAX_HISTORY:])
        
        prompt = SYSTEM_PROMPT + "\n\nHistory:\n" + history
        
        response = model.generate_content(prompt)
        ai_response = response.text
        
        user_conversations[user_id].append("Assistant: " + ai_response)
        
        if len(user_conversations[user_id]) > MAX_HISTORY * 2:
            user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY * 2:]
        
        logger.info("Response to user " + str(user_id) + ": " + ai_response[:100] + "...")
        
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error("Error processing message: " + str(e))
        await update.message.reply_text(
            "Error: " + str(e) + "\n"
            "Please try again."
        )


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Error: " + str(context.error))


def main() -> None:
    logger.info("Starting Telegram bot...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("prompt", show_prompt))
    application.add_handler(CommandHandler("clear", clear_context))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)
    
    logger.info("Bot is running and ready to work!")
    application.run_polling()


if __name__ == '__main__':
    main()
