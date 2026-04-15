"""
Master Bot — Bot Factory (Fixed for Python 3.13 & Railway)
مدير مصنع البوتات - نسخة محسنة ومتوافقة مع رايلواي
"""

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

# ── Master Config ───────────────────────────
MASTER_TOKEN    = os.environ.get("MASTER_TOKEN", "")
MASTER_OWNER_ID = int(os.environ.get("MASTER_OWNER_ID", "0"))
API_ID          = os.environ.get("API_ID", "")
API_HASH        = os.environ.get("API_HASH", "")
RESET_BOT_USERNAME = os.environ.get("RESET_BOT_USERNAME", "")
SESSION_NAME    = os.environ.get("SESSION_NAME", "session")
RESPONSE_TIMEOUT = os.environ.get("RESPONSE_TIMEOUT", "30")
BOTS_FILE       = "bots_data.json"
TEMPLATE_PATH   = os.path.join(os.path.dirname(__file__), "bot_template.py")
# ───────────────────────────────────────────

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(ASK_TOKEN, ASK_OWNER_COUNT, ASK_OWNER_IDS, ASK_CREDITS) = range(4)
running_bots: dict[str, subprocess.Popen] = {}

# --- إدارة البيانات ---
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

# --- تشغيل البوتات ---
def launch_bot(bot: dict) -> subprocess.Popen:
    env = os.environ.copy()
    env.update({
        "BOT_TOKEN":           bot["token"],
        "API_ID":              str(API_ID),
        "API_HASH":            API_HASH,
        "RESET_BOT_USERNAME":  RESET_BOT_USERNAME,
        "SESSION_NAME":        SESSION_NAME,
        "RESPONSE_TIMEOUT":    str(RESPONSE_TIMEOUT),
        "CREDITS":             bot["credits"],
        "OWNER_IDS":           ",".join(str(i) for i in bot["owner_ids"]),
        "SESSIONS_FILE":       bot.get("sessions_file", f"sessions_{bot['token'][:10]}.json"),
    })
    proc = subprocess.Popen(
        [sys.executable, TEMPLATE_PATH],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc

# --- الأوامر والردود ---
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MASTER_OWNER_ID:
        return
    bots = get_all_bots()
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add New Bot", callback_data="add_bot")],
        [InlineKeyboardButton("📋 List Bots", callback_data="list_bots")],
        [InlineKeyboardButton("🗑️ Remove Bot", callback_data="remove_bot")],
    ])
    await update.message.reply_text(
        f"🏭 *Master Bot Factory*\n\nActive: *{len(bots)}*",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

async def main():
    logger.info("🏭 Starting Master Bot Setup...")
    
    # تشغيل البوتات المحفوظة مسبقاً
    for bot in get_all_bots():
        running_bots[bot["token"]] = launch_bot(bot)

    # بناء التطبيق
    app = Application.builder().token(MASTER_TOKEN).build()
    
    # إضافة المعالجات (Handlers)
    app.add_handler(CommandHandler("start", cmd_start))
    # ملاحظة: يمكنك إضافة باقي الـ Handlers هنا بنفس الطريقة

    # --- الإصلاح الجوهري لـ Railway و Python 3.13 ---
    await app.initialize()
    await app.start()
    
    # تشغيل البولينج بطريقة لا تسبب Crash
    await app.updater.start_polling(drop_pending_updates=True)
    
    logger.info("✅ Master Bot is ONLINE!")
    
    # الحفاظ على التشغيل
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Stopping...")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal Error: {e}")
