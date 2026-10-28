import asyncio
import logging
import os

import uvicorn

from bot import bot, dp
from database import init_db
from server import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

PORT = int(os.environ.get("SERVER_PORT") or os.environ.get("PORT") or 8000)


async def run_api():
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
        loop="asyncio",
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_bot():
    await dp.start_polling(bot)


async def main():
    await init_db()
    logging.info(f"Starting API on port {PORT}")
    logging.info("Starting Telegram bot polling")
    await asyncio.gather(
        run_api(),
        run_bot(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutdown requested")