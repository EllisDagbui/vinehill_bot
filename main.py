import os
import re
from pyrogram import Client, filters

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

def parse_filename(file_name, chat_title):
    """
    Rename files based on rules:
      - TV Series: if filename contains SxxExx, format as: 
            "<Series Name> SxxExx <Quality> VINEHILL"
      - Movies: if filename contains a year in parentheses or brackets,
            format as: "<Movie Name> (Year) <Quality> VINEHILL"
      - Games: if the chat title suggests games, remove the channel name.
      - Default: append "VINEHILL" to the filename.
    """
    # Check for TV series pattern (e.g., S01E05)
    tv_match = re.search(r"(S\d{2}E\d{2})", file_name, re.IGNORECASE)
    if tv_match:
        # Assume series name is the part before the season/episode info
        parts = file_name.split(tv_match.group(1))
        series_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{series_name} {tv_match.group(1)} {quality} VINEHILL".strip()
        return new_name
    
    # Check for movie pattern with a year (e.g., (2010) or [2010])
    year_match = re.search(r"[\(\[](\d{4})[\)\]]", file_name)
    if year_match:
        # Assume movie name is the part before the year
        parts = re.split(r"[\(\[]\d{4}[\)\]]", file_name)
        movie_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{movie_name} ({year_match.group(1)}) {quality} VINEHILL".strip()
        return new_name

    # For game files, if the chat title suggests it's from a game channel, remove that name
    if chat_title and "GAMES" in chat_title.upper():
        # Remove "VINEHILL GAMES" (or similar) from the file name if present
        new_name = file_name.replace("VINEHILL GAMES", "").strip()
        return f"{new_name} VINEHILL".strip()
    
    # Default behavior: append "VINEHILL" at the end
    return f"{file_name} VINEHILL".strip()

@app.on_message(filters.document | filters.video | filters.audio)
async def rename_and_forward(client, message):
    # Get the chat title if available (useful for detecting games)
    chat_title = message.chat.title if message.chat and message.chat.title else ""
    
    # Determine the original file name
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name
    elif message.audio:
        file_name = message.audio.file_name
    else:
        file_name = "file"

    # Generate the new name based on our rules
    new_name = parse_filename(file_name, chat_title)
    
    # Download the file asynchronously
    file_path = await message.download()
    
    # Create the new file path using the new name
    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    
    # Rename the downloaded file
    os.rename(file_path, new_file_path)
    
    # Forward the renamed file with a caption
    await message.reply_document(new_file_path, caption="File processed by VINEHILL_BOT")

# Simple /start command for testing
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text("Hello! VINEHILL_BOT is up and running.")

print("Starting VINEHILL_BOT...")
print("Running the bot...")
app.run()
