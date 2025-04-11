from flask import Flask
import threading
import asyncio
import bot

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

# Запускаємо бота у окремому потоці
def run_bot():
    asyncio.run(bot.main())

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()
    app.run(host='0.0.0.0', port=8080)