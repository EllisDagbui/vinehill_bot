import os
from pyrogram import Client, filters

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

@app.on_message(filters.document | filters.video | filters.audio)
def rename_and_forward(client, message):
    # Extract file info
    file_name = message.document.file_name if message.document else message.video.file_name if message.video else message.audio.file_name
    new_name = f"VINEHILL_{file_name}"  # Example renaming rule

    # Download and re-upload with new name
    file_path = message.download()
    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    os.rename(file_path, new_file_path)

    # Forward the renamed file
    message.reply_document(new_file_path, caption="File processed by VINEHILL_BOT")

app.run()
