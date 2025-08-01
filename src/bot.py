import logging
import os
import gspread
from aiogram import Bot, Dispatcher, executor, types
from oauth2client.service_account import ServiceAccountCredentials

# 🔐 Токен Бота
BOT_TOKEN = "8017841130:AAFL7uWSx6rxRzy0W2151cGHUpN5ICbEkpU"

# 📊 Название таблицы
SPREADSHEET_NAME = "OptoMarkaz_Tovary"

# 🔐 Авторизация Google Sheets
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name("src/service_account.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

# 🤖 Настройка бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

# 🔹 Стартовое сообщение
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply(
        "👋 Салом ва хуш омадед ба OptoMarkaz B2B бот!\n"
        "Шумо метавонед:\n"
        "🛒 Иловаи мол: мол, нарх, миқдор (бо вергул)\n"
        "📦 Дидани рӯйхати молҳо: /list"
    )

# 🔹 Қабули маълумоти молҳо
@dp.message_handler(lambda message: ',' in message.text)
async def add_product(message: types.Message):
    try:
        name, price, qty = [x.strip() for x in message.text.split(',')]
        sheet.append_row([name, price, qty, message.from_user.full_name])
        await message.reply("✅ Мол бо муваффақият илова шуд!")
    except Exception as e:
        await message.reply(f"⚠️ Хато ҳангоми илова кардан: {e}")

# 🔹 Нишон додани рӯйхати молҳо
@dp.message_handler(commands=['list'])
async def list_products(message: types.Message):
    try:
        rows = sheet.get_all_values()[1:]  # Пропускаем заголовок
        if not rows:
            await message.reply("📭 Рӯйхати молҳо холӣ аст.")
            return
        text = "📦 Рӯйхати молҳо:\n"
        for row in rows:
            name, price, qty = row[:3]
            text += f"🔹 {name} — {price} сом, монда: {qty}\n"
        await message.reply(text)
    except Exception as e:
        await message.reply(f"⚠️ Хатои хондани рӯйхат: {e}")

# 🔁 Запуск
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
