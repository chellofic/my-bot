import os
import asyncio
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))

# --- ХРАНИМ ВСЁ В ПАМЯТИ (БЕЗ ЗАВИСАНИЙ) ---
PRODUCTS = {} 
PROMOS = {}
REVIEWS = []
next_id = 1

def get_main_menu(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("🛒 Каталог", callback_data="catalog")],
        [InlineKeyboardButton("🎟 Ввести промокод", callback_data="promo")],
        [InlineKeyboardButton("💬 Оставить отзыв", callback_data="leave_review")],
        [InlineKeyboardButton("⭐ Посмотреть отзывы", callback_data="view_reviews")]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def get_back_menu():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    await update.message.reply_text("👋 Добро пожаловать в магазин!", reply_markup=get_main_menu(update.effective_user.id == ADMIN_ID))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    if query.from_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="admin_delete")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await query.message.edit_text("⚙️ Админ-панель. Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введи данные товара в формате:\n`Название | Цена | Описание | Код | Ключ`", parse_mode="Markdown", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_product'

async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not PRODUCTS:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
    text = "Введи ID товара для удаления:\n\n"
    for k, v in PRODUCTS.items():
        text += f"ID: {k} — {v['name']}\n"
    await query.message.reply_text(text, reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_delete_id'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global next_id
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    
    if not state or user_id != ADMIN_ID:
        return

    if state == 'awaiting_product':
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                PRODUCTS[next_id] = {
                    "name": parts[0], "price": parts[1], "desc": parts[2], "text": parts[3], "key": parts[4]
                }
                next_id += 1
                await update.message.reply_text("✅ Товар добавлен!", reply_markup=get_back_menu())
                context.user_data['state'] = None
            else:
                raise ValueError("Нужно 5 частей через ' | '")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=get_back_menu())

    elif state == 'awaiting_delete_id':
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

async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not PRODUCTS:
        await query.message.reply_text("Каталог пуст.")
        return
    for k, v in PRODUCTS.items():
        text = f"📦 *{v['name']}*\n\n{v['desc']}\n\n💰 Цена: *{v['price']} руб.*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{k}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu(query.from_user.id == ADMIN_ID))

flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
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
