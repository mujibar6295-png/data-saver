import logging
import sqlite3
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Token and Admin ID provided by user
TOKEN = "8874940658:AAFV6FcKwFJWGVzNC6qq213dNoiHA-p_xK0"
ADMIN_ID = 5624448603

# SQLite Database Setup
def init_db():
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", 
                       (user_id, username, full_name))
        conn.commit()
    except Exception as e:
        logger.error(f"Error saving user: {e}")
    finally:
        conn.close()

def get_all_users():
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    conn.close()
    return [user[0] for user in users]

def get_total_users_count():
    conn = sqlite3.connect("bot_users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# Track both old members (when they message) and new members (when they join)
async def track_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.new_chat_members:
        for member in update.message.new_chat_members:
            if not member.is_bot:
                add_user(member.id, member.username, member.full_name)
                logger.info(f"New member saved: {member.id} ({member.full_name})")
    
    elif update.effective_user and not update.effective_user.is_bot:
        user = update.effective_user
        add_user(user.id, user.username, user.full_name)

# /start command with interactive buttons for Admin
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("Hello! I am active here.")
        return

    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="btn_stats"),
         InlineKeyboardButton("📢 Broadcast", callback_data="btn_broadcast_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome Admin! Choose an action below:", 
        reply_markup=reply_markup
    )

# /stats command to check how many users are stored
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return
    
    total_users = get_total_users_count()
    text = f"📊 **Database Statistics**\n\nTotal Users Saved: `{total_users}`"
    
    keyboard = [[InlineKeyboardButton("🔄 Refresh Stats", callback_data="btn_stats")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        await update.callback_query.answer()

# /broadcast command implementation
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id != ADMIN_ID:
        return

    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text("Please use the correct format:\n`/broadcast Your message here`", parse_mode="Markdown")
        return

    users = get_all_users()
    if not users:
        await update.message.reply_text("No users found in the database yet!")
        return

    success_count = 0
    fail_count = 0

    status_msg = await update.message.reply_text(f"🚀 Broadcast started... Total target users: {len(users)}")

    for user_id in users:
        try:
            await context.bot.send_message(chat_id=user_id, text=message_text)
            success_count += 1
        except Exception as e:
            logger.error(f"Failed to send message to {user_id}: {e}")
            fail_count += 1

    await status_msg.edit_text(
        f"✅ **Broadcast Completed!**\n\n"
        f"Successfully Sent: `{success_count}`\n"
        f"Failed: `{fail_count}`",
        parse_mode="Markdown"
    )

# Inline button callback handler
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user

    if user.id != ADMIN_ID:
        await query.answer("You are not authorized!", show_alert=True)
        return

    if query.data == "btn_stats":
        await stats(update, context)
    elif query.data == "btn_broadcast_help":
        await query.answer()
        await query.message.reply_text(
            "To send a broadcast message, type your command in this format:\n\n`/broadcast Hello everyone!`",
            parse_mode="Markdown"
        )

def main():
    init_db()
    
    # Build application
    application = Application.builder().token(TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Track message senders and new chat members across groups/chats
    application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, track_users))

    print("Bot is up and running...")
    application.run_polling()

if __name__ == "__main__":
    main()
