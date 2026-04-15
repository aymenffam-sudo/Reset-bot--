"""
Master Bot — Bot Factory
Creates and manages child bots
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

# ── Master Config (edit these) ───────────────────────────
MASTER_TOKEN    = os.environ.get("MASTER_TOKEN", "")
MASTER_OWNER_ID = int(os.environ.get("MASTER_OWNER_ID", "0"))
API_ID          = os.environ.get("API_ID", "")
API_HASH        = os.environ.get("API_HASH", "")
RESET_BOT_USERNAME = os.environ.get("RESET_BOT_USERNAME", "")
SESSION_NAME    = os.environ.get("SESSION_NAME", "session")
RESPONSE_TIMEOUT = os.environ.get("RESPONSE_TIMEOUT", "30")
BOTS_FILE       = "bots_data.json"
TEMPLATE_PATH   = os.path.join(os.path.dirname(__file__), "bot_template.py")
# ────────────────────────────────────────────────────────

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
(
    ASK_TOKEN,
    ASK_OWNER_COUNT,
    ASK_OWNER_IDS,
    ASK_CREDITS,
) = range(4)

# Running child processes { token: subprocess.Popen }
running_bots: dict[str, subprocess.Popen] = {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bots Data Manager
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def load_bots() -> dict:
    if os.path.exists(BOTS_FILE):
        with open(BOTS_FILE, "r") as f:
            return json.load(f)
    return {"bots": []}

def save_bots(data: dict):
    with open(BOTS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_all_bots() -> list:
    return load_bots().get("bots", [])

def add_bot(token: str, owner_ids: list[int], credits: str):
    data = load_bots()
    # Avoid duplicates
    data["bots"] = [b for b in data["bots"] if b["token"] != token]
    data["bots"].append({
        "token": token,
        "owner_ids": owner_ids,
        "credits": credits,
        "sessions_file": f"sessions_{token[:10]}.json",
    })
    save_bots(data)

def remove_bot_data(token: str):
    data = load_bots()
    data["bots"] = [b for b in data["bots"] if b["token"] != token]
    save_bots(data)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bot Launcher
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    logger.info(f"🚀 Launched bot token={bot['token'][:15]}... PID={proc.pid}")
    return proc

def stop_bot(token: str):
    proc = running_bots.pop(token, None)
    if proc:
        proc.terminate()
        logger.info(f"🛑 Stopped bot token={token[:15]}...")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Owner Guard
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def is_master_owner(user_id: int) -> bool:
    return user_id == MASTER_OWNER_ID

async def owner_only(update: Update) -> bool:
    if is_master_owner(update.effective_user.id):
        return True
    await update.message.reply_text("🚫 *Owner only.*", parse_mode="Markdown")
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main Menu
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add New Bot",     callback_data="add_bot")],
        [InlineKeyboardButton("📋 List Bots",       callback_data="list_bots")],
        [InlineKeyboardButton("🗑️ Remove Bot",      callback_data="remove_bot")],
        [InlineKeyboardButton("📢 Broadcast",       callback_data="broadcast")],
    ])

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return
    bots = get_all_bots()
    await update.message.reply_text(
        "🏭 *Master Bot*\n\n"
        f"⚡ Active Bots · *{len(bots)}*\n\n"
        "Select an action below 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Callback Router
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "list_bots":
        await show_list_bots(update, context)
    elif data == "broadcast":
        await query.message.reply_text(
            "📢 *Broadcast*\n\n"
            "Use the command:\n"
            "`/broadcast YOUR MESSAGE`",
            parse_mode="Markdown",
        )
    elif data == "remove_bot":
        await show_remove_bots(update, context)
    elif data.startswith("remove_confirm_"):
        token = data.replace("remove_confirm_", "")
        stop_bot(token)
        remove_bot_data(token)
        await query.message.edit_text(
            "🗑️ *Bot Removed*\n\nThe bot has been stopped and deleted.",
            parse_mode="Markdown",
        )
    elif data == "back_menu":
        bots = get_all_bots()
        await query.message.edit_text(
            "🏭 *Master Bot*\n\n"
            f"⚡ Active Bots · *{len(bots)}*\n\n"
            "Select an action below 👇",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard(),
        )


async def show_list_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bots = get_all_bots()
    if not bots:
        await update.callback_query.message.edit_text(
            "📋 *No Bots Registered*\n\nAdd your first bot with ➕",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_menu")
            ]]),
        )
        return
    lines = ["📋 *Registered Bots*\n"]
    for i, bot in enumerate(bots, 1):
        token_short = bot["token"][:15] + "..."
        owners = ", ".join(str(o) for o in bot["owner_ids"])
        status = "🟢 Running" if bot["token"] in running_bots else "🔴 Stopped"
        lines.append(
            f"`{i}.` {status}\n"
            f"     🔑 `{token_short}`\n"
            f"     👤 `{owners}`\n"
            f"     ©️ {bot['credits']}\n"
        )
    await update.callback_query.message.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("⬅️ Back", callback_data="back_menu")
        ]]),
    )


async def show_remove_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bots = get_all_bots()
    if not bots:
        await update.callback_query.message.edit_text(
            "📋 *No Bots to Remove*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data="back_menu")
            ]]),
        )
        return
    buttons = []
    for bot in bots:
        label = bot["token"][:20] + "..."
        buttons.append([InlineKeyboardButton(
            f"🗑️ {label}", callback_data=f"remove_confirm_{bot['token']}"
        )])
    buttons.append([InlineKeyboardButton("⬅️ Back", callback_data="back_menu")])
    await update.callback_query.message.edit_text(
        "🗑️ *Select Bot to Remove*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Add Bot Conversation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def add_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "➕ *Add New Bot*\n\n"
        "Step 1 of 3\n\n"
        "🤖 Please send the *Bot Token*:\n\n"
        "_You can get it from @BotFather_\n\n"
        "/cancel to abort",
        parse_mode="Markdown",
    )
    return ASK_TOKEN

async def receive_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = update.message.text.strip()
    if ":" not in token or len(token) < 20:
        await update.message.reply_text(
            "❌ *Invalid Token*\n\nPlease send a valid bot token.\n/cancel to abort",
            parse_mode="Markdown",
        )
        return ASK_TOKEN
    context.user_data["new_token"] = token
    await update.message.reply_text(
        "✅ *Token Received*\n\n"
        "Step 2 of 3\n\n"
        "👥 How many owners for this bot?\n\n"
        "Reply with *1* or *2*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("1️⃣ One Owner",  callback_data="owners_1"),
             InlineKeyboardButton("2️⃣ Two Owners", callback_data="owners_2")],
        ]),
    )
    return ASK_OWNER_COUNT

async def receive_owner_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.split("_")[1])
    context.user_data["owner_count"] = count
    context.user_data["owner_ids_collected"] = []
    await query.message.reply_text(
        f"✅ *{count} Owner(s) Selected*\n\n"
        "Step 2 of 3\n\n"
        f"📩 Send the Telegram ID for *Owner 1*:",
        parse_mode="Markdown",
    )
    return ASK_OWNER_IDS

async def receive_owner_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit():
        await update.message.reply_text(
            "❌ *Invalid ID*\n\nPlease send a numeric Telegram ID.",
            parse_mode="Markdown",
        )
        return ASK_OWNER_IDS

    collected: list = context.user_data.setdefault("owner_ids_collected", [])
    collected.append(int(text))
    total = context.user_data["owner_count"]

    if len(collected) < total:
        next_num = len(collected) + 1
        await update.message.reply_text(
            f"✅ Owner {len(collected)} added.\n\n"
            f"📩 Send the Telegram ID for *Owner {next_num}*:",
            parse_mode="Markdown",
        )
        return ASK_OWNER_IDS

    # All owners collected
    await update.message.reply_text(
        "✅ *Owners Saved*\n\n"
        "Step 3 of 3\n\n"
        "©️ Send the *credits* text for this bot.\n\n"
        "_(e.g. any support text)_",
        parse_mode="Markdown",
    )
    return ASK_CREDITS

async def receive_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    credits_text = update.message.text.strip()
    token     = context.user_data["new_token"]
    owner_ids = context.user_data["owner_ids_collected"]

    add_bot(token, owner_ids, credits_text)
    bots_data = load_bots()
    bot_entry = next(b for b in bots_data["bots"] if b["token"] == token)

    proc = launch_bot(bot_entry)
    running_bots[token] = proc

    owners_str = "\n".join(f"     👤 `{oid}`" for oid in owner_ids)
    await update.message.reply_text(
        "🎉 *Bot Created & Launched!*\n\n"
        f"🔑 Token · `{token[:20]}...`\n"
        f"©️ Credits · {credits_text}\n"
        f"Owners:\n{owners_str}\n\n"
        "🟢 Bot is now running.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END

async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "↩️ *Cancelled*",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /broadcast
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await owner_only(update):
        return
    if not context.args:
        await update.message.reply_text(
            "⚠️ *Usage:* `/broadcast YOUR MESSAGE`",
            parse_mode="Markdown",
        )
        return

    message = " ".join(context.args)
    bots = get_all_bots()
    sent = 0
    failed = 0

    for bot in bots:
        try:
            from telegram import Bot
            child = Bot(token=bot["token"])
            sessions = {}
            sf = bot.get("sessions_file", "")
            if os.path.exists(sf):
                with open(sf) as f:
                    sessions = json.load(f).get("sessions", {})
            for user_id in sessions.keys():
                try:
                    await child.send_message(
                        chat_id=int(user_id),
                        text=f"📢 *Broadcast*\n\n{message}",
                        parse_mode="Markdown",
                    )
                    sent += 1
                except Exception:
                    failed += 1
        except Exception as e:
            logger.error(f"Broadcast error for bot: {e}")

    await update.message.reply_text(
        f"📢 *Broadcast Complete*\n\n"
        f"✅ Sent · {sent}\n"
        f"❌ Failed · {failed}",
        parse_mode="Markdown",
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Main
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    logger.info("🏭 Starting Master Bot...")

    # Auto-launch saved bots on startup
    for bot in get_all_bots():
        proc = launch_bot(bot)
        running_bots[bot["token"]] = proc

    app = Application.builder().token(MASTER_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_bot_start, pattern="^add_bot$")],
        states={
            ASK_TOKEN:       [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_token)],
            ASK_OWNER_COUNT: [CallbackQueryHandler(receive_owner_count_callback, pattern="^owners_")],
            ASK_OWNER_IDS:   [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_owner_ids)],
            ASK_CREDITS:     [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_credits)],
        },
        fallbacks=[CommandHandler("cancel", cancel_add)],
    )

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(add_conv)
    app.add_handler(CallbackQueryHandler(callback_router))

    logger.info("✅ Master Bot is ready!")
    
    # ── التعديل المصلح لـ Python 3.13 ──
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    # الحفاظ على تشغيل السكربت دون توقف
    stop_signal = asyncio.Event()
    await stop_signal.wait()

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        for proc in running_bots.values():
            proc.terminate()
        logger.info("🛑 Master Bot stopped.")
