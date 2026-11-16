import os
import asyncio
import random
import time
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- БАЗЫ ДАННЫХ (В ПАМЯТИ) ---
PRODUCTS = {} # Твои конфиги
USERS = {} 
next_id = 1
user_promo = {} 

SETTINGS = {
    "welcome_text": "🔥 Главное меню NuarDLC",
}

def get_user(user_id, username="Игрок"):
    if user_id not in USERS:
        USERS[user_id] = {"exp": 0, "ref_by": None, "last_roll": 0, "purchases": 0, "stars": 50, "name": username}
    return USERS[user_id]

# --- ГЛАВНОЕ МЕНЮ (СТРАНИЦА 1) ---
def get_page_1(user_id):
    u = get_user(user_id)
    text = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐\n🔮 Участвуй в ивенте Ночной Кристалл и выигрывай топ-призы!"
    
    keyboard = [
        [InlineKeyboardButton("🛒 Config Nuar купить", callback_data="catalog"), InlineKeyboardButton("🔮 Ночной Кристалл", callback_data="event")],
        [InlineKeyboardButton("🎮 Игры", callback_data="games"), InlineKeyboardButton("📦 Кейсы", callback_data="cases")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile"), InlineKeyboardButton("💎 Купить VIP", callback_data="buy_vip")],
        [InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus"), InlineKeyboardButton("🆘 Поддержка", url=f"tg://user?id={ADMIN_ID}")],
        [InlineKeyboardButton("➡️ Страница 2", callback_data="page_2")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# --- ГЛАВНОЕ МЕНЮ (СТРАНИЦА 2) ---
def get_page_2(user_id):
    u = get_user(user_id)
    text = "📄 Меню — Страница 2"
    
    keyboard = [
        [InlineKeyboardButton("🏢 Бизнесы", callback_data="business"), InlineKeyboardButton("⛏ Майнинг-ферма", callback_data="mining")],
        [InlineKeyboardButton("👷 Работа", callback_data="job"), InlineKeyboardButton("🚗 Автосалон", callback_data="cars")],
        [InlineKeyboardButton("🏰 Кланы", callback_data="clans"), InlineKeyboardButton("⚓️ Гавань", callback_data="harbor")],
        [InlineKeyboardButton("🏆 Топы", callback_data="tops"), InlineKeyboardButton("👥 Рефералы", callback_data="ref_sys")],
        [InlineKeyboardButton("🎟 Промокод", callback_data="promo"), InlineKeyboardButton("⬅️ Страница 1", callback_data="page_1")]
    ]
    return text, InlineKeyboardMarkup(keyboard)

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад в меню", callback_data="back_to_main")]])

async def edit_msg(query, text, reply_markup=None):
    try:
        await query.message.edit_text(text=text, reply_markup=reply_markup, parse_mode="Markdown")
    except:
        await query.message.chat.send_message(text=text, reply_markup=reply_markup, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    get_user(user_id, name)
    
    text, markup = get_page_1(user_id)
    await update.message.reply_text(text, reply_markup=markup, parse_mode="Markdown")

# --- ПЕРЕКЛЮЧЕНИЕ СТРАНИЦ ---
async def page_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, markup = get_page_1(query.from_user.id)
    await edit_msg(query, text, markup)

async def page_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, markup = get_page_2(query.from_user.id)
    await edit_msg(query, text, markup)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text, markup = get_page_1(query.from_user.id)
    await edit_msg(query, text, markup)

# --- ЗАГЛУШКИ ДЛЯ КНОПОК (ЧТОБЫ НЕ ВИСЕЛИ) ---
async def placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🛠 В разработке...", show_alert=True)

# --- ЕЖЕДНЕВНЫЙ БОНУС ---
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u = get_user(user_id)
    now = time.time()
    
    if now - u.get("last_bonus", 0) < 86400:
        await query.answer("⏳ Ты уже забирал бонус сегодня!", show_alert=True)
        return
        
    u["last_bonus"] = now
    u["stars"] += 10
    await query.answer("🎁 Ты получил 10 звезд на баланс!", show_alert=True)
    
    text, markup = get_page_1(user_id)
    await edit_msg(query, text, markup)

# --- КАТАЛОГ (ТВОИ КОНФИГИ) ---
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if not PRODUCTS:
        await edit_msg(query, "📦 Каталог пока пуст. Админ скоро добавит товары.", get_back_menu())
        return
        
    for k, v in PRODUCTS.items():
        keyboard = [[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]]
        await query.message.chat.send_message(f"📦 *{v['name']}*\n\n{v['desc']}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    await query.message.chat.send_message("Выбери товар выше 👆", reply_markup=get_back_menu())

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
    u["stars"] += 10 # Бонус за покупку
    
    await update.message.reply_text(f"✅ *Покупка успешна!*\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")

# --- ПРОФИЛЬ ---
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    u = get_user(query.from_user.id)
    
    text = (
        f"👤 *Твой профиль*\n\n"
        f"🆔 ID: `{query.from_user.id}`\n"
        f"⭐ Баланс: *{u['stars']}*\n"
        f"🛍 Покупок: *{u['purchases']}*"
    )
    await edit_msg(query, text, get_back_menu())

# --- РЕФЕРАЛЫ ---
async def ref_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={query.from_user.id}"
    text = f"👥 *Пригласи друга!*\n\nТвоя ссылка:\n`{link}`\n\nЗа друга ты получишь 20 ⭐"
    await edit_msg(query, text, get_back_menu())

# --- АДМИНКА (ДОБАВЛЕНИЕ ТОВАРОВ) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить конфиг", callback_data="admin_add")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_main")]
    ]
    await edit_msg(query, "⚙️ Админ-панель:", InlineKeyboardMarkup(keyboard))

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await edit_msg(query, "Введи: `Название | Цена | Описание | Код | Ключ`", get_back_menu())
    context.user_data['state'] = 'awaiting_product'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    if not state: return

    if state == 'awaiting_product' and user_id == ADMIN_ID:
        parts = text.split(" | ")
        if len(parts) == 5:
            PRODUCTS[next_id] = {"name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]}
            next_id += 1
            await update.message.reply_text("✅ Конфиг добавлен!", reply_markup=get_back_menu())
            context.user_data['state'] = None
        else:
            await update.message.reply_text("❌ Ошибка формата.", reply_markup=get_back_menu())

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel)) # Секретная команда для входа в админку
    
    # Кнопки меню
    app.add_handler(CallbackQueryHandler(page_1, pattern="^page_1$"))
    app.add_handler(CallbackQueryHandler(page_2, pattern="^page_2$"))
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^back_to_main$"))
    app.add_handler(CallbackQueryHandler(daily_bonus, pattern="^daily_bonus$"))
    
    # Кнопки с товарами и профилем
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(ref_system, pattern="^ref_sys$"))
    
    # Админка
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    # Заглушки для остальных кнопок (Кейсы, Игры, Бизнесы и т.д.)
    placeholders = ["event", "games", "cases", "buy_vip", "business", "mining", "job", "cars", "clans", "harbor", "tops", "promo"]
    for p in placeholders:
        app.add_handler(CallbackQueryHandler(placeholder, pattern=f"^{p}$"))

    # Оплата
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
