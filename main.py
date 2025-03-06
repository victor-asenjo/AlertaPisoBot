import requests
from bs4 import BeautifulSoup
import json
import time
import logging
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext

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
    for item in soup.find_all("div", class_="some_class"):  # Adjust selector accordingly
        title = item.text.strip()
        link = item.find("a")["href"] if item.find("a") else ""
        new_entries.append({"title": title, "link": link})
    return new_entries

def load_seen_content():
    """Loads previously seen content from a JSON file."""
    try:
        with open(DATA_FILE, "r") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def save_seen_content(content):
    """Saves seen content to a JSON file."""
    with open(DATA_FILE, "w") as file:
        json.dump(content, file, indent=4)

def notify_telegram(new_entries):
    """Sends a message via Telegram to all subscribed users."""
    for entry in new_entries:
        message = f"New publication found!\n\n{entry['title']}\n{entry['link']}"
        for user in users:
            bot.send_message(chat_id=user, text=message)

def main():
    logging.info("Starting website monitoring...")
    seen_content = load_seen_content()

    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
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
