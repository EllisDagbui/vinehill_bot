import os
import re
import asyncio
import time
import urllib.parse
from pyrogram import Client, filters, enums
from pyrogram.types import InlineQueryResultArticle, InputTextMessageContent

# Load environment variables (set these in Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")

# Initialize the bot
app = Client("VINEHILL_BOT", bot_token=BOT_TOKEN, api_id=API_ID, api_hash=API_HASH)

# -----------------------------
# Constants: Using your public channel/group usernames
# -----------------------------
STORAGE_GROUP_ID = "@VINEHILL_STORAGE"     # VINEHILL_STORAGE group
CHANNEL_GAMES_ID = "@VINEHILL_GAMES"       # VINEHILL🤡 GAMES🔫
CHANNEL_MUSIC_ID = "@VINEHILL_MUSIC"       # VINEHILL🤡 MUSIC🔫
CHANNEL_MOVIES_ID = "@VINEHILL_MOVIES"       # VINEHILL🤡 MOVIES🔫
CHANNEL_TVSERIES_ID = "@VINEHILL_TVSERIES"   # VINEHILL🤡 TVSERIES🔫

# -----------------------------
# In-memory storage (resets on restart)
# -----------------------------
# For each category, store a dictionary of file_name -> file_path
available_files = {
    "games": {},
    "music": {},
    "movies": {},
    "tvseries": {}
}

# To store deep-link update message IDs for each channel
channel_update_message_ids = {
    "games": None,
    "music": None,
    "movies": None,
    "tvseries": None
}

# -----------------------------
# Helper Functions
# -----------------------------
def parse_filename(file_name, chat_title):
    """
    Rename files based on rules:
      - TV Series: if filename contains SxxExx, format as: 
            "<Series Name> SxxExx <Quality> VINEHILL"
      - Movies: if filename contains a year (e.g., (2010) or [2010]), format as: 
            "<Movie Name> (Year) <Quality> VINEHILL"
      - Games: if chat title indicates it's from a game channel (contains "GAMES"),
            remove that name from the filename.
      - Otherwise, append "VINEHILL".
    """
    # TV Series pattern check
    tv_match = re.search(r"(S\d{2}E\d{2})", file_name, re.IGNORECASE)
    if tv_match:
        parts = file_name.split(tv_match.group(1))
        series_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{series_name} {tv_match.group(1)} {quality} VINEHILL".strip()
        return new_name

    # Movie pattern: check for a year in parentheses or brackets
    year_match = re.search(r"[\(\[](\d{4})[\)\]]", file_name)
    if year_match:
        parts = re.split(r"[\(\[]\d{4}[\)\]]", file_name)
        movie_name = parts[0].strip()
        quality_match = re.search(r"(\d{3,4}p)", file_name, re.IGNORECASE)
        quality = quality_match.group(1) if quality_match else ""
        new_name = f"{movie_name} ({year_match.group(1)}) {quality} VINEHILL".strip()
        return new_name

    # For games: if the chat title suggests it's from a game channel, remove that part.
    if chat_title and "GAMES" in chat_title.upper():
        new_name = file_name.replace("VINEHILL GAMES", "").strip()
        return f"{new_name} VINEHILL".strip()

    # Default behavior:
    return f"{file_name} VINEHILL".strip()

def categorize_file(new_name):
    """
    Simple categorization based on keywords in the file name.
    Adjust these rules as needed.
    """
    lower = new_name.lower()
    if any(kw in lower for kw in ["s0", "season", "episode", "e0"]):
        return "tvseries"
    elif any(kw in lower for kw in ["movie", "1080p", "720p", "dvdrip"]):
        return "movies"
    elif any(kw in lower for kw in ["game", "apk", "xbox", "ps", "pc"]):
        return "games"
    elif any(kw in lower for kw in ["music", "mp3", "flac", "album"]):
        return "music"
    else:
        return "movies"

async def build_deep_link(file_name):
    """
    Construct a deep link URL for a given file.
    URL-encode the file name.
    """
    encoded = urllib.parse.quote(file_name)
    bot_info = await app.get_me()  # ✅ 'await' now inside an async function
    bot_username = bot_info.username
    return f"https://t.me/{bot_username}?start=file={encoded}"


async def update_channel(category, channel_id):
    """
    Update the channel message for a given category with the list of available files.
    If a message was sent before, edit it; otherwise, send a new one.
    """
    files_dict = available_files.get(category, {})
    if not files_dict:
        text = f"No {category.capitalize()} files available yet."
    else:
        lines = [f"Available {category.capitalize()} Files:"]
        for fname in sorted(files_dict.keys()):
            deep_link = await build_deep_link(fname)
            lines.append(f"[{fname}]({deep_link})")
        text = "\n".join(lines)
    
    # Check if we already have a message ID to edit
    msg_id = channel_update_message_ids.get(category)
    try:
        if msg_id:
            msg = await app.edit_message_text(chat_id=channel_id, message_id=msg_id, text=text, parse_mode="MarkdownV2")
        else:
            msg = await app.send_message(chat_id=channel_id, text=text, parse_mode="MarkdownV2")
            channel_update_message_ids[category] = msg.message_id
    except Exception as e:
    if "FLOOD_WAIT_" in str(e):
        wait_time = int(re.search(r"FLOOD_WAIT_(\d+)", str(e)).group(1))
        print(f"[VINEHILL_BOT] Waiting for {wait_time} seconds before retrying...")
        await asyncio.sleep(wait_time)  # Wait for the required time
        return await update_channel(category, channel_id)  # Retry after waiting
    else:
        print(f"Error updating channel {category}: {e}")


async def update_all_channels():
    """Update all channels with the latest file lists."""
    await update_channel("games", CHANNEL_GAMES_ID)
    await update_channel("music", CHANNEL_MUSIC_ID)
    await update_channel("movies", CHANNEL_MOVIES_ID)
    await update_channel("tvseries", CHANNEL_TVSERIES_ID)

# -----------------------------
# Command Handlers
# -----------------------------
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    # Deep-link handling for file requests
    if len(message.command) > 1 and message.command[1].startswith("file="):
        file_req = message.command[1].split("=", 1)[1]
        for category, files in available_files.items():
            if file_req in files:
                file_path = files[file_req]
                await message.reply_document(file_path, caption=f"Here is your file: {file_req}")
                return
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
        "/trending - List trending files (not implemented in this demo)\n"
        "/favorites - List your favorite files (not implemented in this demo)\n"
        "/setfavorite <file_name> - Mark a file as favorite (not implemented in this demo)\n"
        "/request <file_name> - Request a missing file (not implemented in this demo)\n"
        "/preview - Show auto-generated preview (not implemented in this demo)\n"
    )
    await message.reply_text(help_text)

@app.on_inline_query()
async def inline_query_handler(client, inline_query):
    query = inline_query.query.lower()
    results = []
    for category, files in available_files.items():
        for fname in files:
            if query in fname.lower():
                deep_link = build_deep_link(fname)
                results.append(
                    InlineQueryResultArticle(
                        title=fname,
                        input_message_content=InputTextMessageContent(deep_link)
                    )
                )
    if not results:
        results = [
            InlineQueryResultArticle(
                title="No files available",
                description="No files available yet.",
                input_message_content=InputTextMessageContent("No files available.")
            )
        ]
    await inline_query.answer(results, cache_time=1)

# -----------------------------
# File Processing in Storage Group
# -----------------------------
@app.on_message(filters.chat(STORAGE_GROUP_ID) & (filters.document | filters.video | filters.audio))
async def process_storage_files(client, message):
    """
    Process files sent to the VINEHILL_STORAGE group.
    Downloads the file, renames and categorizes it, then updates the corresponding channel.
    """
    chat_title = message.chat.title if message.chat and message.chat.title else ""
    if message.document:
        orig_name = message.document.file_name
    elif message.video:
        orig_name = message.video.file_name
    elif message.audio:
        orig_name = message.audio.file_name
    else:
        orig_name = "file"

    new_name = parse_filename(orig_name, chat_title)
    category = categorize_file(new_name)
    
    start_time = time.time()
    file_path = await message.download()
    download_time = time.time() - start_time

    new_file_path = os.path.join(os.path.dirname(file_path), new_name)
    os.rename(file_path, new_file_path)
    
    available_files[category][new_name] = new_file_path
    print(f"Processed {new_name} in category {category} in {download_time:.2f} seconds.")

    # Update the corresponding channel for this category
    channel_ids = {
        "games": CHANNEL_GAMES_ID,
        "music": CHANNEL_MUSIC_ID,
        "movies": CHANNEL_MOVIES_ID,
        "tvseries": CHANNEL_TVSERIES_ID
    }
    await update_channel(category, channel_ids[category])

# -----------------------------
# Chatbot Mode (for non-command texts)
# -----------------------------
@app.on_message(filters.text & ~filters.regex(r"^/"))
async def chatbot_mode(client, message):
    response = "I'm VINEHILL_BOT, here to help with your files. Use /help for commands."
    await message.reply_text(response)

print("Starting VINEHILL_BOT with storage monitoring and channel updates...")
app.run()
