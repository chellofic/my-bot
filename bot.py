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

# --- БАЗЫ ДАННЫХ (В ПАМЯТИ) ---
PRODUCTS = {}
USERS = {} 
next_id = 1
user_promo = {}
PROMO_CODES = {} # Твои промокоды (Админ создает)

def get_user(user_id, username="Игрок"):
    if user_id not in USERS:
        USERS[user_id] = {
            "exp": 0, "purchases": 0, "stars": 50, "name": username,
            "last_bonus": 0, "last_roll": 0
        }
    return USERS[user_id]

# --- КЛАВИАТУРА ВНИЗУ (СТРАНИЦА 1) ---
def get_kb_page1():
    keyboard = [
        ["🛒 Купить конфиг", "🎰 Рулетка"],
        ["👤 Профиль", "🎁 Бонус"],
        ["🆘 Поддержка", "➡️ Страница 2"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# --- КЛАВИАТУРА ВНИЗУ (СТРАНИЦА 2) ---
def get_kb_page2():
    keyboard = [
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
        f"💎 Лучшие конфиги для Standoff 2 только здесь!"
    )
    await update.message.reply_text(text, reply_markup=get_kb_page1())

# --- ОБРАБОТЧИК КНОПОК ВНИЗУ ---
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = get_user(user_id)

    # СТРАНИЦЫ
    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Страница 2", reply_markup=get_kb_page2())
    elif text == "⬅️ Страница 1":
        t = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐"
        await update.message.reply_text(t, reply_markup=get_kb_page1())

    # СТРАНИЦА 1
    elif text == "👤 Профиль":
        t = f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n⭐ Баланс: *{u['stars']}*\n🛍 Покупок: *{u['purchases']}*"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page1())

    elif text == "🎁 Бонус":
        now = time.time()
        if now - u["last_bonus"] < 86400:
            await update.message.reply_text("⏳ Ты уже забирал бонус сегодня!", reply_markup=get_kb_page1())
        else:
            u["last_bonus"] = now
            u["stars"] += 10
            await update.message.reply_text("🎁 Ты получил 10 звезд на баланс!", reply_markup=get_kb_page1())

    elif text == "🛒 Купить конфиг":
        if not PRODUCTS:
            await update.message.reply_text("📦 Каталог пуст.", reply_markup=get_kb_page1())
            return
        await update.message.reply_text("🛒 *Доступные конфиги:*", parse_mode="Markdown")
        for k, v in PRODUCTS.items():
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]])
            await update.message.reply_text(f"📦 *{v['name']}*\n{v['desc']}", reply_markup=kb, parse_mode="Markdown")

    elif text == "🎰 Рулетка":
        now = time.time()
        if now - u["last_roll"] < 3600:
            await update.message.reply_text("⏳ Рулетка доступна раз в час.", reply_markup=get_kb_page1())
            return
        
        u["last_roll"] = now
        # Шанс выиграть звезды (50%), скидку (30%) или проигрыш (20%)
        prize = random.choices(["stars", "discount", "nothing"], weights=[50, 30, 20])[0]
        
        if prize == "stars":
            amount = random.randint(5, 20)
            u["stars"] += amount
            await update.message.reply_text(f"🎉 Ты выиграл {amount} ⭐!", reply_markup=get_kb_page1())
        elif prize == "discount":
            discount = random.choice([10, 15, 20])
            user_promo[user_id] = discount
            await update.message.reply_text(f"🎉 Ты выиграл скидку {discount}% на следующую покупку!", reply_markup=get_kb_page1())
        else:
            await update.message.reply_text("😢 В этот раз не повезло. Попробуй позже!", reply_markup=get_kb_page1())

    # СТРАНИЦА 2
    elif text == "🏆 Топы":
        top_users = sorted(USERS.items(), key=lambda x: x[1]['stars'], reverse=True)[:5]
        text_top = "🏆 *Топ 5 игроков по балансу:*\n\n"
        for i, (uid, data) in enumerate(top_users, 1):
            text_top += f"{i}. {data['name']} — {data['stars']} ⭐\n"
        await update.message.reply_text(text_top, parse_mode="Markdown", reply_markup=get_kb_page2())

    elif text == "👥 Рефералы":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        t = f"👥 *Пригласи друга!*\n\nТвоя ссылка:\n`{link}`\n\nЗа друга ты получишь 20 ⭐"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page2())

    elif text == "🎟 Промокод":
        await update.message.reply_text("Введи промокод:", reply_markup=get_kb_page2())
        context.user_data['state'] = 'awaiting_promo'

    # СЕКРЕТНАЯ АДМИНКА
    elif text == "⚙️ Админка" and user_id == ADMIN_ID:
        kb = [
            ["➕ Добавить конфиг", "🎟 Создать промокод"],
            ["📢 Рассылка", "⬅️ Назад"]
        ]
        await update.message.reply_text("⚙️ Админ-панель", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
        
    elif text == "➕ Добавить конфиг" and user_id == ADMIN_ID:
        await update.message.reply_text("Введи: `Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown")
        context.user_data['state'] = 'awaiting_product'

    elif text == "🎟 Создать промокод" and user_id == ADMIN_ID:
        await update.message.reply_text("Введи: `КОД СКИДКА` (например: `NUAR20 20`)")
        context.user_data['state'] = 'awaiting_create_promo'

    elif text == "📢 Рассылка" and user_id == ADMIN_ID:
        await update.message.reply_text("Отправь сообщение для всех:")
        context.user_data['state'] = 'awaiting_broadcast'

    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=get_kb_page1())

# --- ОПЛАТА ---
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    config_key = int(query.data.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    if not item: return

    user_id = query.from_user.id
    u = get_user(user_id)
    
    # Учет скидки
    discount = user_promo.get(user_id, 0)
    price = int(item['price'])
    if discount > 0:
        price = price - (price * discount // 100)
        
    if u["stars"] >= price:
        u["stars"] -= price
        u["purchases"] += 1
        if discount > 0: del user_promo[user_id] # Скидка сгорает
        await query.message.chat.send_message(f"✅ Ты купил *{item['name']}*!\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")
    else:
        await context.bot.send_invoice(chat_id=query.message.chat_id, title=item['name'], description=item['desc'], payload=f"buy_{config_key}", provider_token="", currency="XTR", prices=[LabeledPrice(label=item['name'], amount=price)])

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

# --- ОБРАБОТКА ВВОДА ТЕКСТА (АДМИН И ПРОМО) ---
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id

    if state == 'awaiting_product' and user_id == ADMIN_ID:
        parts = text.split(" | ")
        if len(parts) == 5:
            PRODUCTS[next_id] = {"name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]}
            next_id += 1
            await update.message.reply_text("✅ Конфиг добавлен!", reply_markup=get_kb_page1())
        else:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None

    elif state == 'awaiting_create_promo' and user_id == ADMIN_ID:
        try:
            code, disc = text.split(" ")
            PROMO_CODES[code.upper()] = int(disc)
            await update.message.reply_text(f"✅ Промокод {code.upper()} на {disc}% создан!", reply_markup=get_kb_page1())
        except:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None

    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        success = 0
        for uid in USERS.keys():
            try:
                await context.bot.send_message(uid, f"📢 {text}")
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Отправлено: {success} чел.", reply_markup=get_kb_page1())
        context.user_data['state'] = None

    elif state == 'awaiting_promo':
        code = text.upper()
        if code in PROMO_CODES:
            user_promo[user_id] = PROMO_CODES[code]
            await update.message.reply_text(f"✅ Промокод применен! Твоя скидка {PROMO_CODES[code]}%", reply_markup=get_kb_page2())
        else:
            await update.message.reply_text("❌ Неверный промокод.", reply_markup=get_kb_page2())
        context.user_data['state'] = None

    else:
        await handle_menu(update, context)

# --- ЗАПУСК ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    
    # Секретная команда для входа в админку (напиши /admin)
    app.add_handler(CommandHandler("admin", lambda u, c: u.message.reply_text("⚙️ Админ-панель", reply_markup=ReplyKeyboardMarkup([["➕ Добавить конфиг", "🎟 Создать промокод"], ["📢 Рассылка", "⬅️ Назад"]], resize_keyboard=True)) if u.effective_user.id == ADMIN_ID else None))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
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
