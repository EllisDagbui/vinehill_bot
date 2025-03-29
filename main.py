import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    import subprocess
    subprocess.run(["pip", "install", "python-dotenv"], check=True)
    from dotenv import load_dotenv  # Try importing again after installation

# Load environment variables from .env file (only once)
load_dotenv()

import re
import asyncio
import urllib.parse
from pyrogram import Client, filters
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

# Environment Variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
try:
    API_ID = int(os.getenv("API_ID", "0"))
except (TypeError, ValueError):
    raise ValueError("Invalid or missing API_ID in .env")
API_HASH = os.getenv("API_HASH")

# Debugging STORAGE_GROUP_ID: Clean any hidden characters
raw_storage_id = os.getenv("STORAGE_GROUP_ID", "").strip()
cleaned_id = raw_storage_id.encode("ascii", "ignore").decode()  # Remove non-ASCII characters
print(f"Cleaned STORAGE_GROUP_ID: {repr(cleaned_id)}")  # Debug output

try:
    STORAGE_GROUP_ID = int(cleaned_id)
except (TypeError, ValueError):
    raise ValueError(f"Invalid STORAGE_GROUP_ID: {repr(cleaned_id)}")

if not BOT_TOKEN or not API_ID or not API_HASH or STORAGE_GROUP_ID == 0:
    raise ValueError("Missing required environment variables.")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# -----------------------------
# Constants: Telegram Channel & Group IDs (as integers)
# -----------------------------
CHANNEL_IDS = {
    "games": int(os.getenv("CHANNEL_GAMES_ID", "0")),
    "music": int(os.getenv("CHANNEL_MUSIC_ID", "0")),
    "movies": int(os.getenv("CHANNEL_MOVIES_ID", "0")),
    "tvseries": int(os.getenv("CHANNEL_TVSERIES_ID", "0"))
}
# Remove any invalid channel IDs (0)
CHANNEL_IDS = {k: v for k, v in CHANNEL_IDS.items() if v != 0}

# -----------------------------
# In-memory Storage
# -----------------------------
# Stores available files per category: {category: {file_name: file_id}}
available_files = {category: {} for category in CHANNEL_IDS}
# Stores the message ID for the last channel update per category
channel_update_message_ids = {category: None for category in CHANNEL_IDS}

# -----------------------------
# Helper Functions
# -----------------------------
def parse_filename(file_name):
    """
    Rename files based on VINEHILL naming rules and assign a category.
    Returns (new_name, category)
    """
    file_name = file_name.replace("_", " ")

    # TV Series: look for SxxExx pattern
    tv_match = re.search(r"(S\d{2}E\d{2})", file_name, re.IGNORECASE)
    if tv_match:
        series_name = file_name.split(tv_match.group(1))[0].strip()
        quality = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        new_name = f"{series_name} {tv_match.group(1)} {quality.group(1) if quality else ''} VINEHILL".strip()
        return new_name, "tvseries"

    # Movies: look for a year in parentheses or brackets
    year_match = re.search(r"[\(\[](\d{4})[\)\]]", file_name)
    if year_match:
        movie_name = re.split(r"[\(\[]\d{4}[\)\]]", file_name)[0].strip()
        quality = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        new_name = f"{movie_name} ({year_match.group(1)}) {quality.group(1) if quality else ''} VINEHILL".strip()
        return new_name, "movies"

    # Games: if file name contains certain keywords
    if any(kw in file_name.lower() for kw in ["ps", "xbox", "pc", "game"]):
        return f"{file_name} VINEHILL", "games"

    # Default: categorize as movie
    return f"{file_name} VINEHILL".strip(), "movies"

async def build_deep_link(file_name):
    """
    Construct a deep link URL for a given file.
    The file_name is URL-encoded and appended as a parameter.
    """
    encoded = urllib.parse.quote(file_name)
    bot_username = (await app.get_me()).username
    return f"https://t.me/{bot_username}?start=file={encoded}"

async def update_channel(category):
    """
    Updates the specified channel's message with a list of available files.
    Handles flood wait errors and retries.
    """
    channel_id = CHANNEL_IDS[category]
    files = available_files.get(category, {})

    if not files:
        text = f"No {category.capitalize()} files available yet."
    else:
        # Build a markdown list with deep links for each file
        links = [f"[{fname}]({await build_deep_link(fname)})" for fname in sorted(files.keys())]
        text = f"Available {category.capitalize()} Files:\n" + "\n".join(links)

    try:
        if channel_update_message_ids[category]:
            await app.edit_message_text(
                chat_id=channel_id,
                message_id=channel_update_message_ids[category],
                text=text,
                parse_mode="MarkdownV2"
            )
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
    """Updates all category channels sequentially with a small delay to avoid rate limits."""
    for category in CHANNEL_IDS:
        await update_channel(category)
        await asyncio.sleep(2)

# -----------------------------
# Command Handlers
# -----------------------------
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # Deep-link file request: /start file=<file_name>
    if len(message.command) > 1 and message.command[1].startswith("file="):
        file_req = urllib.parse.unquote(message.command[1].split("=", 1)[1])
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
    """
    Processes files sent to VINEHILL_STORAGE:
      - Retrieves the original file name.
      - Parses the file name to rename and categorize it.
      - Stores the file ID in in-memory storage.
      - Updates the corresponding channel with the new file list.
    """
    orig_name = (message.document.file_name if message.document else
                 message.video.file_name if message.video else
                 message.audio.file_name if message.audio else "unknown_file")

    new_name, category = parse_filename(orig_name)
    file_id = (message.document.file_id if message.document else
               message.video.file_id if message.video else
               message.audio.file_id if message.audio else None)
    
    if file_id:
        available_files[category][new_name] = file_id
        print(f"Processed {new_name} ({category}).")
        await update_channel(category)

# -----------------------------
# Start Bot
# -----------------------------
print("Starting VINEHILL_BOT...")
app.run()
