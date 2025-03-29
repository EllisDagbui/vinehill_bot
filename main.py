import os
import re
import asyncio
import time
import urllib.parse
from pyrogram import Client, filters
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

# Load environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

if not BOT_TOKEN or not API_ID or not API_HASH:
    raise ValueError("Missing environment variables: BOT_TOKEN, API_ID, or API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# -----------------------------
# Constants: Telegram Channel & Group IDs
# -----------------------------
STORAGE_GROUP_ID = "@VINEHILL_STORAGE"
CHANNEL_GAMES_ID = "@VINEHILL_GAMES"
CHANNEL_MUSIC_ID = "@VINEHILL_MUSIC"
CHANNEL_MOVIES_ID = "@VINEHILL_MOVIES"
CHANNEL_TVSERIES_ID = "@VINEHILL_TVSERIES"

channel_ids = {
    "games": CHANNEL_GAMES_ID,
    "music": CHANNEL_MUSIC_ID,
    "movies": CHANNEL_MOVIES_ID,
    "tvseries": CHANNEL_TVSERIES_ID
}

# -----------------------------
# In-memory Storage
# -----------------------------
available_files = {category: {} for category in channel_ids}
channel_update_message_ids = {category: None for category in channel_ids}

# -----------------------------
# Helper Functions
# -----------------------------
def parse_filename(file_name, chat_title):
    """Rename files based on rules for TV Series, Movies, and Games."""
    tv_match = re.search(r"(S\d{2}E\d{2})", file_name, re.IGNORECASE)
    if tv_match:
        series_name, quality = file_name.split(tv_match.group(1))[0].strip(), ""
        if quality_match := re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE):
            quality = quality_match.group(1)
        return f"{series_name} {tv_match.group(1)} {quality} VINEHILL".strip()

    if year_match := re.search(r"[\(\[](\d{4})[\)\]]", file_name):
        movie_name, quality = re.split(r"[\(\[]\d{4}[\)\]]", file_name)[0].strip(), ""
        if quality_match := re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE):
            quality = quality_match.group(1)
        return f"{movie_name} ({year_match.group(1)}) {quality} VINEHILL".strip()

    if chat_title and "GAMES" in chat_title.upper():
        return file_name.replace("VINEHILL GAMES", "").strip() + " VINEHILL"

    return f"{file_name} VINEHILL".strip()

def categorize_file(file_name):
    """Categorizes files based on their name."""
    lower = file_name.lower()
    if any(kw in lower for kw in ["s0", "season", "episode", "e0"]):
        return "tvseries"
    if any(kw in lower for kw in ["movie", "1080p", "720p", "dvdrip"]):
        return "movies"
    if any(kw in lower for kw in ["game", "apk", "xbox", "ps", "pc"]):
        return "games"
    if any(kw in lower for kw in ["music", "mp3", "flac", "album"]):
        return "music"
    return "movies"

async def build_deep_link(file_name):
    """Construct a deep link URL for a given file."""
    encoded = urllib.parse.quote(file_name)
    bot_username = (await app.get_me()).username
    return f"https://t.me/{bot_username}?start=file={encoded}"

async def update_channel(category):
    """Updates a category's channel message with available files."""
    channel_id = channel_ids[category]
    files = available_files.get(category, {})

    text = f"No {category.capitalize()} files available yet." if not files else \
           "\n".join([f"Available {category.capitalize()} Files:"] + 
                     [f"[{fname}]({await build_deep_link(fname)})" for fname in sorted(files.keys())])

    try:
        if channel_update_message_ids[category]:
            await app.edit_message_text(chat_id=channel_id, message_id=channel_update_message_ids[category],
                                        text=text, parse_mode="MarkdownV2")
        else:
            msg = await app.send_message(chat_id=channel_id, text=text, parse_mode="MarkdownV2")
            channel_update_message_ids[category] = msg.message_id
    except Exception as e:
        if "FLOOD_WAIT_" in str(e):
            wait_time = int(re.search(r"FLOOD_WAIT_(\d+)", str(e)).group(1))
            print(f"[VINEHILL_BOT] Flood wait {wait_time}s for {category}. Retrying...")
            await asyncio.sleep(wait_time)
            return await update_channel(category)
        print(f"Error updating {category}: {e}")

async def update_all_channels():
    """Updates all category channels sequentially to avoid rate limits."""
    for category in channel_ids:
        await update_channel(category)
        await asyncio.sleep(2)

# -----------------------------
# Command Handlers
# -----------------------------
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    if len(message.command) > 1 and message.command[1].startswith("file="):
        file_req = message.command[1].split("=", 1)[1]
        for category, files in available_files.items():
            if file_req in files:
                return await message.reply_document(files[file_req], caption=f"Here is your file: {file_req}")
        return await message.reply_text("Requested file not found.")
    await message.reply_text("Hello! VINEHILL_BOT is up and running. Use /help to see commands.")

@app.on_inline_query()
async def inline_query_handler(client, inline_query):
    if not inline_query.query.strip():
        return
    results = [
        InlineQueryResultArticle(
            title=fname,
            input_message_content=InputTextMessageContent(await build_deep_link(fname))
        ) for category, files in available_files.items() for fname in files if inline_query.query.lower() in fname.lower()
    ]
    await inline_query.answer(results if results else [
        InlineQueryResultArticle(title="No files available", input_message_content=InputTextMessageContent("No files available."))
    ], cache_time=1)

@app.on_message(filters.chat(STORAGE_GROUP_ID) & (filters.document | filters.video | filters.audio))
async def process_storage_files(client, message):
    """Processes files sent to VINEHILL_STORAGE, categorizes and updates channels."""
    chat_title = message.chat.title if message.chat else ""
    orig_name = (message.document or message.video or message.audio).file_name if message.document or message.video or message.audio else "unknown_file"
    
    new_name, category = parse_filename(orig_name, chat_title), categorize_file(orig_name)
    file_path, start_time = await message.download(), time.time()
    
    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    os.rename(file_path, new_file_path)
    available_files[category][new_name] = new_file_path
    
    print(f"Processed {new_name} ({category}) in {time.time() - start_time:.2f}s.")
    await update_channel(category)

# -----------------------------
# Start Bot
# -----------------------------
print("Starting VINEHILL_BOT with storage monitoring and channel updates...")
app.run()
