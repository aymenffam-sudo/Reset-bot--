"""
Entry point — loads .env then starts master bot
"""
from dotenv import load_dotenv
load_dotenv()
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from master_bot import main
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

asyncio.run(main())
