import os
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

CONFIGS = {
    "config_1": {
        "name": "Конфиг Nuar v1",
        "price": "40 руб.",
        "desc": "Конфиг от ангелка.",
        "text": "X0J500UYIH",
        "key": "FR1K5"
    },
    "config_2": {
        "name": "Конфиг Nuar v2",
        "price": "54 руб.",
        "desc": "Хэдшот конфиг.",
        "text": "QWERTY12345ASDFG",
        "key": "MB3KJ"
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("🛒 Каталог", callback_data="catalog")]]
    await update.message.reply_text("👋 Магазин работает 24/7. Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    for key, item in CONFIGS.items():
        text = f"📦 *{item['name']}*\n\n{item['desc']}\n\n💰 Цена: *{item['price']}*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{key}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config_key = query.data.replace("buy_", "")
    item = CONFIGS.get(config_key)
    
    await query.message.reply_text(f"✅ *Покупка (тест)*\nТовар: {item['name']}\nКлюч: `{item['key']}`", parse_mode="Markdown")
    await query.message.reply_text(item['text'])

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ RENDER НЕ ЗАКРЫВАЛ БОТА) ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "Bot is running"

# --- ПРАВИЛЬНЫЙ ЗАПУСК БОТА ---
if __name__ == "__main__":
    # Создаем приложение
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    
    # Запускаем бота в фоне через отдельный поток с правильным event loop
    def run_bot():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(app.run_polling())
        
    import threading
    threading.Thread(target=run_bot, daemon=True).start()
    
    # Запускаем веб-сервер (Render требует, чтобы приложение слушало порт)
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
