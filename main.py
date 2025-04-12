from flask import Flask
import threading
import asyncio
import bot  # або import yt_stream_notifier як bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def loop_runner():
        while True:
            try:
                await bot.main()
            except Exception as e:
                print(f"Помилка у боті, перезапускаємо: {e}")
                await asyncio.sleep(10)

    loop.run_until_complete(loop_runner())

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()