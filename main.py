import requests
from bs4 import BeautifulSoup
import json
import time
import logging
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from datetime import datetime
from dotenv import load_dotenv
import os
load_dotenv()

# Configuration
URL = "https://www.registresolicitants.cat/registre/index.jsp"
DATA_FILE = "seen_content.json"
USERS_FILE = "users.json"
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN_ENV')
CHECK_INTERVAL = 150  # Check every 10 minutes
PROXIES = None
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

def stop(update: Update, context: CallbackContext) -> None:
    """Handles the /stop command and unregisters the user."""
    chat_id = update.message.chat_id
    if chat_id in users:
        users.remove(chat_id)
        save_users(users)
        update.message.reply_text("You are now unsubscribed from updates.")
    else:
        update.message.reply_text("You are not subscribed.")

def get_status(update: Update, context: CallbackContext) -> None:
    """Shows the current status of the service."""
    message = f"🟢 Service is running and monitoring the website for new content.\n\n"
    # Check if who sends the message is subscribed
    chat_id = update.message.chat_id
    if chat_id in users:
        message += "✅ You are subscribed to notifications\n"
    else:
        message += "❌ You are not subscribed to notifications\n"
    message += f"📄 Total publications saved: {len(load_seen_content())}\n"
    message += f"🔍 Check interval: {CHECK_INTERVAL} seconds"

    # Add a keyboard with some links
    keyboard = [
        [InlineKeyboardButton("View Website", url=URL)],
        [InlineKeyboardButton("Bot Status", url="https://alertapisobot.onrender.com/")],
        [InlineKeyboardButton("Subscribe to Notifications", callback_data="start")],
        [InlineKeyboardButton("Unsubscribe from Notifications", callback_data="stop")],
        [InlineKeyboardButton("View Last Publication", callback_data="last")],
        [InlineKeyboardButton("Check for New Content", callback_data="check")],
        [InlineKeyboardButton("Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(message, reply_markup=reply_markup)

def help_command(update: Update, context: CallbackContext) -> None:
    """Provides a list of available commands."""
    commands = (
        "/start - Subscribes you to notifications\n"
        "/check - Checks for new content immediately\n"
        "/last - Retrieves the last saved publication\n"
        "/stop - Unsubscribes you from notifications\n"
        "/status - Shows the current status of the service\n"
        "/help - Displays available commands"
    )
    update.message.reply_text(commands)

def unknown_command(update: Update, context: CallbackContext) -> None:
    """Handles unknown commands."""
    update.message.reply_text("No te entiendo, envíame alguno de estos mensajes.")
    help_command(update, context)

def callback_query_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    if query.data == "start":
        start(update, context)
    elif query.data == "stop":
        stop(update, context)
    elif query.data == "last":
        get_last_publication(update, context)
    elif query.data == "check":
        check_now(update, context)
    elif query.data == "help":
        help_command(update, context)
    else:
        query.edit_message_text(text="Unknown command.")

from flask import Flask, render_template_string

# Add this at the top of your script
app = Flask(__name__)

# HTML template with inline CSS for a prettier interface
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Website Monitoring Service</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f4f4f9;
            color: #333;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .container {
            text-align: center;
            background: white;
            padding: 2rem;
            border-radius: 10px;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
            max-width: 600px;
            width: 100%;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 1rem;
            color: #2c3e50;
        }
        p {
            font-size: 1.2rem;
            color: #7f8c8d;
        }
        .status {
            font-size: 1.5rem;
            color: #27ae60;
            font-weight: bold;
            margin-top: 1rem;
        }
        .last-publication {
            margin-top: 2rem;
            text-align: left;
            background: #f9f9f9;
            padding: 1rem;
            border-radius: 5px;
            border: 1px solid #e0e0e0;
        }
        .last-publication h2 {
            font-size: 1.5rem;
            color: #2c3e50;
            margin-bottom: 0.5rem;
        }
        .last-publication p {
            font-size: 1rem;
            color: #7f8c8d;
            margin: 0;
        }
        .footer {
            margin-top: 2rem;
            font-size: 0.9rem;
            color: #95a5a6;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Website Monitoring Service</h1>
        <p>This service is actively monitoring the website for new content.</p>
        <div class="status">🟢 Running</div>

        <div class="last-publication">
            <h2>Last Publication</h2>
            {% if last_publication %}
                <p><strong>Title:</strong> {{ last_publication.title }}</p>
                <p><strong>Date:</strong> {{ last_publication.date }}</p>
                <p><strong>Link:</strong> <a href="{{ last_publication.link }}" target="_blank">View Publication</a></p>
            {% else %}
                <p>No publications found.</p>
            {% endif %}
        </div>

        <div class="footer">
            Powered by #elPagès | Made with ❤️ | Using Render and UptimeRobot
        </div>
    </div>
</body>
</html>
"""

def load_seen_content():
    """Loads previously seen content from a JSON file and sorts it by date."""
    try:
        with open("seen_content.json", "r") as file:
            content = json.load(file)
            # Sort by date (first part of the title)
            content.sort(key=lambda x: datetime.strptime(x["title"].split("\n")[0], "%d/%m/%Y"), reverse=True)
            return content
    except (FileNotFoundError, json.JSONDecodeError):
        return []

@app.route('/')
def home():
    """Renders a styled HTML page with the last publication."""
    seen_content = load_seen_content()
    last_publication = None
    if seen_content:
        latest_entry = seen_content[0]
        last_publication = {
            "title": latest_entry["title"],
            "date": latest_entry["title"].split("\n")[0],  # Extract date from title
            "link": f"https://www.registresolicitants.cat/registre/{latest_entry['link']}"
        }

    return render_template_string(HTML_TEMPLATE, last_publication=last_publication)

def run_flask():
    """Runs the Flask server on port 8080."""
    app.run(host='0.0.0.0', port=8080)

# Modify the main function to run Flask in a separate thread
from threading import Thread

def main():
    logging.info("Starting website monitoring...")
    seen_content = load_seen_content()

    # Start Flask in a separate thread
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    updater = Updater(TELEGRAM_TOKEN)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("check", check_now))
    dispatcher.add_handler(CommandHandler("last", get_last_publication))
    dispatcher.add_handler(CommandHandler("stop", stop))
    dispatcher.add_handler(CommandHandler("status", get_status))
    dispatcher.add_handler(CommandHandler("help", help_command))
    dispatcher.add_handler(MessageHandler(Filters.command, unknown_command))
    dispatcher.add_handler(CallbackQueryHandler(callback_query_handler))  # Add this line
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