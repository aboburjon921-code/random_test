"""Bot (polling) + FastAPI web-serverni bitta jarayonda yuritadi."""
import os, asyncio, logging
import uvicorn
from telegram import Update
import db, bot, webapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("main")


async def expirer():
    while True:
        await asyncio.sleep(20)
        try:
            db.expire_due()
        except Exception:
            pass


async def main():
    if not bot.TOKEN:
        raise SystemExit("BOT_TOKEN kiritilmagan!")
    db.init()
    application = bot.build_app()

    port = int(os.environ.get("PORT", "8080"))
    config = uvicorn.Config(webapp.app, host="0.0.0.0", port=port, log_level="warning")
    server = uvicorn.Server(config)

    await application.initialize()
    await application.start()
    try:
        me = await application.bot.get_me()
        os.environ["BOT_USERNAME"] = me.username or ""
        log.info("Bot: @%s", me.username)
    except Exception:
        pass
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES,
                                            drop_pending_updates=True)
    asyncio.create_task(expirer())
    log.info("Bot va web-server ishga tushdi. BASE_URL=%s", bot.BASE_URL or "(sozlanmagan)")
    try:
        await server.serve()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
