from pyrogram import Client, filters
import os
from utils import rename_file, is_valid_file

# Load bot configuration
from config import API_ID, API_HASH, BOT_TOKEN, REQUIRED_GROUPS, STORAGE_GROUP_ID

bot = Client("VINEHILL_BOT", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@bot.on_message(filters.document | filters.video | filters.audio)
def monitor_files(client, message):
    if message.chat.id == STORAGE_GROUP_ID:
        file_name = None
        file_id = None

        if message.document:
            file_name = message.document.file_name
            file_id = message.document.file_id
        elif message.video:
            file_name = message.video.file_name
            file_id = message.video.file_id
        elif message.audio:
            file_name = message.audio.file_name
            file_id = message.audio.file_id

        if file_name and is_valid_file(file_name):
            new_name = rename_file(file_name)
            
            # Save file info
            with open("files_db.txt", "a") as db:
                db.write(f"{file_id}|{new_name}\n")

            message.reply_text(f"File saved as: {new_name}")

@bot.on_message(filters.command("getfile"))
def send_file(client, message):
    user_id = message.from_user.id
    joined_all = all(client.get_chat_member(group, user_id).status in ["member", "administrator"] for group in REQUIRED_GROUPS)
    
    if not joined_all:
        message.reply_text("You must join all VINEHILL groups to access files.")
        return
    
    query = " ".join(message.command[1:])
    with open("files_db.txt", "r") as db:
        for line in db:
            file_id, name = line.strip().split("|")
            if query.lower() in name.lower():
                client.send_document(message.chat.id, file_id, caption=name)
                return
    
    message.reply_text("File not found.")

bot.run()
