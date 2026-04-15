import asyncio
import logging
import json
import os
import sys
import subprocess

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ── الإعدادات ───────────────────────────
MASTER_TOKEN    = os.environ.get("MASTER_TOKEN", "")
MASTER_OWNER_ID = int(os.environ.get("MASTER_OWNER_ID", "0"))
API_ID          = os.environ.get("API_ID", "")
API_HASH        = os.environ.get("API_HASH", "")
RESET_BOT_USERNAME = os.environ.get("RESET_BOT_USERNAME", "")
SESSION_NAME    = os.environ.get("SESSION_NAME", "session")
RESPONSE_TIMEOUT = os.environ.get("RESPONSE_TIMEOUT", "30")
BOTS_FILE       = "bots_data.json"
TEMPLATE_PATH   = os.path.join(os.path.dirname(__file__), "bot_template.py")

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(ASK_TOKEN, ASK_OWNER_COUNT, ASK_OWNER_IDS, ASK_CREDITS) = range(4)
running_bots: dict[str, subprocess.Popen] = {}

# ── إدارة البيانات ──
def load_bots() -> dict:
    if os.path.exists(BOTS_FILE):
        with open(BOTS_FILE, "r") as f:
            try: return json.load(f)
            except: return {"bots": []}
    return {"bots": []}

def save_bots(data: dict):
    with open(BOTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_all_bots() -> list:
    return load_bots().get("bots", [])

def add_bot(token: str, owner_ids: list[int], credits: str):
    data = load_bots()
    data["bots"] = [b for b in data["bots"] if b["token"] != token]
    data["bots"].append({
        "token": token, "owner_ids": owner_ids, "credits": credits,
        "sessions_file": f"sessions_{token[:10]}.json",
    })
    save_bots(data)

def remove_bot_data(token: str):
    data = load_bots()
    data["bots"] = [b for b in data["bots"] if b["token"] != token]
    save_bots(data)

# ── تشغيل العمليات ──
def launch_bot(bot: dict) -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        "BOT_TOKEN": bot["token"], "API_ID": str(API_ID), "API_HASH": API_HASH,
        "RESET_BOT_USERNAME": RESET_BOT_USERNAME, "SESSION_NAME": SESSION_NAME,
        "RESPONSE_TIMEOUT": str(RESPONSE_TIMEOUT), "CREDITS": bot["credits"],
        "OWNER_IDS": ",".join(str(i) for i in bot["owner_ids"]),
        "SESSIONS_FILE": bot.get("sessions_file", f"sessions_{bot['token'][:10]}.json"),
    })
    return subprocess.Popen([sys.executable, TEMPLATE_PATH], env=env)

def stop_bot(token: str):
    proc = running_bots.pop(token, None)
    if proc: proc.terminate()

# ── الواجهات ──
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add New Bot", callback_data="add_bot")],
        [InlineKeyboardButton("📋 List Bots", callback_data="list_bots")],
        [InlineKeyboardButton("🗑️ Remove Bot", callback_data="remove_bot")],
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MASTER_OWNER_ID: return
    bots = get_all_bots()
    await update.message.reply_text(
        f"🏭 *Master Bot Factory*\nActive Bots: {len(bots)}",
        parse_mode="Markdown", reply_markup=main_menu_keyboard()
    )

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "list_bots":
        bots = get_all_bots()
        text = "📋 *Bots:*\n" + "\n".join([f"• `{b['token'][:10]}...`" for b in bots]) if bots else "No bots."
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    elif query.data == "remove_bot":
        bots = get_all_bots()
        if not bots: return
        buttons = [[InlineKeyboardButton(f"🗑️ {b['token'][:15]}", callback_data=f"del_{b['token']}")] for b in bots]
        await query.message.edit_text("Select bot to remove:", reply_markup=InlineKeyboardMarkup(buttons))
    elif query.data.startswith("del_"):
        token = query.data.replace("del_", "")
        stop_bot(token)
        remove_bot_data(token)
        await query.message.edit_text("✅ Bot Removed.", reply_markup=main_menu_keyboard())

# ── نظام إضافة بوت جديد ──
async def add_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.message.reply_text("🤖 Send Bot Token (or /cancel):")
    return ASK_TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_token"] = update.message.text.strip()
    await update.message.reply_text("👥 Owner ID:")
    return ASK_OWNER_IDS

async def receive_owner_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["owner_id"] = int(update.message.text.strip())
    await update.message.reply_text("©️ Credits text:")
    return ASK_CREDITS

async def receive_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = context.user_data["new_token"]
    owner_id = context.user_data["owner_id"]
    credits = update.message.text.strip()
    
    add_bot(token, [owner_id], credits)
    bot_data = next(b for b in load_bots()["bots"] if b["token"] == token)
    running_bots[token] = launch_bot(bot_data)
    
    await update.message.reply_text("🎉 Bot Launched!", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ── المشغل الرئيسي ──
async def main():
    for bot in get_all_bots():
        running_bots[bot["token"]] = launch_bot(bot)

    app = Application.builder().token(MASTER_TOKEN).build()
    
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_bot_start, pattern="^add_bot$")],
        states={
            ASK_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            ASK_OWNER_IDS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_owner_ids)],
            ASK_CREDITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_credits)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(callback_router))

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    logger.info("✅ Master Bot is ONLINE with all features!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
