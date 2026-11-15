import os
import asyncio
import random
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters, PreCheckoutQueryHandler
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- БАЗА ДАННЫХ В ПАМЯТИ ---
PRODUCTS = {}
PROMOS = {}
REVIEWS = []
USERS = set() 
USER_PURCHASES = {} 
next_id = 1
user_promo = {}

# --- РЕДАКТИРУЕМЫЕ НАСТРОЙКИ ---
SETTINGS = {
    "welcome_text": "👋 Добро пожаловать в магазин конфигов Nuar!",
    "support_text": "🛡 Поддержка",
    "catalog_btn": "🛒 Каталог",
    "profile_btn": "👤 Мой профиль",
}

def get_main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton(SETTINGS['catalog_btn'], callback_data="catalog")],
        [InlineKeyboardButton(SETTINGS['profile_btn'], callback_data="profile")],
        [InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo")],
        [InlineKeyboardButton("💬 Оставить отзыв", callback_data="leave_review"), InlineKeyboardButton("⭐ Отзывы", callback_data="view_reviews")],
        [InlineKeyboardButton(SETTINGS['support_text'], url=f"tg://user?id={ADMIN_ID}")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_menu")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    user_id = update.effective_user.id
    USERS.add(user_id)
    await update.message.reply_text(SETTINGS['welcome_text'], reply_markup=get_main_menu(user_id == ADMIN_ID))

async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_promo:
        await update.message.reply_text("Ты уже использовал удачу!")
        return
    discount = random.choice([1, 5, 10])
    user_promo[user_id] = discount
    await update.message.reply_text(f"🎲 Тебе выпала скидка *{discount}%*!", parse_mode="Markdown")

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    user_id = query.from_user.id
    discount = user_promo.get(user_id, 0)
    purchases = USER_PURCHASES.get(user_id, 0)
    text = f"👤 *Твой профиль*\n\n🆔 ID: `{user_id}`\n🎁 Скидка: *{discount}%*\n🛍 Покупок: *{purchases}*"
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_back_menu())

# --- ОПЛАТА ЗВЕЗДАМИ ---
async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    config_key = int(query.data.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    
    if not item:
        await query.message.reply_text("Товар не найден.")
        return

    discount = user_promo.get(query.from_user.id, 0)
    final_price = int(item['price']) - (int(item['price']) * discount // 100)
    
    await context.bot.send_invoice(
        chat_id=query.message.chat_id,
        title=item['name'],
        description=item['desc'],
        payload=f"buy_{config_key}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=item['name'], amount=final_price)],
    )

async def pre_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payload = update.message.successful_payment.invoice_payload
    config_key = int(payload.replace("buy_", ""))
    item = PRODUCTS.get(config_key)
    
    if not item:
        await update.message.reply_text("Ошибка: товар не найден.")
        return

    user_id = update.effective_user.id
    USER_PURCHASES[user_id] = USER_PURCHASES.get(user_id, 0) + 1
    license_key = item['key']
    
    await update.message.reply_text(
        f"✅ *Оплата прошла успешно!*\n\n"
        f"Товар: {item['name']}\n"
        f"Ключ покупки: `{license_key}`\n\n"
        f"Твой конфиг ниже. Зажми на него и выбери 'Копировать'.",
        parse_mode="Markdown"
    )
    await update.message.reply_text(item['text'])
    keyboard = [[InlineKeyboardButton("⬅️ В главное меню", callback_data="back_menu")]]
    await update.message.reply_text("Что-нибудь еще?", reply_markup=InlineKeyboardMarkup(keyboard))

# --- АДМИНКА (С РЕДАКТОРОМ) ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    if query.from_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="admin_delete")],
        [InlineKeyboardButton("🎟 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("📢 Сделать рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton("✏️ Редактировать тексты", callback_data="admin_edit_texts")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await query.message.delete()
    await query.message.reply_text("⚙️ Админ-панель:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_edit_texts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    keyboard = [
        [InlineKeyboardButton("Текст приветствия", callback_data="edit_welcome_text")],
        [InlineKeyboardButton("Текст поддержки", callback_data="edit_support_text")],
        [InlineKeyboardButton("Название 'Каталог'", callback_data="edit_catalog_btn")],
        [InlineKeyboardButton("Название 'Профиль'", callback_data="edit_profile_btn")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]
    ]
    await query.message.reply_text("Выбери, что хочешь изменить:", reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_setting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    setting_key = query.data.replace("edit_", "")
    context.user_data['edit_setting_key'] = setting_key
    await query.message.delete()
    await query.message.reply_text("Отправь новый текст:", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_setting_text'

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Введи данные товара в формате:\n`Название | Цена в звездах (число) | Описание | Код | Ключ`", parse_mode="Markdown", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_product'

async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    if not PRODUCTS:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
    text = "Введи ID товара для удаления:\n\n"
    for k, v in PRODUCTS.items():
        text += f"ID: {k} — {v['name']}\n"
    await query.message.reply_text(text, reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_delete_id'

async def admin_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Введи промокод и скидку (например: `NUAR50 50`):", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_promo'

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Отправь сообщение для всех:", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_broadcast'

async def promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Отправь мне промокод:", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_promo_code'

async def leave_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Напиши свой отзыв:", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_review'

async def view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    if not REVIEWS:
        await query.message.reply_text("Пока нет отзывов.", reply_markup=get_back_menu())
        return
    text = "⭐ *Последние отзывы:*\n\n" + "\n\n".join([f"• {r}" for r in REVIEWS[-5:]])
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_back_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    if not state: return

    if state == 'awaiting_setting_text' and user_id == ADMIN_ID:
        setting_key = context.user_data.get('edit_setting_key')
        SETTINGS[setting_key] = text
        await update.message.reply_text(f"✅ Текст обновлен!", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_product' and user_id == ADMIN_ID:
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                PRODUCTS[next_id] = {"name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]}
                next_id += 1
                await update.message.reply_text("✅ Товар добавлен!", reply_markup=get_back_menu())
                context.user_data['state'] = None
            else:
                raise ValueError("Нужно 5 частей")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=get_back_menu())

    elif state == 'awaiting_delete_id' and user_id == ADMIN_ID:
        try:
            product_id = int(text)
            if product_id in PRODUCTS:
                del PRODUCTS[product_id]
                await update.message.reply_text(f"✅ Товар удален!", reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ Не найден.", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Введи число.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo' and user_id == ADMIN_ID:
        try:
            code, discount = text.split(" ")
            PROMOS[code.upper()] = int(discount)
            await update.message.reply_text(f"✅ Промокод {code.upper()} создан!", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Ошибка формата.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        success = 0
        for uid in USERS:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 <b>Сообщение:</b>\n\n{text}", parse_mode="HTML")
                success += 1
            except: pass
        await update.message.reply_text(f"✅ Доставлено: {success} чел.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo_code':
        code = text.upper()
        if code in PROMOS:
            user_promo[user_id] = PROMOS[code]
            await update.message.reply_text(f"✅ Скидка {PROMOS[code]}% применена!", reply_markup=get_main_menu(user_id == ADMIN_ID))
        else:
            await update.message.reply_text("❌ Промокод не найден.", reply_markup=get_main_menu(user_id == ADMIN_ID))
        context.user_data['state'] = None

    elif state == 'awaiting_review':
        REVIEWS.append(text)
        await update.message.reply_text("✅ Спасибо за отзыв!", reply_markup=get_main_menu(user_id == ADMIN_ID))
        context.user_data['state'] = None

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    if not PRODUCTS:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
    for k, v in PRODUCTS.items():
        text = f"📦 *{v['name']}*\n\n{v['desc']}\n\n💰 Цена: *{v['price']} ⭐*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{k}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.delete()
    await query.message.reply_text("👋 Главное меню:", reply_markup=get_main_menu(query.from_user.id == ADMIN_ID))

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roll", roll))
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_edit_texts, pattern="^admin_edit_texts$"))
    app.add_handler(CallbackQueryHandler(edit_setting, pattern="^edit_"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin_promo, pattern="^admin_promo$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(promo_menu, pattern="^promo$"))
    app.add_handler(CallbackQueryHandler(leave_review, pattern="^leave_review$"))
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(buy, pattern="^buy_"))
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
