"""
Run this ONCE before starting the master bot
to authenticate your Telegram account (Telethon session)
"""
import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient

API_ID       = int(os.environ.get("API_ID", "0"))
API_HASH     = os.environ.get("API_HASH", "")
SESSION_NAME = os.environ.get("SESSION_NAME", "session")

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()
    me = await client.get_me()
    print("✅ Session saved successfully.")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
