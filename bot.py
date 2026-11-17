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
user_promo = {}
PROMO_CODES = {}

def get_user(user_id, username="Игрок"):
    if user_id not in USERS:
        USERS[user_id] = {
            "exp": 0, "purchases": 0, "stars": 20, "name": username,
            "last_bonus": 0, "last_roll": 0, "last_work": 0, 
            "business": 0, "mining": 0, "car": "Нет", "job": "Безработный",
            "last_passive": 0
        }
    return USERS[user_id]

def get_kb_page1(user_id):
    keyboard = [
        ["🛒 Config Nuar купить", "🎰 Рулетка"],
        ["🎮 Игры", "📦 Кейсы"],
        ["👤 Профиль", "🎁 Ежедневный бонус"],
        ["🆘 Поддержка", "➡️ Страница 2"]
    ]
    if user_id == ADMIN_ID:
        keyboard.append(["⚙️ Админ-панель"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_kb_page2():
    keyboard = [
        ["🏢 Бизнесы", "⛏ Майнинг-ферма"],
        ["👷 Работа", "🚗 Автосалон"],
        ["🏰 Кланы", "⚓️ Гавань"],
        ["🏆 Топы", "👥 Рефералы"],
        ["🎟 Промокод", "⬅️ Страница 1"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_to_menu_kb(user_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="back_to_main")]])

def get_admin_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"), InlineKeyboardButton("➕ Добавить конфиг", callback_data="admin_add")],
        [InlineKeyboardButton("🎁 Раздача", callback_data="admin_giveaway"), InlineKeyboardButton("🎟 Промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("🗑 Удалить конфиг", callback_data="admin_del"), InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Закрыть админку", callback_data="back_to_main")]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    name = update.effective_user.first_name
    u = get_user(user_id, name)
    text = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐"
    await update.message.reply_text(text, reply_markup=get_kb_page1(user_id))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = get_user(user_id)

    if text == "⚙️ Админ-панель" and user_id == ADMIN_ID:
        await update.message.reply_text("⚙️ *Удобная Админ-панель*", parse_mode="Markdown", reply_markup=get_admin_inline_kb())
        return

    now = time.time()
    if now - u["last_passive"] >= 3600:
        passive_income = (u["business"] * 5) + (u["mining"] * 2)
        if passive_income > 0:
            u["stars"] += passive_income
            u["last_passive"] = now
            await update.message.reply_text(f"💰 Пассивный доход: +{passive_income} ⭐")

    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Страница 2", reply_markup=get_kb_page2())
    elif text == "⬅️ Страница 1":
        await update.message.reply_text("🔥 Меню", reply_markup=get_kb_page1(user_id))
    elif text == "👤 Профиль":
        t = f"👤 *Профиль*\n⭐ Баланс: *{u['stars']}*\n💼 Работа: {u['job']}\n🏢 Бизнесов: {u['business']}"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page1(user_id))
    elif text == "📦 Кейсы":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("📦 Кейс (20 ⭐)", callback_data="case_20")]])
        await update.message.reply_text("Выбери кейс:", reply_markup=kb)
    elif text == "👷 Работа":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛵 Курьер (30 мин)", callback_data="job_courier")]])
        await update.message.reply_text("Выбери работу:", reply_markup=kb)
    elif text == "🚗 Автосалон":
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🚗 Lada (100 ⭐)", callback_data="car_lada")]])
        await update.message.reply_text("Выбери машину:", reply_markup=kb)
    elif text == "🆘 Поддержка":
        support_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✉️ Админ", url=f"tg://user?id={ADMIN_ID}")]])
        await update.message.reply_text("Напиши админу:", reply_markup=support_kb)
    elif text == "🎟 Промокод":
        await update.message.reply_text("Введи промокод:")
        context.user_data['state'] = 'awaiting_promo'
    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=get_kb_page1(user_id))

# --- ОБРАБОТЧИК INLINE КНОПОК (АДМИНКА И ПОКУПКИ) ---
async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u = get_user(user_id)

    if data.startswith("case_"):
        price = int(data.replace("case_", ""))
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Открыть за {price} ⭐", callback_data=f"confirm_case_{price}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Открыть кейс за {price} ⭐?", reply_markup=kb)
    elif data.startswith("confirm_case_"):
        price = int(data.replace("confirm_case_", ""))
        if u["stars"] >= price:
            u["stars"] -= price
            win = random.choice([0, price*2, price*5])
            u["stars"] += win
            await query.message.edit_text(f"🎉 Выигрыш: {win} ⭐!", reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Мало звезд.", reply_markup=get_back_to_menu_kb(user_id))
    elif data.startswith("job_"):
        job = data.replace("job_", "")
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Работать", callback_data=f"confirm_job_{job}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Работать {job}?", reply_markup=kb)
    elif data.startswith("confirm_job_"):
        u["last_work"] = time.time()
        earn = random.randint(10, 20)
        u["stars"] += earn
        await query.message.edit_text(f"👷 Заработал {earn} ⭐!", reply_markup=get_back_to_menu_kb(user_id))
    elif data == "buy_business":
        if u["stars"] >= 100:
            u["stars"] -= 100
            u["business"] += 1
            await query.message.edit_text("🏢 Бизнес куплен!", reply_markup=get_back_to_menu_kb(user_id))
        else: await query.message.edit_text("❌ Мало звезд.", reply_markup=get_back_to_menu_kb(user_id))
    elif data == "admin_stats":
        await query.message.edit_text(f"📊 Юзеров: {len(USERS)}\n📦 Конфигов: {len(PRODUCTS)}", reply_markup=get_admin_inline_kb())
    elif data == "admin_add":
        await query.message.edit_text("Введи: `Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown")
        context.user_data['state'] = 'awaiting_product'
    elif data == "admin_giveaway":
        await query.message.edit_text("Отправь текст раздачи:")
        context.user_data['state'] = 'awaiting_giveaway'
    elif data == "admin_promo":
        await query.message.edit_text("Введи: `КОД СКИДКА`")
        context.user_data['state'] = 'awaiting_create_promo'
    elif data == "admin_broadcast":
        await query.message.edit_text("Отправь текст для всех:")
        context.user_data['state'] = 'awaiting_broadcast'
    elif data == "back_to_main":
        await query.message.delete()
        await query.message.chat.send_message("🔥 Меню", reply_markup=get_kb_page1(user_id))
    elif data.startswith("buy_"):
        await query.message.edit_text("✅ Конфиг куплен!", reply_markup=get_back_to_menu_kb(user_id))
        # --- ОБРАБОТКА ТЕКСТА (АДМИНКА И ПРОМО) ---
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
            await update.message.reply_text("✅ Конфиг добавлен!", reply_markup=get_kb_page1(user_id))
        else:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None
    elif state == 'awaiting_giveaway' and user_id == ADMIN_ID:
        for uid in USERS.keys():
            try:
                get_user(uid)["stars"] += 10
                await context.bot.send_message(uid, f"🎁 РАЗДАЧА!\n{text}\n+10 ⭐")
            except: pass
        await update.message.reply_text("✅ Раздача завершена!", reply_markup=get_kb_page1(user_id))
        context.user_data['state'] = None
    elif state == 'awaiting_create_promo' and user_id == ADMIN_ID:
        try:
            code, disc = text.split(" ")
            PROMO_CODES[code.upper()] = int(disc)
            await update.message.reply_text(f"✅ Промокод создан!", reply_markup=get_kb_page1(user_id))
        except:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None
    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        for uid in USERS.keys():
            try: await context.bot.send_message(uid, f"📢 {text}")
            except: pass
        await update.message.reply_text("✅ Отправлено!", reply_markup=get_kb_page1(user_id))
        context.user_data['state'] = None
    elif state == 'awaiting_promo':
        code = text.upper()
        if code in PROMO_CODES:
            user_promo[user_id] = PROMO_CODES[code]
            await update.message.reply_text(f"✅ Скидка {PROMO_CODES[code]}%!", reply_markup=get_kb_page2())
        else:
            await update.message.reply_text("❌ Неверный промокод.", reply_markup=get_kb_page2())
        context.user_data['state'] = None
    else:
        await handle_menu(update, context)

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(handle_inline))
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    import threading
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port), daemon=True).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
