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
    raise ValueError("TELEGRAM_BOT_TOKEN not found")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

user_conversations = {}
MAX_HISTORY = 10

SYSTEM_PROMPT_FILE = Path(__file__).parent / 'system_prompt.txt'
try:
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    SYSTEM_PROMPT = "You are a helpful assistant."


async def start(update, context):
    user_id = update.effective_user.id
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    msg = "Hello! I am a bot with Google Gemini. Write me and I will help!"
    await update.message.reply_text(msg)


async def help_command(update, context):
    msg = "Commands: /start /help /prompt /clear"
    await update.message.reply_text(msg)


async def show_prompt(update, context):
    msg = "System prompt:\n\n" + SYSTEM_PROMPT
    await update.message.reply_text(msg)


async def clear_context(update, context):
    user_id = update.effective_user.id
    if user_id in user_conversations:
        user_conversations[user_id] = []
        await update.message.reply_text("Chat cleared!")
    else:
        await update.message.reply_text("Already empty.")


async def handle_message(update, context):
    user_message = update.message.text
    user_id = update.effective_user.id
    
    if user_id not in user_conversations:
        user_conversations[user_id] = []
    
    logger.info("Message from user: " + str(user_id))
    
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
        
        logger.info("Sent response")
        
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error("Error: " + str(e))
        msg = "Error. Try again."
        await update.message.reply_text(msg)


async def error_handler(update, context):
    logger.error("Error: " + str(context.error))


def main():
    logger.info("Starting bot...")
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("prompt", show_prompt))
    application.add_handler(CommandHandler("clear", clear_context))
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    application.add_error_handler(error_handler)
    
    logger.info("Bot running!")
    application.run_polling()


if __name__ == '__main__':
    main()
