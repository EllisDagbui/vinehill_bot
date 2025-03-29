import os
import re
import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

# Load environment variables (set these in Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# REQUIRED_GROUPS: Replace these with the actual Telegram group IDs your users must join.
REQUIRED_GROUPS = [-1001234567890, -1009876543210]  # Example IDs; update accordingly

# In-memory stores (for demonstration; these reset on restart)
trending_downloads = {}   # new_name: download count
user_favorites = {}       # user_id: [file_name, ...]
available_files = {}      # new_name: file_path (for deep-link sending)
# Simulated processing queue
file_processing_queue = asyncio.Queue()

def parse_filename(file_name, chat_title):
    """
    Rename files based on rules:
    - TV Series: if filename contains SxxExx, format as "<Series Name> SxxExx <Quality> VINEHILL"
    - Movies: if filename contains a year (e.g., (2010) or [2010]), format as "<Movie Name> (Year) <Quality> VINEHILL"
    - Games: if chat title indicates games, remove the channel name and append VINEHILL.
    - Default: append "VINEHILL" to the filename.
    """
    # Check for TV series pattern (e.g., S01E05)
    tv_match = re.search(r"(S\d{2}E\d{2})", file_name, re.IGNORECASE)
    if tv_match:
        parts = file_name.split(tv_match.group(1))
        series_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{series_name} {tv_match.group(1)} {quality} VINEHILL".strip()
        return new_name

    # Check for movie pattern with a year
    year_match = re.search(r"[\(\[](\d{4})[\)\]]", file_name)
    if year_match:
        parts = re.split(r"[\(\[]\d{4}[\)\]]", file_name)
        movie_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{movie_name} ({year_match.group(1)}) {quality} VINEHILL".strip()
        return new_name

    # For game files: if the chat title indicates it's from a game channel, remove that part.
    if chat_title and "GAMES" in chat_title.upper():
        new_name = file_name.replace("VINEHILL GAMES", "").strip()
        return f"{new_name} VINEHILL".strip()

    # Default behavior: append VINEHILL to the filename.
    return f"{file_name} VINEHILL".strip()

async def check_membership(user_id):
    """Check if the user is a member of all required groups."""
    for group_id in REQUIRED_GROUPS:
        try:
            member = await app.get_chat_member(group_id, user_id)
            if member.status in [enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.KICKED]:
                return False
        except Exception:
            return False
    return True

# ----------------------------
# Command Handlers
# ----------------------------

@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # Check if there's a deep link parameter
    if len(message.command) > 1 and message.command[1].startswith("file="):
        file_req = message.command[1].split("=", 1)[1]
        # Before sending the file, verify membership
        if not await check_membership(message.from_user.id):
            await message.reply_text("Please join all VINEHILL groups to access files.")
            return
        # If the file exists, send it
        if file_req in available_files:
            file_path = available_files[file_req]
            # Update trending downloads
            trending_downloads[file_req] = trending_downloads.get(file_req, 0) + 1
            await message.reply_document(file_path, caption=f"Here is your file: {file_req}")
        else:
            await message.reply_text("Requested file not found.")
    else:
        await message.reply_text("Hello! VINEHILL_BOT is up and running. Use /help to see commands.")

@app.on_message(filters.command("help"))
async def help_handler(client, message):
    help_text = (
        "Available Commands:\n"
        "/start - Start the bot or request a file via deep link\n"
        "/help - Show this help message\n"
        "/search <query> - Search for available files\n"
        "/trending - List trending files\n"
        "/favorites - List your favorite files\n"
        "/setfavorite <file_name> - Mark a file as favorite\n"
        "/request <file_name> - Request a missing file\n"
        "/preview - Show auto-generated preview\n"
    )
    await message.reply_text(help_text)

@app.on_message(filters.command("search"))
async def search_handler(client, message):
    query = " ".join(message.command[1:]).lower()
    if not available_files:
        await message.reply_text("No files available yet.")
        return
    results = [name for name in available_files if query in name.lower()]
    if results:
        response = "Search Results:\n" + "\n".join(results)
    else:
        response = "No matching files found."
    await message.reply_text(response)

@app.on_message(filters.command("trending"))
async def trending_handler(client, message):
    if not trending_downloads:
        await message.reply_text("No trending files yet.")
        return
    sorted_trending = sorted(trending_downloads.items(), key=lambda x: x[1], reverse=True)
    response = "Trending Files:\n" + "\n".join(f"{name} - {count} downloads" for name, count in sorted_trending)
    await message.reply_text(response)

@app.on_message(filters.command("favorites"))
async def favorites_handler(client, message):
    user_id = message.from_user.id
    favs = user_favorites.get(user_id, [])
    if favs:
        response = "Your Favorites:\n" + "\n".join(favs)
    else:
        response = "You have no favorites set."
    await message.reply_text(response)

@app.on_message(filters.command("setfavorite"))
async def setfavorite_handler(client, message):
    user_id = message.from_user.id
    if len(message.command) < 2:
        await message.reply_text("Usage: /setfavorite <file_name>")
        return
    file_name = " ".join(message.command[1:])
    user_favorites.setdefault(user_id, []).append(file_name)
    await message.reply_text(f"Added '{file_name}' to your favorites.")

@app.on_message(filters.command("request"))
async def request_handler(client, message):
    user_id = message.from_user.id
    if not await check_membership(user_id):
        await message.reply_text("Please join all VINEHILL groups to request files.")
        return
    if len(message.command) < 2:
        await message.reply_text("Usage: /request <file_name>")
        return
    file_name = " ".join(message.command[1:])
    # Simulate handling a custom file request
    await message.reply_text(f"Your request for '{file_name}' has been noted. We'll notify you if it becomes available.")

@app.on_message(filters.command("preview"))
async def preview_handler(client, message):
    # Simulate an auto-generated preview
    await message.reply_text("Auto-generated preview:\n[Cover Image Placeholder]\nDescription: Sample file description.")

# Inline query handler for searching files in any chat
@app.on_inline_query()
async def inline_query_handler(client, inline_query):
    query = inline_query.query.lower()
    if not available_files:
        results = [
            InlineQueryResultArticle(
                title="No files available",
                description="No files available yet.",
                input_message_content=InputTextMessageContent("No files available.")
            )
        ]
    else:
        matching_files = [name for name in available_files if query in name.lower()]
        results = []
        for file in matching_files:
            results.append(
                InlineQueryResultArticle(
                    title=file,
                    input_message_content=InputTextMessageContent(file)
                )
            )
    await inline_query.answer(results, cache_time=1)

# ----------------------------
# File Processing Handler
# ----------------------------
@app.on_message(filters.document | filters.video | filters.audio)
async def rename_and_forward(client, message):
    user_id = message.from_user.id
    # Verify membership before processing
    if not await check_membership(user_id):
        await message.reply_text("Please join all VINEHILL groups to access files.")
        return

    chat_title = message.chat.title if message.chat and message.chat.title else ""
    # Determine original file name
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name
    elif message.audio:
        file_name = message.audio.file_name
    else:
        file_name = "file"

    # Generate new file name based on our rules
    new_name = parse_filename(file_name, chat_title)

    # Start download and estimate speed
    start_time = time.time()
    file_path = await message.download()
    download_time = time.time() - start_time

    # Update trending downloads count
    trending_downloads[new_name] = trending_downloads.get(new_name, 0) + 1

    # Store the file path for deep link requests (in-memory; not persistent)
    available_files[new_name] = os.path.join(os.path.dirname(file_path), new_name)

    # Simulate queue system for processing large files
    await file_processing_queue.put(new_name)

    # Rename the file
    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    os.rename(file_path, new_file_path)

    # Reply with the renamed file and include download speed info
    await message.reply_document(new_file_path, caption=f"File processed by VINEHILL_BOT in {download_time:.2f} seconds")
    
    # Remove from processing queue (simulate)
    await file_processing_queue.get()

# ----------------------------
# Chatbot Mode: Answer general queries
# ----------------------------
# This now filters out messages starting with "/" (i.e., commands)
@app.on_message(filters.text & ~filters.regex(r"^/"))
async def chatbot_mode(client, message):
    if "trending" in message.text.lower():
        response = "Trending files: " + ", ".join(sorted(trending_downloads.keys()))
    else:
        response = "I'm VINEHILL_BOT, here to help with your files. Use /help for commands."
    await message.reply_text(response)

print("Starting VINEHILL_BOT with advanced features...")
print("Running the bot...")
app.run()
