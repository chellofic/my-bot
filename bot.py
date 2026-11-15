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
PRODUCTS = {}
PROMOS = {}
REVIEWS = []
USERS = {} 
next_id = 1
user_promo = {} 

SETTINGS = {
    "welcome_text": "👋 Добро пожаловать в магазин Nuar!",
    "support_text": "🛡 Поддержка",
    "catalog_btn": "🛒 Каталог",
    "profile_btn": "👤 Профиль",
    "ref_btn": "👥 Пригласить друга",
    "roll_btn": "🎰 Рулетка"
}

def get_user(user_id):
    if user_id not in USERS:
        USERS[user_id] = {"exp": 0, "ref_by": None, "last_roll": 0, "purchases": 0}
    return USERS[user_id]

def get_level(exp):
    if exp < 100: return "🥉 Новичок", 0
    elif exp < 300: return "🥈 Про", 5
    elif exp < 600: return "🥇 Мастер", 10
    else: return "💎 Легенда", 20

def get_main_menu(user_id):
    is_admin = user_id == ADMIN_ID
    keyboard = [
        [InlineKeyboardButton(SETTINGS['catalog_btn'], callback_data="catalog")],
        [InlineKeyboardButton(SETTINGS['profile_btn'], callback_data="profile")],
        [InlineKeyboardButton(SETTINGS['roll_btn'], callback_data="roll")],
        [InlineKeyboardButton(SETTINGS['ref_btn'], callback_data="ref_sys")],
        [InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo")],
        [InlineKeyboardButton("💬 Оставить отзыв", callback_data="leave_review"), InlineKeyboardButton("⭐ Отзывы", callback_data="view_reviews")],
        [InlineKeyboardButton(SETTINGS['support_text'], url=f"tg://user?id={ADMIN_ID}")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ В главное меню", callback_data="back_menu")]])

# --- УДАЛЕНИЕ И ПАУЗА 0.3 СЕКУНДЫ ---
async def smooth_transition(query, text, reply_markup=None, parse_mode=None):
    try:
        await query.message.delete()
    except:
        pass
    
    await asyncio.sleep(0.3) # Твоя задержка
    
    await query.message.chat.send_message(
        text=text, 
        reply_markup=reply_markup, 
        parse_mode=parse_mode
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    user_id = update.effective_user.id
    u = get_user(user_id)
    
    if context.args and len(context.args) > 0:
        try:
            ref_id = int(context.args[0])
            if ref_id != user_id and u["ref_by"] is None:
                u["ref_by"] = ref_id
                await update.message.reply_text("✅ Ты пришел по приглашению друга!")
        except: pass

    await update.message.reply_text(SETTINGS['welcome_text'], reply_markup=get_main_menu(user_id))

async def roll_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    u = get_user(user_id)
    now = time.time()
    
    if now - u["last_roll"] < 86400:
        await smooth_transition(query, "⏳ Ты уже крутил сегодня. Приходи завтра!", get_back_menu())
        return
        
    u["last_roll"] = now
    prize_type = random.choices(["discount", "exp"], weights=[70, 30])[0]
    
    if prize_type == "discount":
        discount = random.choice([5, 10, 15, 20, 25, 30])
        user_promo[user_id] = discount
        text = f"🎉 Ты выиграл скидку *{discount}%* на следующую покупку!"
    else:
        amount = random.choice([20, 50, 100])
        u["exp"] += amount
        text = f"🎉 Ты выиграл *{amount} EXP*!"
        
    await smooth_transition(query, text, get_back_menu(), "Markdown")

async def ref_system(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    bot_info = await context.bot.get_me()
    link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    text = (
        f"👥 *Пригласи друга и получай бонусы!*\n\n"
        f"Твоя ссылка:\n`{link}`\n\n"
        f"За каждого приведенного друга ты получаешь +100 EXP."
    )
    await smooth_transition(query, text, get_back_menu(), "Markdown")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    u = get_user(user_id)
    level_name, level_discount = get_level(u["exp"])
    temp_discount = user_promo.get(user_id, 0)
    total_discount = level_discount + temp_discount
    
    text = (
        f"👤 *Твой профиль*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"🏆 Уровень: *{level_name}* (Скидка {level_discount}%)\n"
        f"🎁 Временная скидка: *{temp_discount}%*\n"
        f"🔥 *Общая скидка: {total_discount}%*\n\n"
        f"🛍 Покупок: *{u['purchases']}*\n"
        f"✨ EXP: *{u['exp']}*"
    )
    await smooth_transition(query, text, get_back_menu(), "Markdown")

async def promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await smooth_transition(query, "Отправь мне промокод:", get_back_menu())
    context.user_data['state'] = 'awaiting_promo_code'

async def leave_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await smooth_transition(query, "Напиши свой отзыв:", get_back_menu())
    context.user_data['state'] = 'awaiting_review'

async def view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not REVIEWS:
        await smooth_transition(query, "Пока нет отзывов.", get_back_menu())
        return
    text = "⭐ *Последние отзывы:*\n\n" + "\n\n".join([f"• {r}" for r in REVIEWS[-5:]])
    await smooth_transition(query, text, get_back_menu(), "Markdown")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config_key = int(query.data.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    if not item: return

    user_id = query.from_user.id
    u = get_user(user_id)
    _, level_discount = get_level(u["exp"])
    temp_discount = user_promo.get(user_id, 0)
    total_discount = level_discount + temp_discount
    
    if total_discount > 50: total_discount = 50
    
    price = int(item['price'])
    price_after_discount = price - (price * total_discount // 100)
    
    try: await query.message.delete()
    except: pass
    await asyncio.sleep(0.3)
    
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=item['name'],
        description=f"{item['desc']}\n(Твоя скидка: {total_discount}%)",
        payload=f"buy_{config_key}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=item['name'], amount=price_after_discount)],
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
    u["exp"] += 50
    
    if u["ref_by"]:
        ref_u = get_user(u["ref_by"])
        ref_u["exp"] += 100
        try:
            await context.bot.send_message(u["ref_by"], "🎉 Твой друг купил конфиг! Тебе начислено *100 EXP*", parse_mode="Markdown")
        except: pass

    await update.message.reply_text(
        f"✅ *Покупка успешна!*\n\n"
        f"Товар: {item['name']}\n"
        f"Ключ: `{item['key']}`",
        parse_mode="Markdown"
    )
    await update.message.reply_text(item['text'])
    await update.message.reply_text("Что-нибудь еще?", reply_markup=get_back_menu())

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    total_users = len(USERS)
    total_purchases = sum(u["purchases"] for u in USERS.values())
    text = f"📊 *Статистика*\n\n👥 Юзеров: *{total_users}*\n🛍 Покупок: *{total_purchases}*"
    await smooth_transition(query, text, get_back_menu(), "Markdown")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    if query.from_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="admin_delete")],
        [InlineKeyboardButton("🎟 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await smooth_transition(query, "⚙️ Админ-панель:", InlineKeyboardMarkup(keyboard))

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await smooth_transition(query, "Введи: `Название | Цена(число) | Описание | Код | Ключ`", get_back_menu(), "Markdown")
    context.user_data['state'] = 'awaiting_product'

async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not PRODUCTS:
        await smooth_transition(query, "Каталог пуст.", get_back_menu())
        return
    text = "Введи ID для удаления:\n\n"
    for k, v in PRODUCTS.items(): text += f"ID: {k} — {v['name']}\n"
    await smooth_transition(query, text, get_back_menu())
    context.user_data['state'] = 'awaiting_delete_id'

async def admin_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await smooth_transition(query, "Введи промокод и скидку (например: `NUAR50 50`):", get_back_menu())
    context.user_data['state'] = 'awaiting_promo'

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await smooth_transition(query, "Отправь сообщение для всех:", get_back_menu())
    context.user_data['state'] = 'awaiting_broadcast'

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
            await update.message.reply_text("✅ Товар добавлен!", reply_markup=get_back_menu())
            context.user_data['state'] = None
        else:
            await update.message.reply_text("❌ Ошибка формата.", reply_markup=get_back_menu())

    elif state == 'awaiting_delete_id' and user_id == ADMIN_ID:
        try:
            del PRODUCTS[int(text)]
            await update.message.reply_text("✅ Удалено!", reply_markup=get_back_menu())
        except: await update.message.reply_text("❌ Ошибка.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo' and user_id == ADMIN_ID:
        try:
            code, disc = text.split(" ")
            PROMOS[code.upper()] = int(disc)
            await update.message.reply_text("✅ Промокод создан!", reply_markup=get_back_menu())
        except: await update.message.reply_text("❌ Ошибка.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        success = 0
        for uid in USERS.keys():
            try:
                await context.bot.send_message(uid, f"📢 {text}")
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Отправлено: {success}", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo_code':
        code = text.upper()
        if code in PROMOS:
            user_promo[user_id] = PROMOS[code]
            await update.message.reply_text(f"✅ Скидка {PROMOS[code]}% применена!", reply_markup=get_main_menu(user_id))
        else:
            await update.message.reply_text("❌ Промокод не найден.", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = None

    elif state == 'awaiting_review':
        REVIEWS.append(text)
        await update.message.reply_text("✅ Спасибо за отзыв!", reply_markup=get_main_menu(user_id))
        context.user_data['state'] = None

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try: await query.message.delete()
    except: pass
    await asyncio.sleep(0.3)
    
    if not PRODUCTS:
        await query.message.chat.send_message("Каталог пуст.", reply_markup=get_back_menu())
        return
    for k, v in PRODUCTS.items():
        keyboard = [
            [InlineKeyboardButton("💳 Купить", callback_data=f"buy_{k}")],
            [InlineKeyboardButton("⬅️ В главное меню", callback_data="back_menu")]
        ]
        await query.message.chat.send_message(f"📦 *{v['name']}*\n\n{v['desc']}\n\n💰 Цена: *{v['price']} ⭐*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await smooth_transition(query, "👋 Главное меню:", get_main_menu(query.from_user.id))

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats, pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin_promo, pattern="^admin_promo$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(ref_system, pattern="^ref_sys$"))
    app.add_handler(CallbackQueryHandler(roll_game, pattern="^roll$"))
    app.add_handler(CallbackQueryHandler(promo_menu, pattern="^promo$"))
    app.add_handler(CallbackQueryHandler(leave_review, pattern="^leave_review$"))
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews$"))
    app.add_handler(CallbackQueryHandler(back_menu, pattern="^back_menu$"))
    
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    
    import threading
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(target=lambda: flask_app.run(host="0.0.0.0", port=port), daemon=True).start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
