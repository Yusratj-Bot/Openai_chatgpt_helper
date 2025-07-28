
import logging
import os
import gspread
from aiogram import Bot, Dispatcher, executor, types
from oauth2client.service_account import ServiceAccountCredentials

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPREADSHEET_NAME = "OptoMarkaz_Tovary"

scope = ["https://spreadsheets.google.com/feeds","https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
client = gspread.authorize(creds)
sheet = client.open(SPREADSHEET_NAME).sheet1

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
logging.basicConfig(level=logging.INFO)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply(
        "👋 Добро пожаловать в OptoMarkaz B2B бот!\n"
        "Вы можете:\n"
        "🛒 Отправить товар: товар, цена, количество\n"
        "📦 Посмотреть список товаров: /list"
    )

@dp.message_handler(lambda m: ',' in m.text)
async def add_product(message: types.Message):
    try:
        name, price, qty = [x.strip() for x in message.text.split(',')]
        sheet.append_row([name, price, qty, message.from_user.full_name])
        await message.reply("✅ Товар успешно добавлен!")
    except Exception as e:
        await message.reply(f"⚠️ Ошибка при добавлении: {e}")

@dp.message_handler(commands=['list'])
async def list_products(message: types.Message):
    rows = sheet.get_all_values()[1:]
    if not rows:
        await message.reply("📭 Список товаров пуст.")
        return
    text = "📦 Список товаров:\n"
    for row in rows:
        name, price, qty = row[:3]
        text += f"🔹 {name} — {price} сом, осталось: {qty}\n"
    await message.reply(text)

if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
