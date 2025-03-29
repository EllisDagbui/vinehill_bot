import os
from pyrogram import Client, filters

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

print("Starting VINEHILL_BOT...")

# Add a /start command handler to confirm the bot is working
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text("Hello! VINEHILL_BOT is up and running.")

print("Running the bot...")
app.run()
