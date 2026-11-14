import os
import asyncio
import aiosqlite
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, 
    ContextTypes, MessageHandler, filters
)

TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", 0))
DB_PATH = "shop.db"

# --- База данных ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS products 
                            (id INTEGER PRIMARY KEY, name TEXT, price INTEGER, desc TEXT, text TEXT, key TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promos 
                            (code TEXT PRIMARY KEY, discount INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS reviews 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)""")
        await db.commit()

# --- Меню ---
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

# --- Старт ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['state'] = None
    await update.message.reply_text("👋 Добро пожаловать в магазин!", reply_markup=get_main_menu(update.effective_user.id == ADMIN_ID))

# --- Админка ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    if query.from_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("📝 Изменить товар", callback_data="admin_edit_list")],
        [InlineKeyboardButton("🗑 Удалить товар", callback_data="admin_delete")],
        [InlineKeyboardButton("🎟 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await query.message.edit_text("⚙️ Админ-панель. Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- Добавление ---
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Введи данные товара в формате:\n`Название | Цена(число) | Описание | Код конфига | Ключ`",
        parse_mode="Markdown", reply_markup=get_back_menu()
    )
    context.user_data['state'] = 'awaiting_product'

# --- Изменение ---
async def admin_edit_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cursor:
            products = await cursor.fetchall()
    
    if not products:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
        
    text = "Введи ID товара, который хочешь изменить:\n\n"
    for p in products:
        text += f"ID: {p[0]} — {p[1]}\n"
    
    await query.message.reply_text(text, reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_edit_id'

# --- Удаление ---
async def admin_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name FROM products") as cursor:
            products = await cursor.fetchall()
    
    if not products:
        await query.message.reply_text("Каталог пуст.", reply_markup=get_back_menu())
        return
        
    text = "Введи ID товара, который хочешь удалить:\n\n"
    for p in products:
        text += f"ID: {p[0]} — {p[1]}\n"
    
    await query.message.reply_text(text, reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_delete_id'

# --- Промокоды ---
async def admin_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введи промокод и скидку в % через пробел (например: `NUAR50 50`):", reply_markup=get_back_menu())
    context.user_data['state'] = 'awaiting_promo'

# --- Обработка текста ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    
    if not state or user_id != ADMIN_ID:
        return

    if state == 'awaiting_product':
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("INSERT INTO products (name, price, desc, text, key) VALUES (?, ?, ?, ?, ?)", (parts[0], int(parts[1]), parts[2], parts[3], parts[4]))
                    await db.commit()
                await update.message.reply_text("✅ Товар добавлен!", reply_markup=get_back_menu())
                context.user_data['state'] = None
            else:
                raise ValueError("Нужно 5 частей через ' | '")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}\nПопробуй снова или нажми «Назад».", reply_markup=get_back_menu())

    elif state == 'awaiting_edit_id':
        try:
            product_id = int(text)
            async with aiosqlite.connect(DB_PATH) as db:
                async with db.execute("SELECT name FROM products WHERE id = ?", (product_id,)) as cursor:
                    row = await cursor.fetchone()
            if row:
                await update.message.reply_text(f"Введи новые данные для '{row[0]}' в формате:\n`Название | Цена(число) | Описание | Код конфига | Ключ`", parse_mode="Markdown")
                context.user_data['edit_id'] = product_id
                context.user_data['state'] = 'awaiting_edit_data'
            else:
                await update.message.reply_text("❌ Товар с таким ID не найден.", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Введи число (ID).", reply_markup=get_back_menu())

    elif state == 'awaiting_edit_data':
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("UPDATE products SET name=?, price=?, desc=?, text=?, key=? WHERE id=?", 
                                     (parts[0], int(parts[1]), parts[2], parts[3], parts[4], context.user_data['edit_id']))
                    await db.commit()
                await update.message.reply_text("✅ Товар изменен!", reply_markup=get_back_menu())
                context.user_data['state'] = None
            else:
                raise ValueError("Нужно 5 частей через ' | '")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}", reply_markup=get_back_menu())

    elif state == 'awaiting_delete_id':
        try:
            product_id = int(text)
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
                await db.commit()
            await update.message.reply_text(f"✅ Товар с ID {product_id} удален!", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Введи число (ID).", reply_markup=get_back_menu())
        context.user_data['state'] = None
        
    elif state == 'awaiting_promo':
        try:
            code, discount = text.split(" ")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO promos (code, discount) VALUES (?, ?)", (code.upper(), int(discount)))
                await db.commit()
            await update.message.reply_text("✅ Промокод создан!", reply_markup=get_back_menu())
        except:
            await update.message.reply_text("❌ Ошибка формата. Пример: `NUAR50 50`", reply_markup=get_back_menu())
        context.user_data['state'] = None

# --- Каталог (для пользователей) ---
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price, desc FROM products") as cursor:
            products = await cursor.fetchall()
            
    if not products:
        await query.message.reply_text("Каталог пуст.")
        return
        
    for p in products:
        text = f"📦 *{p[1]}*\n\n{p[3]}\n\n💰 Цена: *{p[2]} руб.*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{p[0]}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['state'] = None
    await query.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu(query.from_user.id == ADMIN_ID))

# --- Запуск ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_edit_list, pattern="^admin_edit_list$"))
    app.add_handler(CallbackQueryHandler(admin_delete, pattern="^admin_delete$"))
    app.add_handler(CallbackQueryHandler(admin_promo, pattern="^admin_promo$"))
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
