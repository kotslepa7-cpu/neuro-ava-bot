import asyncio
import sqlite3
import urllib.parse
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton

# Вставь сюда токен своего бота от @BotFather
BOT_TOKEN = "9050576973:AAFNdWmA5GKYl2YV1tgZJl9NSTT2HmTHlow"

# Настройки монетизации
FREE_GENERATIONS = 3      # Бесплатно при старте
STARS_PRICE = 25          # Цена в звездах (XTR)
PACK_GENERATIONS = 15     # Сколько генераций даем за покупку

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- Работа с базой данных (SQLite) ---
conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER
    )
""")
conn.commit()

def get_balance(user_id: int) -> int:
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, FREE_GENERATIONS))
        conn.commit()
        return FREE_GENERATIONS
    return row[0]

def update_balance(user_id: int, amount: int):
    current = get_balance(user_id)
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (current + amount, user_id))
    conn.commit()

# --- Клавиатура покупки ---
def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"⭐ Купить {PACK_GENERATIONS} генераций за {STARS_PRICE} Звезд",
            callback_data="buy_pack"
        )]
    ])

# --- Команды и сообщения ---
@dp.message(CommandStart())
async def start_command(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        f"Привет! Я **NeuroAva** — бот для генерации картинок и аватарок.\n\n"
        f"🎁 Твой баланс: **{balance} генераций**.\n"
        f"Просто напиши мне, что нарисовать (например: *киберпанк кот в очках, неоновый свет*).",
        parse_mode="Markdown",
        reply_markup=buy_keyboard()
    )

@dp.callback_query(F.data == "buy_pack")
async def send_stars_invoice(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer_invoice(
        title=f"Пакет на {PACK_GENERATIONS} аватарок",
        description=f"Пополнение баланса в боте NeuroAva на {PACK_GENERATIONS} генераций.",
        payload="pack_15",
        currency="XTR",  # Валюта Telegram Stars
        prices=[LabeledPrice(label=f"{PACK_GENERATIONS} генераций", amount=STARS_PRICE)]
    )

# Обязательное подтверждение перед оплатой
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

# Начисление генераций после успешной оплаты
@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user_id = message.from_user.id
    update_balance(user_id, PACK_GENERATIONS)
    new_balance = get_balance(user_id)
    await message.answer(
        f"✅ Оплата прошла успешно!\n"
        f"Начислено **{PACK_GENERATIONS} генераций**.\n"
        f"Твой текущий баланс: **{new_balance}**.",
        parse_mode="Markdown"
    )

# Генерация картинки
@dp.message()
async def generate_image(message: types.Message):
    prompt = message.text
    if not prompt:
        await message.answer("Отправь текстовое описание картинки.")
        return

    user_id = message.from_user.id
    balance = get_balance(user_id)

    if balance <= 0:
        await message.answer(
            "😔 У тебя закончились бесплатные генерации.\n"
            "Пополни баланс, чтобы продолжить создавать аватарки!",
            reply_markup=buy_keyboard()
        )
        return

    wait_msg = await message.answer("🎨 Рисую твою аватарку, подожди пару секунд...")

    encoded_prompt = urllib.parse.quote(prompt)
    image_url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&nologo=true"

    try:
        await message.answer_photo(
            photo=image_url,
            caption=f"✨ Готово! Запрос: *{prompt}*\nОсталось генераций: **{balance - 1}**",
            parse_mode="Markdown"
        )
        update_balance(user_id, -1)
        await wait_msg.delete()
    except Exception:
        await wait_msg.edit_text("Ошибка при генерации. Попытка не списана, попробуй другой запрос.")

async def main():
    print("Бот NeuroAva со звездами запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
