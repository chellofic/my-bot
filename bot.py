import os
import asyncio
import random
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- ВРЕМЕННАЯ ПАМЯТЬ ---
PRODUCTS = {}
PROMOS = {}
REVIEWS = []
USERS = set() # Храним всех, кто нажал /start
USER_PURCHASES = {} # Сколько купил каждый
next_id = 1
user_promo = {}

def get_main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("🛒 Каталог", callback_data="catalog")],
        [InlineKeyboardButton("👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo")],
        [InlineKeyboardButton("💬 Оставить отзыв", callback_data="leave_review"), InlineKeyboardButton("⭐ Отзывы", callback_data="view_reviews")],
        [InlineKeyboardButton("🛡 Поддержка", url=f"tg://user?id={ADMIN_ID}")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="back_menu")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    user_id = update.effective_user.id
    USERS.add(user_id) # Запоминаем пользователя для рассылки
    await update.message.reply_text("👋 Добро пожаловать в магазин!", reply_markup=get_main_menu(user_id == ADMIN_ID))

# --- СЕКРЕТНАЯ КОМАНДА ---
async def roll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_promo:
        await update.message.reply_text("Ты уже использовал удачу!")
        return
    
    discount = random.choice([1, 5, 10])
    user_promo[user_id] = discount
    await update.message.reply_text(f"🎲 Тебе выпала скидка *{discount}%*! Она автоматически применится при покупке.", parse_mode="Markdown")

# --- ПРОФИЛЬ ---
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    user_id = query.from_user.id
    discount = user_promo.get(user_id, 0)
    purchases = USER_PURCHASES.get(user_id, 0)
    
    text = (
        f"👤 *Твой профиль*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"🎁 Скидка: *{discount}%*\n"
        f"🛍 Покупок: *{purchases}*"
    )
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=get_back_menu())

# --- АДМИНКА ---
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
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await query.message.delete()
    await query.message.reply_text("⚙️ Админ-панель. Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Введи данные товара в формате:\n`Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown", reply_markup=get_back_menu())
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
    await query.message.reply_text("Введи промокод и скидку в % через пробел (например: `NUAR50 50`):", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_promo'

async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    await query.message.reply_text("Отправь сообщение, которое получат ВСЕ пользователи бота:", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_broadcast'

# --- КЛИЕНТСКИЕ КНОПКИ ---
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

# --- ОБРАБОТКА ТЕКСТА ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    
    if not state: return

    if state == 'awaiting_product' and user_id == ADMIN_ID:
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                PRODUCTS[next_id] = {"name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]}
                next_id += 1
                await update.message.reply_text("✅ Товар добавлен!", reply_markup=get_back_menu())
                context.user_data['state'] = None
            else:
                raise ValueError("Нужно 5 частей через ' | '")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=get_back_menu())

    elif state == 'awaiting_delete_id' and user_id == ADMIN_ID:
        try:
            product_id = int(text)
            if product_id in PRODUCTS:
                del PRODUCTS[product_id]
                await update.message.reply_text(f"✅ Товар {product_id} удален!", reply_markup=get_back_menu())
            else:
                await update.message.reply_text("❌ Товар не найден.", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Введи число (ID).", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo' and user_id == ADMIN_ID:
        try:
            code, discount = text.split(" ")
            PROMOS[code.upper()] = int(discount)
            await update.message.reply_text(f"✅ Промокод {code.upper()} на {discount}% создан!", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Ошибка. Пример: `NUAR50 50`", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_broadcast' and user_id == ADMIN_ID:
        success = 0
        for uid in USERS:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 <b>Сообщение от админа:</b>\n\n{text}", parse_mode="HTML")
                success += 1
            except:
                pass
        await update.message.reply_text(f"✅ Рассылка завершена! Доставлено: {success} чел.", reply_markup=get_back_menu())
        context.user_data['state'] = None

    elif state == 'awaiting_promo_code':
        code = text.upper()
        if code in PROMOS:
            user_promo[user_id] = PROMOS[code]
            await update.message.reply_text(f"✅ Промокод применен! Скидка {PROMOS[code]}%", reply_markup=get_main_menu(user_id == ADMIN_ID))
        else:
            await update.message.reply_text("❌ Промокод не найден.", reply_markup=get_main_menu(user_id == ADMIN_ID))
        context.user_data['state'] = None

    elif state == 'awaiting_review':
        REVIEWS.append(text)
        await update.message.reply_text("✅ Спасибо за отзыв!", reply_markup=get_main_menu(user_id == ADMIN_ID))
        context.user_data['state'] = None

# --- КАТАЛОГ ---
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    if not PRODUCTS:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
    for k, v in PRODUCTS.items():
        text = f"📦 *{v['name']}*\n\n{v['desc']}\n\n💰 Цена: *{v['price']} руб.*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{k}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.delete()
    await query.message.reply_text("👋 Главное меню:", reply_markup=get_main_menu(query.from_user.id == ADMIN_ID))

# --- ЗАПУСК ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("roll", roll)) # Пасхалка
    app.add_handler(CallbackQueryHandler(profile, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin_promo, pattern="^admin_promo$"))
    app.add_handler(CallbackQueryHandler(admin_broadcast, pattern="^admin_broadcast$"))
    app.add_handler(CallbackQueryHandler(promo_menu, pattern="^promo$"))
    app.add_handler(CallbackQueryHandler(leave_review, pattern="^leave_review$"))
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(back_menu, pattern="^back_menu$"))
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
