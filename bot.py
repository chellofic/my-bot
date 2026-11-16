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

# --- БАЗОВЫЕ ФУНКЦИИ ---
def get_user(user_id, username="Игрок"):
    if user_id not in USERS:
        USERS[user_id] = {
            "exp": 0, "purchases": 0, "stars": 50, "name": username,
            "last_bonus": 0, "last_work": 0, "business": 0, "mining": 0, "car": "Нет"
        }
    return USERS[user_id]

def get_reply_kb_page1():
    keyboard = [
        ["🛒 Config Nuar купить", "🔮 Ночной Кристалл"],
        ["🎮 Игры", "📦 Кейсы"],
        ["👤 Профиль", "💎 Купить VIP"],
        ["🎁 Ежедневный бонус", "🆘 Поддержка"],
        ["➡️ Страница 2"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

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

# --- ОБРАБОТЧИК КНОПОК ВНИЗУ ---
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = get_user(user_id)

    # СТРАНИЦЫ
    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Меню — Страница 2", reply_markup=get_reply_kb_page2())
    elif text == "⬅️ Страница 1":
        t = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐"
        await update.message.reply_text(t, reply_markup=get_reply_kb_page1())

    # СТРАНИЦА 1
    elif text == "👤 Профиль":
        t = f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n⭐ Баланс: *{u['stars']}*\n🛍 Покупок: *{u['purchases']}*\n🏢 Бизнес: {u['business']}\n⛏ Майнинг: {u['mining']}\n🚗 Авто: {u['car']}"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_reply_kb_page1())

    elif text == "🎁 Ежедневный бонус":
        now = time.time()
        if now - u["last_bonus"] < 86400:
            await update.message.reply_text("⏳ Ты уже забирал бонус сегодня!", reply_markup=get_reply_kb_page1())
        else:
            u["last_bonus"] = now
            u["stars"] += 10
            await update.message.reply_text("🎁 Ты получил 10 звезд на баланс!", reply_markup=get_reply_kb_page1())

    elif text == "🛒 Config Nuar купить":
        if not PRODUCTS:
            await update.message.reply_text("📦 Каталог пуст.", reply_markup=get_reply_kb_page1())
            return
        await update.message.reply_text("🛒 *Доступные конфиги:*", parse_mode="Markdown", reply_markup=get_reply_kb_page1())
        for k, v in PRODUCTS.items():
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]])
            await update.message.reply_text(f"📦 *{v['name']}*\n{v['desc']}", reply_markup=kb, parse_mode="Markdown")

    elif text == "🎮 Игры":
        await update.message.reply_text("🎲 Бросай кубик! Напиши /dice, чтобы сыграть.", reply_markup=get_reply_kb_page1())

    elif text == "📦 Кейсы":
        if u["stars"] >= 20:
            u["stars"] -= 20
            win = random.choice(["10 ⭐", "0 ⭐", "50 ⭐", "Конфиг"])
            if win == "50 ⭐": u["stars"] += 50
            elif win == "10 ⭐": u["stars"] += 10
            await update.message.reply_text(f"📦 Ты открыл кейс за 20 ⭐ и выиграл: {win}!", reply_markup=get_reply_kb_page1())
        else:
            await update.message.reply_text("❌ Недостаточно звезд (нужно 20).", reply_markup=get_reply_kb_page1())

    # СТРАНИЦА 2
    elif text == "🏢 Бизнесы":
        price = 100
        if u["stars"] >= price:
            u["stars"] -= price
            u["business"] += 1
            await update.message.reply_text(f"🏢 Ты купил бизнес! Теперь он приносит +5 ⭐ в час.", reply_markup=get_reply_kb_page2())
        else:
            await update.message.reply_text(f"❌ Бизнес стоит {price} ⭐. У тебя недостаточно.", reply_markup=get_reply_kb_page2())

    elif text == "⛏ Майнинг-ферма":
        price = 50
        if u["stars"] >= price:
            u["stars"] -= price
            u["mining"] += 1
            await update.message.reply_text(f"⛏ Ты купил майнинг-ферму! +2 ⭐ в час.", reply_markup=get_reply_kb_page2())
        else:
            await update.message.reply_text(f"❌ Ферма стоит {price} ⭐.", reply_markup=get_reply_kb_page2())

    elif text == "👷 Работа":
        now = time.time()
        if now - u["last_work"] < 3600:
            await update.message.reply_text("⏳ Ты устал. Отдохни 1 час.", reply_markup=get_reply_kb_page2())
        else:
            u["last_work"] = now
            earn = random.randint(5, 15)
            u["stars"] += earn
            await update.message.reply_text(f"👷 Ты поработал и заработал {earn} ⭐!", reply_markup=get_reply_kb_page2())

    elif text == "🚗 Автосалон":
        if u["stars"] >= 200:
            u["stars"] -= 200
            u["car"] = "BMW M5"
            await update.message.reply_text("🚗 Ты купил BMW M5! Статус +100.", reply_markup=get_reply_kb_page2())
        else:
            await update.message.reply_text("❌ Авто стоит 200 ⭐.", reply_markup=get_reply_kb_page2())

    elif text == "🏆 Топы":
        top_users = sorted(USERS.items(), key=lambda x: x[1]['stars'], reverse=True)[:5]
        text_top = "🏆 *Топ 5 игроков по балансу:*\n\n"
        for i, (uid, data) in enumerate(top_users, 1):
            text_top += f"{i}. {data['name']} — {data['stars']} ⭐\n"
        await update.message.reply_text(text_top, parse_mode="Markdown", reply_markup=get_reply_kb_page2())

    elif text == "👥 Рефералы":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        t = f"👥 *Пригласи друга!*\n\nТвоя ссылка:\n`{link}`\n\nЗа друга ты получишь 20 ⭐"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_reply_kb_page2())

    elif text == "🎟 Промокод":
        await update.message.reply_text("Введи промокод (например, NUAR2026):", reply_markup=get_reply_kb_page2())
        context.user_data['state'] = 'awaiting_promo'

    elif text in ["🏰 Кланы", "⚓️ Гавань"]:
        await update.message.reply_text("🛠 Скоро добавим!", reply_markup=get_reply_kb_page2())

    # АДМИНКА (ПО КОМАНДЕ)
    elif text == "⚙️ Админка" and user_id == ADMIN_ID:
        kb = [
            ["➕ Добавить конфиг", "🎁 Создать раздачу"],
            ["📊 Статистика", "⬅️ Назад"]
        ]
        await update.message.reply_text("⚙️ Админ-панель", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))

    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=get_reply_kb_page1())

# --- ИГРА В КУБИК ---
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = get_user(user_id)
    if u["stars"] < 10:
        await update.message.reply_text("❌ Нужно 10 ⭐ для игры.")
        return
    u["stars"] -= 10
    msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(4)
    
    if msg.dice.value in [4, 5, 6]:
        u["stars"] += 20
        await update.message.reply_text(f"🎉 Ты выиграл 20 ⭐! Выпало {msg.dice.value}.", reply_markup=get_reply_kb_page1())
    else:
        await update.message.reply_text(f"😢 Ты проиграл. Выпало {msg.dice.value}.", reply_markup=get_reply_kb_page1())

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
    
    await update.message.reply_text(f"✅ *Покупка успешна!*\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown", reply_markup=get_reply_kb_page1())

# --- АДМИН-ФУНКЦИИ ---
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
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
            await update.message.reply_text("✅ Конфиг добавлен!", reply_markup=get_reply_kb_page1())
            context.user_data['state'] = None
        else:
            await update.message.reply_text("❌ Ошибка формата.", reply_markup=get_reply_kb_page1())
    elif state == 'awaiting_promo':
        if update.message.text.upper() == "NUAR2026":
            u = get_user(update.effective_user.id)
            u["stars"] += 50
            await update.message.reply_text("✅ Промокод NUAR2026 активирован! +50 ⭐", reply_markup=get_reply_kb_page2())
        else:
            await update.message.reply_text("❌ Неверный промокод.", reply_markup=get_reply_kb_page2())
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
    app.add_handler(CommandHandler("dice", dice_game))
    app.add_handler(CommandHandler("admin", admin_add))
    app.add_handler(CommandHandler("panel", lambda u, c: u.message.reply_text("⚙️ Админка", reply_markup=ReplyKeyboardMarkup([["➕ Добавить конфиг", "🎁 Создать раздачу"], ["📊 Статистика", "⬅️ Назад"]], resize_keyboard=True)) if u.effective_user.id == ADMIN_ID else None))
    
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
