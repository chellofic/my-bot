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

def get_admin_inline_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"), InlineKeyboardButton("➕ Добавить конфиг", callback_data="admin_add")],
        [InlineKeyboardButton("🎁 Раздача", callback_data="admin_giveaway"), InlineKeyboardButton("🎟 Промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("🗑 Удалить конфиг", callback_data="admin_del"), InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ Закрыть админку", callback_data="back_to_main")]
    ])

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
        await update.message.reply_text("⚙️ *Удобная Админ-панель*\nВыбери действие:", parse_mode="Markdown", reply_markup=get_admin_inline_kb())
        return

    now = time.time()
    if now - u["last_passive"] >= 3600:
        passive_income = (u["business"] * 5) + (u["mining"] * 2)
        if passive_income > 0:
            u["stars"] += passive_income
            u["last_passive"] = now
            await update.message.reply_text(f"💰 Ты получил пассивный доход: +{passive_income} ⭐")

    if text == "➡️ Страница 2":
        await update.message.reply_text("📄 Страница 2", reply_markup=get_kb_page2())
    elif text == "⬅️ Страница 1":
        await update.message.reply_text("🔥 Главное меню", reply_markup=get_kb_page1(user_id))

    elif text == "👤 Профиль":
        t = (f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n⭐ Баланс: *{u['stars']}*\n"
             f"🛍 Покупок: *{u['purchases']}*\n💼 Работа: {u['job']}\n🚗 Машина: {u['car']}\n"
             f"🏢 Бизнесов: {u['business']}\n⛏ Ферм: {u['mining']}")
        await update.message.reply_text(t, parse_mode="Markdown", reply_markup=get_kb_page1(user_id))

    elif text == "🛒 Config Nuar купить":
        if not PRODUCTS:
            await update.message.reply_text("📦 Каталог пуст.", reply_markup=get_kb_page1(user_id))
            return
        await update.message.reply_text("🛒 *Доступные конфиги:*", parse_mode="Markdown")
        for k, v in PRODUCTS.items():
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"💳 Купить за {v['price']} ⭐", callback_data=f"buy_{k}")]])
            await update.message.reply_text(f"📦 *{v['name']}*\n{v['desc']}", reply_markup=kb, parse_mode="Markdown")

    elif text == "📦 Кейсы":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📦 Дешевый кейс (20 ⭐)", callback_data="case_20")],
            [InlineKeyboardButton("🎁 Дорогой кейс (50 ⭐)", callback_data="case_50")],
            [InlineKeyboardButton("💎 Легендарный кейс (100 ⭐)", callback_data="case_100")]
        ])
        await update.message.reply_text("Выбери кейс для открытия:", reply_markup=kb)

    elif text == "👷 Работа":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛵 Курьер (10-20 ⭐, 30 мин)", callback_data="job_courier")],
            [InlineKeyboardButton("💻 Программист (30-50 ⭐, 1 час)", callback_data="job_dev")],
            [InlineKeyboardButton("🎥 Стример (50-100 ⭐, 2 часа)", callback_data="job_streamer")]
        ])
        await update.message.reply_text("Выбери профессию:", reply_markup=kb)

    elif text == "🚗 Автосалон":
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚗 Lada (100 ⭐)", callback_data="car_lada")],
            [InlineKeyboardButton("🏎 BMW (300 ⭐)", callback_data="car_bmw")],
            [InlineKeyboardButton("🚀 Bugatti (1000 ⭐)", callback_data="car_bugatti")]
        ])
        await update.message.reply_text("Выбери машину:", reply_markup=kb)

    elif text == "🎰 Рулетка":
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
        if now - u["last_bonus"] < 86400:
            await update.message.reply_text("⏳ Ты уже забирал бонус сегодня!", reply_markup=get_kb_page1(user_id))
        else:
            u["last_bonus"] = now
            u["stars"] += 10
            await update.message.reply_text("🎁 Ты получил 10 звезд на баланс!", reply_markup=get_kb_page1(user_id))

    elif text == "🆘 Поддержка":
        support_kb = InlineKeyboardMarkup([[InlineKeyboardButton("✉️ Написать админу", url=f"tg://user?id={ADMIN_ID}")]])
        await update.message.reply_text("Нажми на кнопку ниже, чтобы написать админу:", reply_markup=support_kb)

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

# --- ОБРАБОТЧИК INLINE КНОПОК ---
async def handle_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    u = get_user(user_id)

    if data.startswith("case_"):
        price = int(data.replace("case_", ""))
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(f"✅ Открыть за {price} ⭐", callback_data=f"confirm_case_{price}"), InlineKeyboardButton("❌ Отмена", callback_data="back_to_main")]])
        await query.message.edit_text(f"Ты уверен, что хочешь открыть кейс за {price} ⭐?", reply_markup=kb)
        
    elif data.startswith("confirm_case_"):
        price = int(data.replace("confirm_case_", ""))
        if u["stars"] >= price:
            u["stars"] -= price
            msg = await query.message.edit_text("📦 Открываем кейс...")
            await asyncio.sleep(1)
            await msg.edit_text("📦 Крутим...")
            await asyncio.sleep(1)
            
            win = random.choices(["nothing", "stars", "big_stars", "discount"], weights=[50, 30, 15, 5])[0]
            if win == "nothing":
                await msg.edit_text("😢 Кейс оказался пустым.", reply_markup=get_back_to_menu_kb(user_id))
            elif win == "stars":
                amount = int(price * 1.5)
                u["stars"] += amount
                await msg.edit_text(f"🎉 Ты выиграл {amount} ⭐!", reply_markup=get_back_to_menu_kb(user_id))
            elif win == "big_stars":
                amount = price * 5
                u["stars"] += amount
                await msg.edit_text(f"💎 ДЖЕКПОТ! Ты выиграл {amount} ⭐!", reply_markup=get_back_to_menu_kb(user_id))
            else:
                discount = random.choice([10, 20, 30])
                user_promo[user_id] = discount
                await msg.edit_text(f"🎟 Ты выиграл скидку {discount}%!", reply_markup=get_back_to_menu_kb(user_id))
        else:
            await query.message.edit_text("❌ Недостаточно звезд.", reply_markup=get_back_to_menu_kb(user_id))

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
        
        if random.random() < 0.1:
            earn = -int(earn / 2)
            await query.message.edit_text(f"👷 Ты облажался на работе и потерял {abs(earn)} ⭐!", reply_markup=get_back_to_menu_kb(user_id))
        else:
            u["stars"] += earn
            u["job"] = {"courier": "Курьер", "dev": "Программист", "streamer": "Стример"}[job]
            await query.message.edit_text(f"👷 Ты отработал смену и заработал {earn} ⭐!", reply_markup=get_back_to_menu_kb(user_id))

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

    elif data == "admin_stats":
        await query.message.edit_text(f"📊 Статистика:\n\n👥 Юзеров: {len(USERS)}\n🛍 Покупок: {sum(x['purchases'] for x in USERS.values())}\n📦 Конфигов: {len(PRODUCTS)}", reply_markup=get_admin_inline_kb())
    elif data == "admin_add":
        await query.message.edit_text("Введи данные: `Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown")
        context.user_data['state'] = 'awaiting_product'
    elif data == "admin_giveaway":
        await query.message.edit_text("Отправь текст раздачи (его получат все + 10 ⭐):")
        context.user_data['state'] = 'awaiting_giveaway'
    elif data == "admin_promo":
        await query.message.edit_text("Введи: `КОД СКИДКА` (например: `NUAR20 20`)")
        context.user_data['state'] = 'awaiting_create_promo'
    elif data == "admin_del":
        if not PRODUCTS:
            await query.message.edit_text("Каталог пуст.", reply_markup=get_admin_inline_kb())
            return
        text_list = "Введи ID конфига для удаления:\n\n"
        for k, v in PRODUCTS.items(): text_list += f"ID {k}: {v['name']}\n"
        await query.message.edit_text(text_list)
        context.user_data['state'] = 'awaiting_delete_product'
    elif data == "admin_broadcast":
        await query.message.edit_text("Отправь сообщение для всех:")
        context.user_data['state'] = 'awaiting_broadcast'
    elif data == "back_to_main":
        await query.message.delete()
        await query.message.chat.send_message("🔥 Главное меню", reply_markup=get_kb_page1(user_id))
        
    elif data.startswith("buy_"):
        config_key = int(data.replace("buy_", ""))
        item = PRODUCTS.get(config_key)
        if not item: return
        discount = user_promo.get(user_id, 0)
        price = int(item['price'])
        if discount > 0: price = price - (price * discount // 100)
        if u["stars"] >= price:
            u["stars"] -= price
            u["purchases"] += 1
            if discount > 0: del user_promo[user_id]
            await query.message.chat.send_message(f"✅ Ты купил *{item['name']}*!\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")
        else:
            await context.bot.send_invoice(chat_id=query.message.chat_id, title=item['name'], description=item['desc'], payload=f"buy_{config_key}", provider_token="", currency="XTR", prices=[LabeledPrice(label=item['name'], amount=price)])

# --- ОБРАБОТКА ВВОДА ---
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
        success = 0
        for uid in USERS.keys():
            try:
                u = get_user(uid)
                u["stars"] += 10
                await context.bot.send_message(uid, f"🎁 РАЗДАЧА ОТ АДМИНА!\n\n{text}\n\n+10 ⭐ на баланс!")
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Раздача завершена! Доставлено: {success} чел.", reply_markup=get_kb_page1(user_id))
        context.user_data['state'] = None
    elif state == 'awaiting_create_promo' and user_id == ADMIN_ID:
        try:
            code, disc = text.split(" ")
            PROMO_CODES[code.upper()] = int(disc)
            await update.message.reply_text(f"✅ Промокод {code.upper()} создан!", reply_markup=get_kb_page1(user_id))
        except:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None
    elif state == 'awaiting_delete_product' and user_id == ADMIN_ID:
        try:
            del PRODUCTS[int(text)]
            await update.message.reply_text("✅ Конфиг удален!", reply_markup=get_kb_page1(user_id))
        except:
            await update.message.reply_text("❌ Неверный ID.", reply_markup=get_kb_page1(user_id))
        context.user_data['state'] = None
    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        success = 0
        for uid in USERS.keys():
            try:
                await context.bot.send_message(uid, f"📢 {text}")
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Отправлено: {success} чел.", reply_markup=get_kb_page1(user_id))
        context.user_data['state'] = None
    elif state == 'awaiting_promo':
    if code in PROMO_CODES:
            user_promo[user_id] = PROMO_CODES[code]
            await update.message.reply_text(f"✅ Скидка {PROMO_CODES[code]}%!", reply_markup=get_kb_page2())
        else:
            await update.message.reply_text("❌ Неверный промокод.", reply_markup=get_kb_page2())
        context.user_data['state'] = None
    else:
        await handle_menu(update, context)

# --- КУБИК ---
async def dice_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = get_user(user_id)
    if u["stars"] < 10:
        await update.message.reply_text("❌ Нужно 10 ⭐.")
        return
    u["stars"] -= 10
    msg = await update.message.reply_dice(emoji="🎲")
    await asyncio.sleep(4)
    if msg.dice.value in [4, 5, 6]:
        u["stars"] += 20
        await update.message.reply_text(f"🎉 Ты выиграл 20 ⭐!", reply_markup=get_kb_page1(user_id))
    else:
        await update.message.reply_text(f"😢 Проигрыш.", reply_markup=get_kb_page1(user_id))

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    config_key = int(payload.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    user_id = update.effective_user.id
    get_user(user_id)["purchases"] += 1
    await update.message.reply_text(f"✅ *Покупка успешна!*\n\nКлюч: `{item['key']}`\nКонфиг: `{item['text']}`", parse_mode="Markdown")

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("dice", dice_game))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    app.add_handler(CallbackQueryHandler(handle_inline))
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
