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

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS products 
                            (id INTEGER PRIMARY KEY, name TEXT, price INTEGER, desc TEXT, text TEXT, key TEXT)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS promos 
                            (code TEXT PRIMARY KEY, discount INTEGER)""")
        await db.execute("""CREATE TABLE IF NOT EXISTS reviews 
                            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)""")
        await db.commit()

# --- ГЛАВНОЕ МЕНЮ ---
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Добро пожаловать в магазин!", reply_markup=get_main_menu(update.effective_user.id == ADMIN_ID))

# --- АДМИН-ПАНЕЛЬ ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.from_user.id != ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("➕ Добавить товар", callback_data="admin_add")],
        [InlineKeyboardButton("🎟 Создать промокод", callback_data="admin_promo")],
        [InlineKeyboardButton("⬅️ В меню", callback_data="back_menu")]
    ]
    await query.message.edit_text("⚙️ Админ-панель. Выбери действие:", reply_markup=InlineKeyboardMarkup(keyboard))

# --- ДОБАВЛЕНИЕ ТОВАРА (АДМИН) ---
async def admin_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введи данные товара в формате:\n`Название | Цена(число) | Описание | Код конфига | Ключ`", parse_mode="Markdown")
    context.user_data['state'] = 'awaiting_product'

# --- ПРОМОКОДЫ (АДМИН) ---
async def admin_promo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Введи промокод и скидку в % через пробел (например: `NUAR50 50`):")
    context.user_data['state'] = 'awaiting_promo'

# --- ВВОД ПРОМОКОДА (КЛИЕНТ) ---
async def promo_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Отправь мне промокод:")
    context.user_data['state'] = 'awaiting_promo_code'

# --- ОТЗЫВЫ ---
async def leave_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Напиши свой отзыв (текстом):")
    context.user_data['state'] = 'awaiting_review'

async def view_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT text FROM reviews LIMIT 5") as cursor:
            reviews = await cursor.fetchall()
    
    if not reviews:
        await query.message.reply_text("Пока нет отзывов.")
    else:
        text = "⭐ *Последние отзывы:*\n\n" + "\n\n".join([f"• {r[0]}" for r in reviews])
        await query.message.reply_text(text, parse_mode="Markdown")

# --- ОБРАБОТЧИК ТЕКСТА (ЛОВИТ ВСЁ) ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    text = update.message.text
    user_id = update.effective_user.id
    
    if state == 'awaiting_product' and user_id == ADMIN_ID:
        try:
            parts = text.split(" | ")
            if len(parts) == 5:
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("INSERT INTO products (name, price, desc, text, key) VALUES (?, ?, ?, ?, ?)", (parts[0], int(parts[1]), parts[2], parts[3], parts[4]))
                    await db.commit()
                await update.message.reply_text("✅ Товар добавлен!")
            else:
                await update.message.reply_text("❌ Неверный формат. Нужно 5 частей через `|`")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
        context.user_data['state'] = None
        
    elif state == 'awaiting_promo' and user_id == ADMIN_ID:
        try:
            code, discount = text.split(" ")
            async with aiosqlite.connect(DB_PATH) as db:
                await db.execute("INSERT OR REPLACE INTO promos (code, discount) VALUES (?, ?)", (code.upper(), int(discount)))
                await db.commit()
            await update.message.reply_text("✅ Промокод создан!")
        except:
            await update.message.reply_text("❌ Ошибка формата.")
        context.user_data['state'] = None
        
    elif state == 'awaiting_promo_code':
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT discount FROM promos WHERE code = ?", (text.upper(),)) as cursor:
                row = await cursor.fetchone()
                if row:
                    context.user_data['promo'] = row[0]
                    await update.message.reply_text(f"✅ Промокод применен! Твоя скидка: {row[0]}%")
                else:
                    await update.message.reply_text("❌ Промокод не найден.")
        context.user_data['state'] = None
        
    elif state == 'awaiting_review':
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO reviews (user_id, text) VALUES (?, ?)", (user_id, text))
            await db.commit()
        await update.message.reply_text("✅ Спасибо за отзыв!")
        context.user_data['state'] = None

# --- КАТАЛОГ (ИЗ БАЗЫ ДАННЫХ) ---
async def catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, price, desc FROM products") as cursor:
            products = await cursor.fetchall()
            
    if not products:
        await query.message.reply_text("Каталог пуст. Админ скоро добавит товары.")
        return
        
    for p in products:
        text = f"📦 *{p[1]}*\n\n{p[3]}\n\n💰 Цена: *{p[2]} руб.*"
        keyboard = [[InlineKeyboardButton("💳 Купить", callback_data=f"buy_{p[0]}")]]
        await query.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu(query.from_user.id == ADMIN_ID))

# --- ВЕБ-СЕРВЕР И ЗАПУСК ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health(): return "Bot is running"

async def main():
    await init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(admin_panel, pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_add, pattern="^admin_add$"))
    app.add_handler(CallbackQueryHandler(admin_promo, pattern="^admin_promo$"))
    app.add_handler(CallbackQueryHandler(promo_menu, pattern="^promo$"))
    app.add_handler(CallbackQueryHandler(leave_review, pattern="^leave_review$"))
    app.add_handler(CallbackQueryHandler(view_reviews, pattern="^view_reviews$"))
    app.add_handler(CallbackQueryHandler(catalog, pattern="^catalog$"))
    app.add_handler(CallbackQueryHandler(back_menu, pattern="^back_menu$"))
    
    # Ловим весь текст
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
