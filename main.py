import requests
from bs4 import BeautifulSoup
import json
import time
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from datetime import datetime

# Configuration
URL = "https://www.registresolicitants.cat/registre/index.jsp"
DATA_FILE = "seen_content.json"
USERS_FILE = "users.json"
TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
CHECK_INTERVAL = 600  # Check every 10 minutes

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize Telegram bot
bot = Bot(token=TELEGRAM_TOKEN)

def load_users():
    """Loads the list of users from a file."""
    try:
        with open(USERS_FILE, "r") as file:
            return set(json.load(file))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_users(users):
    """Saves the list of users to a file."""
    with open(USERS_FILE, "w") as file:
        json.dump(list(users), file, indent=4)

users = load_users()

def start(update: Update, context: CallbackContext) -> None:
    """Handles the /start command and registers the user."""
    chat_id = update.message.chat_id
    users.add(chat_id)
    save_users(users)
    update.message.reply_text("You are now subscribed to updates.")

def fetch_page():
    """Fetches the webpage and returns the parsed BeautifulSoup object."""
    response = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code == 200:
        return BeautifulSoup(response.text, "html.parser")
    else:
        logging.error(f"Failed to fetch the page, status code: {response.status_code}")
        return None

def extract_new_content(soup):
    """Extracts the relevant content from the page."""
    new_entries = []
    for item in soup.find_all("div", class_="NotHome"):  # Adjust selector accordingly
        title = item.text.strip()
        link = item.find("a")["href"] if item.find("a") else ""
        new_entries.append({"title": title, "link": link})
    return new_entries

def load_seen_content():
    """Loads previously seen content from a JSON file and sorts it by date."""
    try:
        with open(DATA_FILE, "r") as file:
            content = json.load(file)
            # Sort by date (first part of the title)
            content.sort(key=lambda x: datetime.strptime(x["title"].split("\n")[0], "%d/%m/%Y"), reverse=True)
            return content
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_seen_content(content):
    """Saves seen content to a JSON file."""
    with open(DATA_FILE, "w") as file:
        json.dump(content, file, indent=4)

def notify_telegram(new_entries):
    """Sends a message via Telegram to all subscribed users with inline buttons."""
    for entry in new_entries:
        message = f"New publication found!\n\n{entry['title']}"
        keyboard = [[InlineKeyboardButton("View Publication", url=f"https://www.registresolicitants.cat/registre/{entry['link']}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        for user in users:
            bot.send_message(chat_id=user, text=message, reply_markup=reply_markup)

def check_now(update: Update, context: CallbackContext) -> None:
    """Checks the website immediately and notifies users if new content is found."""
    soup = fetch_page()
    if soup:
        seen_content = load_seen_content()
        new_entries = extract_new_content(soup)
        fresh_entries = [entry for entry in new_entries if entry not in seen_content]

        if fresh_entries:
            notify_telegram(fresh_entries)
            seen_content.extend(fresh_entries)
            save_seen_content(seen_content)
            update.message.reply_text("New content found and notified!")
        else:
            update.message.reply_text("No new content found.")

def get_last_publication(update: Update, context: CallbackContext) -> None:
    """Retrieves the last saved publication(s) and sends them with inline buttons."""
    seen_content = load_seen_content()
    if seen_content:
        # Get the most recent publication(s)
        latest_date = datetime.strptime(seen_content[0]["title"].split("\n")[0], "%d/%m/%Y")
        latest_entries = [entry for entry in seen_content if datetime.strptime(entry["title"].split("\n")[0], "%d/%m/%Y") == latest_date]

        for entry in latest_entries:
            message = f"🔊 Last publication:\n\n{entry['title']}"
            keyboard = [[InlineKeyboardButton("View Publication", url=f"https://www.registresolicitants.cat/registre/{entry['link']}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(message, reply_markup=reply_markup)
    else:
        update.message.reply_text("No publications found.")

def help_command(update: Update, context: CallbackContext) -> None:
    """Provides a list of available commands."""
    commands = (
        "/start - Subscribes you to notifications\n"
        "/check - Checks for new content immediately\n"
        "/last - Retrieves the last saved publication\n"
        "/help - Displays available commands"
    )
    update.message.reply_text(commands)

def unknown_command(update: Update, context: CallbackContext) -> None:
    """Handles unknown commands."""
    update.message.reply_text("No te entiendo, envíame alguno de estos mensajes.")
    help_command(update, context)

def main():
    logging.info("Starting website monitoring...")
    seen_content = load_seen_content()

    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("check", check_now))
    dispatcher.add_handler(CommandHandler("last", get_last_publication))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))
    updater.start_polling()

    while True:
        soup = fetch_page()
        if soup:
            new_entries = extract_new_content(soup)
            fresh_entries = [entry for entry in new_entries if entry not in seen_content]
            
            if fresh_entries:
                logging.info(f"Found {len(fresh_entries)} new entries.")
                notify_telegram(fresh_entries)
                seen_content.extend(fresh_entries)
                save_seen_content(seen_content)
            else:
                logging.info("No new content found.")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()