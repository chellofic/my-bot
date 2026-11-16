import os
import asyncio
import random
import time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

PRODUCTS = {}
USERS = {} 
next_id = 1

def get_user(user_id, username="Игрок"):
    if user_id not in USERS:
        USERS[user_id] = {"exp": 0, "purchases": 0, "stars": 50, "name": username}
    return USERS[user_id]

# --- КНОПКИ ВНИЗУ ЭКРАНА (PAGE 1) ---
def get_reply_kb_page1():
    keyboard = [
        ["🛒 Config Nuar купить", "🔮 Ночной Кристалл"],
        ["🎮 Игры", "📦 Кейсы"],
        ["👤 Профиль", "💎 Купить VIP"],
        ["🎁 Ежедневный бонус", "🆘 Поддержка"],
        ["➡️ Страница 2"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- КНОПКИ ВНИЗУ ЭКРАНА (PAGE 2) ---
def get_reply_kb_page2():
    keyboard = [
        ["🏢 Бизнесы", "⛏ Майнинг-ферма"],
        ["👷 Работа", "🚗 Автосалон"],
        ["🏰 Кланы", "⚓️ Гавань"],
        ["🏆 Топы", "👥 Рефералы"],
        ["🎟 Промокод", "⬅️ Страница 1"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- СТАРТ ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    u = get_user(user_id, name)
    
    text = (
        f"🔥 Главное меню NuarDLC\n"
        f"👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐\n"
        f"🔮 Участвуй в ивенте Ночной Кристалл и выигрывай топ-призы!"
    )
    await update.message.reply_text(text, reply_markup=get_reply_kb_page1())

# --- ОБРАБОТЧИК ТЕКСТА (КНОПОК ВНИЗУ) ---
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = get_user(user_id)

    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Меню — Страница 2", reply_markup=get_reply_kb_page2())
        
    elif text == "⬅️ Страница 1":
        t = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐"
        await update.message.reply_text(t, reply_markup=get_reply_kb_page1())

    elif text == "👤 Профиль":
        t = f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n⭐ Баланс: *{u['stars']}*\n🛍 Покупок: *{u['purchases']}*"
        await update.message.reply_text(t, parse_mode="Markdown")

    elif text == "🎁 Ежедневный бонус":
        now = time.time()
        if now - u.get("last_bonus", 0) < 86400:
            await update.message.reply_text("⏳ Ты уже забирал бонус сегодня!")
        else:
            u["last_bonus"] = now
            u["stars"] += 10
            await update.message.reply_text("🎁 Ты получил 10 звезд на баланс!")

    elif text == "🛒 Config Nuar купить":
        if not PRODUCTS:
            await update.message.reply_text("📦 Каталог пуст.")
            return
        
        await update.message.reply_text("🛒 *Доступные конфиги:*", parse_mode="Markdown")
        for k, v in PRODUCTS.items():
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]])
            await update.message.reply_text(f"📦 *{v['name']}*\n{v['desc']}", reply_markup=kb, parse_mode="Markdown")

    else:
        await update.message.reply_text("🛠 В разработке...", reply_markup=get_reply_kb_page1())

# --- ОПЛАТА ---
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config_key = int(query.data.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    if not item: return

    user_id = query.from_user.id
    u = get_user(user_id)
    price = int(item['price'])
    
    if u["stars"] >= price:
        u["stars"] -= price
        u["purchases"] += 1
        await query.message.chat.send_message(f"✅ Ты купил *{item['name']}* за звезды с баланса!\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")
    else:
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title=item['name'],
            description=item['desc'],
            payload=f"buy_{config_key}",
            provider_token="",
            currency="XTR",
            prices=[LabeledPrice(label=item['name'], amount=price)],
        )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    config_key = int(payload.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    user_id = update.effective_user.id
    u = get_user(user_id)
    u["purchases"] += 1
    
    await update.message.reply_text(f"✅ *Покупка успешна!*\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")

# --- АДМИНКА ---
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введи: `Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown")
    context.user_data['state'] = 'awaiting_product'

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    if state == 'awaiting_product':
        parts = update.message.text.split(" | ")
        if len(parts) == 5:
            PRODUCTS[next_id] = {"name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]}
            next_id += 1
            await update.message.reply_text("✅ Конфиг добавлен!")
            context.user_data['state'] = None
        else:
            await update.message.reply_text("❌ Ошибка формата.")
    else:
        await handle_menu(update, context)

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_add))
    
    # Обработка кнопок-клавиатуры
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_input))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    import threading
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port), daemon=True).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
