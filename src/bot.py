import logging
import os
import collections
import json
from google.oauth2.service_account import Credentials
import gspread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import sys

# --- Translation Setup ---
TRANSLATIONS = {}
user_language_prefs = {}  # {user_id: lang_code}
SUPPORTED_LANGUAGES = ["en", "ru", "tg"]
DEFAULT_LANG = "tg"

def load_translations():
    """Loads translation files from the locales directory."""
    for lang in SUPPORTED_LANGUAGES:
        try:
            with open(f"locales/{lang}.json", "r", encoding="utf-8") as f:
                TRANSLATIONS[lang] = json.load(f)
        except FileNotFoundError:
            logger.error(f"Translation file for language '{lang}' not found.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from translation file for language '{lang}'.")

def get_text(key, lang_code="tg", **kwargs):
    """Gets a translated text by key and language code."""
    lang = lang_code if lang_code in SUPPORTED_LANGUAGES else DEFAULT_LANG
    template = TRANSLATIONS.get(lang, {}).get(key, f"_{key}_")
    return template.format(**kwargs)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load translations at startup
load_translations()

# --- Initialization ---
ADMIN_IDS = [883017560]

try:
    logger.info("Starting bot initialization...")

    # Get BOT_TOKEN from environment
    TOKEN = os.getenv("BOT_TOKEN")
    if not TOKEN:
        logger.critical("CRITICAL: BOT_TOKEN environment variable not set.")
        sys.exit(1)

    # Spreadsheet ID
    SPREADSHEET_ID = "1TizFswnv4fNUFfz_UvlldyTmzfOB2CcEq4a8EtZC_mg"

    # Google Sheets Authorization
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_file("src/service_account.json", scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    logger.info(f"Successfully connected to Google Sheet '{sheet.spreadsheet.title}'.")

    # Build the Telegram Bot Application
    app = ApplicationBuilder().token(TOKEN).build()
    logger.info("Bot application built successfully.")

except Exception:
    logger.exception("!!! CRITICAL ERROR ON STARTUP !!!")
    sys.exit(1)

# --- Bot Handlers ---

async def language_select_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and sets the language preference."""
    query = update.callback_query
    await query.answer() # Acknowledge the button press

    # Extract the language code from the callback data, e.g., "en" from "set_lang_en"
    lang_code = query.data.split('_')[-1]

    # Store the user's preference
    if query.from_user:
        user_language_prefs[query.from_user.id] = lang_code
        logger.info(f"User {query.from_user.id} selected language: {lang_code}")

    # Edit the original message to become the welcome message in the selected language
    await query.edit_message_text(text=get_text("welcome", lang_code))


def get_lang(update: Update):
    """
    Gets user's language preference.
    Priority:
    1. In-memory preference from button selection.
    2. User's Telegram client language.
    3. Default language.
    """
    if update.effective_user:
        user_id = update.effective_user.id
        # 1. Check for a stored preference
        if user_id in user_language_prefs:
            return user_language_prefs[user_id]
        
        # 2. Fallback to user's client language
        if update.effective_user.language_code in SUPPORTED_LANGUAGES:
            return update.effective_user.language_code
            
    # 3. Fallback to default language
    return DEFAULT_LANG

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message with language selection buttons."""
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data='set_lang_en')],
        [InlineKeyboardButton("Русский 🇷🇺", callback_data='set_lang_ru')],
        [InlineKeyboardButton("Тоҷикӣ 🇹🇯", callback_data='set_lang_tg')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Please select your language / Забони худро интихоб кунед / Пожалуйста, выберите язык:", reply_markup=reply_markup)

async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all products from the Google Sheet, grouped by category."""
    lang = get_lang(update)
    try:
        rows = sheet.get_all_values()[1:]  # Skip header
        if not rows:
            await update.message.reply_text(get_text("list_empty", lang))
            return

        # Group products by category
        categories = collections.defaultdict(list)
        for row in rows:
            if len(row) >= 4:
                name, price, qty, category = row[:4]
                # Use a default category if it's empty
                category_name = category.strip() if category.strip() else get_text("uncategorized", lang)
                product_line = f"🔹 {name} — {price} сом, монда: {qty}"
                categories[category_name].append(product_line)

        if not categories:
            await update.message.reply_text(get_text("list_empty", lang)) # Re-using list_empty here
            return

        # Build the final message
        text = get_text("list_header", lang) + "\n"
        # Sort categories alphabetically for consistent order
        for category, products in sorted(categories.items()):
            text += f"\n📁 **{category.upper()}**\n"
            text += "\n".join(products)
        
        await update.message.reply_text(text, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error in list_products: {e}")
        await update.message.reply_text(get_text("list_error", lang, error=e))

async def add_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adds a new product with a category to the Google Sheet."""
    # --- Authorization Check ---
    if not update.effective_user or update.effective_user.id not in ADMIN_IDS:
        logger.warning(f"Unauthorized attempt to add product by user {update.effective_user.id if update.effective_user else 'Unknown'}")
        return  # Silently ignore non-admins

    lang = get_lang(update)
    try:
        if not update.message.text or ',' not in update.message.text:
            return

        # Unpack four values now
        name, price, qty, category = [x.strip() for x in update.message.text.split(',', 3)]
        user = update.message.from_user
        # Append all four values, plus the user's name
        sheet.append_row([name, price, qty, category, user.full_name if user else 'Unknown'])
        await update.message.reply_text(get_text("add_success", lang))
    except ValueError:
        await update.message.reply_text(get_text("add_error_format", lang))
    except Exception as e:
        logger.error(f"Error in add_product: {e}")
        await update.message.reply_text(get_text("add_error_generic", lang, error=e))


# --- Register Handlers and Start Bot ---
if __name__ == "__main__":
    # Register handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(language_select_callback))
    app.add_handler(CommandHandler("list", list_products))
    # This handler processes any text message that is not a command
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, add_product))

    logger.info("Starting bot polling...")
    app.run_polling()
