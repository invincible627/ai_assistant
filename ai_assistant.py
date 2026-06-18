from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from telegram import Update, ReplyKeyboardMarkup
import telegram.error
from dotenv import load_dotenv
import os
import aiofiles
from google import genai
from flask import Flask
import threading
app = Flask(__name__)
@app.route('/')
def keep_alive_endpoint():
    return "Bot is running!", 200
def start_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
def keep_alive():
    t = threading.Thread(target=start_web_server)
    t.daemon = True
    t.start()
load_dotenv()
administrator_ids = os.getenv("administrators_id")
api_key = os.getenv("api_key")
bot_token = os.getenv("token")
async def save_user_id(user_id):
    try:
        async with aiofiles.open("users_id_list.txt", "r") as users_ids_file:
            content_of_users_ids_list = await users_ids_file.read()
        if str(user_id) not in content_of_users_ids_list:
            async with aiofiles.open("users_id_list.txt", "a") as users_ids_file:
                await users_ids_file.write(str(user_id) + "\n")
    except FileNotFoundError:
        async with aiofiles.open("users_id_list.txt", "w") as users_ids_file:
            await users_ids_file.write(str(user_id) + "\n")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_starts_bot = update.message.from_user.id
    await save_user_id(user_id_starts_bot)
    buttons = [["شروع"], ["راهنما"]]
    if str(user_id_starts_bot) in administrator_ids.split(","):
        buttons.append(["اطلاع رسانی"])
    welcome_message = "سلام، به دستیار هوش مصنوعی خوش آمدید"
    start_and_help_keyboard = ReplyKeyboardMarkup(buttons, resize_keyboard=True)
    await update.message.reply_text(welcome_message, reply_markup = start_and_help_keyboard)
async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_help = "به دستیار هوش مصنوعی خوشآمدید، شما میتوانید سؤالات خود را از هوش مصنوعی بپرسید و جواب سؤالتان را دریافت کنید"
    await update.message.reply_text(bot_help)
GET_MESSAGE = 0
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_message = "ادمین عزیز، لطفاً پیام خود را وارد کنید"
    await update.message.reply_text(admin_message)
    return GET_MESSAGE
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_sent = update.message.text
    try:
        async with aiofiles.open("users_id_list.txt", "r") as users_list_file:
            content_of_users_ids_list = await users_list_file.read()
            users_ids = content_of_users_ids_list.splitlines()
    except FileNotFoundError:
        users_ids = []
    for user_id in users_ids:
        try:
            await context.bot.send_message(chat_id = user_id, text = f"اطلاع رسانی از طرف ادمین: {admin_sent}")
        except telegram.error.TelegramError:
            continue
    success_send = "ادمین عزیز، پیام شما با موفقیت ارسال شد"
    await update.message.reply_text(success_send)
    return ConversationHandler.END
async def ask_gemini(user_message, chat_history, update):
    client = genai.Client(api_key=api_key)
    contents = []
    for message in chat_history:
        if message["role"] == "user":
            contents.append(message["content"])
        elif message["role"] == "assistant":
            contents.append(message["content"])
    contents.append(user_message)
    try:
        response = client.models.generate_content(
            model = genai.GenerativeModel("gemini-1.5-flash")
            contents=contents
        )
        return response.text
    except Exception as error:
        await update.message.reply_text(f"❌ خطا در ارتباط با هوش مصنوعی:\n{str(error)}")
        return "متاسفم، خطایی در ارتباط با هوش مصنوعی رخ داده است."
CONVERSATION_CHAT = 1
async def start_chat_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    await save_user_id(user_id)
    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = [
            {"role": "user", "content": "تو یک دستیار هوش مصنوعی مفید هستی که به زبان فارسی پاسخ می‌دهی."}
        ]
    welcome_chat_message = "سلام! هر سوالی دارید، بپرسید. من در خدمت شما هستم."
    await update.message.reply_text(welcome_chat_message)
    return CONVERSATION_CHAT
async def handle_chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    if not user_message or user_message.strip() == "":
        await update.message.reply_text("لطفاً یک پیام معتبر وارد کنید.")
        return CONVERSATION_CHAT
    if "chat_history" not in context.user_data:
        context.user_data["chat_history"] = [
            {"role": "user", "content": "تو یک دستیار هوش مصنوعی مفید هستی که به زبان فارسی پاسخ می‌دهی."}
        ]
    context.user_data["chat_history"].append({"role": "user", "content": user_message})
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    assistant_reply = await ask_gemini(user_message, context.user_data["chat_history"], update)
    context.user_data["chat_history"].append({"role": "assistant", "content": assistant_reply})
    if len(assistant_reply) > 4000:
        for i in range(0, len(assistant_reply), 4000):
            await update.message.reply_text(assistant_reply[i:i+4000])
    else:
        await update.message.reply_text(assistant_reply)
    return CONVERSATION_CHAT
async def cancel_chat_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مکالمه به پایان رسید. برای شروع مجدد از دکمه شروع استفاده کنید.")
    return ConversationHandler.END
filter_for_start = filters.Text(["شروع"])
filter_for_help = filters.Text(["راهنما"])
filter_for_broadcast = filters.Text(["اطلاع رسانی"])
broadcast_conversation = ConversationHandler(
    entry_points=[
        MessageHandler(filter_for_broadcast, broadcast)
    ],
    states={
        GET_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)]
    },
    fallbacks=[
        CommandHandler("start", start)
    ]
)
chat_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("start", start_chat_conversation),
        MessageHandler(filter_for_start, start_chat_conversation)
    ],
    states={
        CONVERSATION_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat_message)]
    },
    fallbacks=[
        CommandHandler("stop", cancel_chat_conversation),
        CommandHandler("start", start_chat_conversation)
    ]
)
ai_assistant_bot = ApplicationBuilder().token(bot_token).build()
ai_assistant_bot.add_handler(chat_conversation)
ai_assistant_bot.add_handler(MessageHandler(filter_for_help, help))
ai_assistant_bot.add_handler(broadcast_conversation)
keep_alive()
ai_assistant_bot.run_polling()