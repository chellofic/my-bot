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
            "exp": 0, "purchases": 0, "stars": 50, "name": username,
            "last_bonus": 0, "last_roll": 0, "last_work": 0, "business": 0, "mining": 0,
            "car": "Нет", "job": "Безработный"
        }
    return USERS[user_id]

# --- КЛАВИАТУРА (СТРАНИЦА 1) ---
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

# --- КЛАВИАТУРА (СТРАНИЦА 2) ---
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
    await update.message.reply_text(text, reply_markup=get_kb_page1(user_id))

# --- ОБРАБОТЧИК КНОПОК ---
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    u = get_user(user_id)

    if text == "⚙️ Админ-панель" and user_id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"), InlineKeyboardButton("➕ Добавить конфиг", callback_data="admin_add")],
            [InlineKeyboardButton("🎁 Раздача", callback_data="admin_giveaway"), InlineKeyboardButton("🎟 Промокод", callback_data="admin_promo")],
            [InlineKeyboardButton("🗑 Удалить конфиг", callback_data="admin_del"), InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⬅️ Закрыть админку", callback_data="back_to_main")]
        ]
        await update.message.reply_text("⚙️ *Удобная Админ-панель*\nВыбери действие:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Страница 2", reply_markup=get_kb_page2())
    elif text == "⬅️ Страница 1":
        await update.message.reply_text("🔥 Главное меню", reply_markup=get_kb_page1(user_id))

    elif text == "👤 Профиль":
        t = f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n⭐ Баланс: *{u['stars']}*\n🛍 Покупок: *{u['purchases']}*\n💼 Работа: {u['job']}\n🚗 Машина: {u['car']}"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page1(user_id))

    elif text == "🛒 Config Nuar купить":
        if not PRODUCTS:
            await update.message.reply_text("📦 Каталог пуст.", reply_markup=get_kb_page1(user_id))
            return
        await update.message.reply_text("🛒 *Доступные конфиги:*", parse_mode="Markdown")
        for k, v in PRODUCTS.items():
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]])
            await update.message.reply_text(f"📦 *{v['name']}*\n{v['desc']}", reply_markup=kb, parse_mode="Markdown")

    # --- НОВЫЕ КЕЙСЫ С ВЫБОРОМ ---
    elif text == "📦 Кейсы":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Дешевый кейс (20 ⭐)", callback_data="case_20")],
            [InlineKeyboardButton("🎁 Дорогой кейс (50 ⭐)", callback_data="case_50")],
            [InlineKeyboardButton("💎 Легендарный кейс (100 ⭐)", callback_data="case_100")]
        ])
        await update.message.reply_text("Выбери кейс для открытия:", reply_markup=kb)

    # --- НОВАЯ РАБОТА С ВЫБОРОМ ---
    elif text == "👷 Работа":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛵 Курьер (10-20 ⭐, 30 мин)", callback_data="job_courier")],
            [InlineKeyboardButton("💻 Программист (30-50 ⭐, 1 час)", callback_data="job_dev")],
            [InlineKeyboardButton("🎥 Стример (50-100 ⭐, 2 часа)", callback_data="job_streamer")]
        ])
        await update.message.reply_text("Выбери профессию:", reply_markup=kb)

    # --- НОВЫЙ АВТОСАЛОН С ВЫБОРОМ ---
    elif text == "🚗 Автосалон":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚗 Lada (100 ⭐)", callback_data="car_lada")],
            [InlineKeyboardButton("🏎 BMW (300 ⭐)", callback_data="car_bmw")],
            [InlineKeyboardButton("🚀 Bugatti (1000 ⭐)", callback_data="car_bugatti")]
        ])
        await update.message.reply_text("Выбери машину:", reply_markup=kb)

    elif text == "🎰 Рулетка":
        now = time.time()
        if now - u["last_roll"] < 3600:
            await update.message.reply_text("⏳ Рулетка доступна раз в час.", reply_markup=get_kb_page1(user_id))
            return
        u["last_roll"] = now
        prize = random.choices(["stars", "discount", "nothing"], weights=[50, 30, 20])[0]
        
        if prize == "stars":
            amount = random.randint(5, 20)
            u["stars"] += amount
            await update.message.reply_text(f"🎉 Ты выиграл {amount} ⭐!", reply_markup=get_kb_page1(user_id))
        elif prize == "discount":
            discount = random.choice([10, 15, 20])
            user_promo[user_id] = discount
            await update.message.reply_text(f"🎉 Ты выиграл скидку {discount}%!", reply_markup=get_kb_page1(user_id))
        else:
            await update.message.reply_text("😢 Не повезло.", reply_markup=get_kb_page1(user_id))

    elif text == "🎁 Ежедневный бонус":
        now = time.time()
        if now - u["last_bonus"] < 86400:
            await update.message.reply_text("⏳ Ты уже забирал бонус сегодня!", reply_markup=get_kb_page1(user_id))
        else:
            u["last_bonus"] = now
            u["stars"] += 10
            await update.message.reply_text("🎁 Ты получил 10 звезд на баланс!", reply_markup=get_kb_page1(user_id))

    elif text == "🆘 Поддержка":
        support_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✉️ Написать админу", url=f"tg://user?id={ADMIN_ID}")]])
        await update.message.reply_text("Нажми на кнопку ниже, чтобы написать админу:", reply_markup=support_kb)

    # --- ОСТАЛЬНАЯ СТРАНИЦА 2 ---
    elif text == "🏢 Бизнесы":
        if u["stars"] >= 100:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Купить бизнес (100 ⭐)", callback_data="buy_business"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
            await update.message.reply_text("Вы точно хотите купить бизнес за 100 ⭐? (Приносит +5 ⭐ в час)", reply_markup=kb)
        else:
            await update.message.reply_text("❌ Нужно 100 ⭐.", reply_markup=get_kb_page2())

    elif text == "⛏ Майнинг-ферма":
        if u["stars"] >= 50:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Купить ферму (50 ⭐)", callback_data="buy_mining"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
            await update.message.reply_text("Вы точно хотите купить майнинг-ферму за 50 ⭐? (Приносит +2 ⭐ в час)", reply_markup=kb)
        else:
            await update.message.reply_text("❌ Нужно 50 ⭐.", reply_markup=get_kb_page2())

    elif text == "🏆 Топы":
        top_users = sorted(USERS.items(), key=lambda x: x[1]['stars'], reverse=True)[:5]
        text_top = "🏆 *Топ 5 игроков:*\n\n"
        for i, (uid, data) in enumerate(top_users, 1):
            text_top += f"{i}. {data['name']} — {data['stars']} ⭐\n"
        await update.message.reply_text(text_top, parse_mode="Markdown", reply_markup=get_kb_page2())

    elif text == "👥 Рефералы":
        bot_info = await context.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={user_id}"
        t = f"👥 *Пригласи друга!*\n\nТвоя ссылка:\n`{link}`\n\nЗа друга получишь 20 ⭐"
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page2())

    elif text == "🎟 Промокод":
        await update.message.reply_text("Введи промокод:", reply_markup=get_kb_page2())
        context.user_data['state'] = 'awaiting_promo'

    else:
        await update.message.reply_text("Неизвестная команда.", reply_markup=get_kb_page1(user_id))

# --- ОБРАБОТЧИК ВСЕХ INLINE КНОПОК ---
async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u = get_user(user_id)

    # --- ПОДТВЕРЖДЕНИЕ КЕЙСОВ ---
    if data.startswith("case_"):
        price = int(data.replace("case_", ""))
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Открыть за {price} ⭐", callback_data=f"confirm_case_{price}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Ты уверен, что хочешь открыть кейс за {price} ⭐?", reply_markup=kb)
        
    elif data.startswith("confirm_case_"):
        price = int(data.replace("confirm_case_", ""))
        if u["stars"] >= price:
            u["stars"] -= price
            win = random.choices(["nothing", "stars", "big_stars"], weights=[60, 30, 10])[0]
            if win == "nothing":
                msg = "😢 Кейс оказался пустым."
            elif win == "stars":
                amount = price * 2
                u["stars"] += amount
                msg = f"🎉 Ты выиграл {amount} ⭐!"
            else:
                amount = price * 5
                u["stars"] += amount
                msg = f"💎 ДЖЕКПОТ! Ты выиграл {amount} ⭐!"
            await query.message.edit_text(msg, reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Недостаточно звезд.", reply_markup=get_back_to_menu_kb(user_id))

    # --- ПОДТВЕРЖДЕНИЕ РАБОТЫ ---
    elif data.startswith("job_"):
        job = data.replace("job_", "")
        jobs = {
            "courier": ("🛵 Курьер", "10-20 ⭐", "30 минут"),
            "dev": ("💻 Программист", "30-50 ⭐", "1 час"),
            "streamer": ("🎥 Стример", "50-100 ⭐", "2 часа")
        }
        name, pay, cd = jobs[job]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ Устроиться", callback_data=f"confirm_job_{job}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Ты хочешь работать *{name}*?\nОплата: {pay}\nКулдаун: {cd}", parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("confirm_job_"):
        job = data.replace("confirm_job_", "")
        now = time.time()
        cooldowns = {"courier": 1800, "dev": 3600, "streamer": 7200}
        
        if now - u["last_work"] < cooldowns[job]:
            await query.message.edit_text("⏳ Ты еще не отдохнул от прошлой работы.", reply_markup=get_back_to_menu_kb(user_id))
            return
            
        u["last_work"] = now
        jobs_pay = {"courier": (10, 20), "dev": (30, 50), "streamer": (50, 100)}
        earn = random.randint(*jobs_pay[job])
        u["stars"] += earn
        u["job"] = {"courier": "Курьер", "dev": "Программист", "streamer": "Стример"}[job]
        
        await query.message.edit_text(f"👷 Ты отработал смену и заработал {earn} ⭐!", reply_markup=get_back_to_menu_kb(user_id))

    # --- ПОДТВЕРЖДЕНИЕ АВТО ---
    elif data.startswith("car_"):
        car = data.replace("car_", "")
        cars = {"lada": ("🚗 Lada", 100), "bmw": ("🏎 BMW", 300), "bugatti": ("🚀 Bugatti", 1000)}
        name, price = cars[car]
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Купить за {price} ⭐", callback_data=f"confirm_car_{car}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Ты хочешь купить *{name}* за {price} ⭐?", parse_mode="Markdown", reply_markup=kb)

    elif data.startswith("confirm_car_"):
        car = data.replace("confirm_car_", "")
        cars = {"lada": ("🚗 Lada", 100), "bmw": ("🏎 BMW", 300), "bugatti": ("🚀 Bugatti", 1000)}
        name, price = cars[car]
        if u["stars"] >= price:
            u["stars"] -= price
            u["car"] = name
            await query.message.edit_text(f"✅ Ты купил {name}!", reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Недостаточно звезд.", reply_markup=get_back_to_menu_kb(user_id))

    # --- БИЗНЕС И МАЙНИНГ ---
    elif data == "buy_business":
        if u["stars"] >= 100:
            u["stars"] -= 100
            u["business"] += 1
            await query.message.edit_text("🏢 Бизнес куплен! +5 ⭐ в час.", reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Недостаточно звезд.", reply_markup=get_back_to_menu_kb(user_id))

    elif data == "buy_mining":
        if u["stars"] >= 50:
            u["stars"] -= 50
            u["mining"] += 1
            await query.message.edit_text("⛏ Ферма куплена! +2 ⭐ в час.", reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Недостаточно звезд.", reply_markup=get_back_to_menu_kb(user_id))

    # --- ВОЗВРАТ В МЕНЮ ---
    elif data == "back_to_main":
        await query.message.delete()
        t = f"🔥 Главное меню NuarDLC\n👤 Игрок: {u['name']} | Баланс: {u['stars']} ⭐"
        await query.message.chat.send_message(t, reply_markup=get_kb_page1(user_id))

    # --- ОСТАЛЬНОЕ (АДМИНКА И Т.Д.) ---
    elif data.startswith("admin_"):
        # ... логика админки ...
        pass
    elif data.startswith("buy_"):
        # ... логика покупки конфигов ...
        pass

# --- ОБРАБОТКА ВВОДА (АДМИНКА И ПРОМОКОДЫ) ---
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

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(handle_inline))
    app.add_handler(PreCheckoutQueryHandler(lambda u, c: u.pre_checkout_query.answer(ok=True)))
    
    async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
        payload = update.message.successful_payment.invoice_payload
        config_key = int(payload.replace("buy_", ""))
        item = PRODUCTS.get(config_key)
        user_id = update.effective_user.id
        get_user(user_id)["purchases"] += 1
        await update.message.reply_text(f"✅ *Покупка успешна!*\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")

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
