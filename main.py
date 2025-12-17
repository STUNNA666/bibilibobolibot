import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from telegram.ext import Application, CommandHandler, MessageHandler, filters

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    raise ValueError('Missing API keys')

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

user_conversations = {}
MAX_HISTORY = 10

SYSTEM_PROMPT_FILE = Path(__file__).parent / 'system_prompt.txt'
try:
    with open(SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
        SYSTEM_PROMPT = f.read().strip()
except Exception:
    SYSTEM_PROMPT = 'You are helpful assistant.'

async def start(update, context):
    uid = update.effective_user.id
    if uid not in user_conversations:
        user_conversations[uid] = []
    await update.message.reply_text('Hello! I am Gemini bot.')

async def help_cmd(update, context):
    await update.message.reply_text('Commands: /start /help /prompt /clear')

async def show_prompt(update, context):
    await update.message.reply_text('Prompt: ' + SYSTEM_PROMPT)

async def clear_chat(update, context):
    uid = update.effective_user.id
    if uid in user_conversations:
        user_conversations[uid] = []
    await update.message.reply_text('Cleared.')

async def handle_msg(update, context):
    uid = update.effective_user.id
    text = update.message.text
    if uid not in user_conversations:
        user_conversations[uid] = []
    try:
        user_conversations[uid].append('User: ' + text)
        hist = '\n'.join(user_conversations[uid][-MAX_HISTORY:])
        prompt = SYSTEM_PROMPT + '\n\nHistory:\n' + hist
        resp = model.generate_content(prompt)
        answer = resp.text
        user_conversations[uid].append('Bot: ' + answer)
        if len(user_conversations[uid]) > MAX_HISTORY * 2:
            user_conversations[uid] = user_conversations[uid][-MAX_HISTORY * 2:]
        await update.message.reply_text(answer)
    except Exception as e:
        await update.message.reply_text('Error.')

async def error_h(update, context):
    logger.error(str(context.error))

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_cmd))
    app.add_handler(CommandHandler('prompt', show_prompt))
    app.add_handler(CommandHandler('clear', clear_chat))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_error_handler(error_h)
    logger.info('Bot started')
    app.run_polling()

if __name__ == '__main__':
    main()
