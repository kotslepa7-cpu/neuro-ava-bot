import os
import random
import asyncio
import sqlite3
import urllib.parse
import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile

BOT_TOKEN = "9050576973:AAFNdWmA5GKYl2YV1tgZJl9NSTT2HmTHlow" # Вставь свой полный токен от @BotFather, если обрезан

FREE_GENERATIONS = 3
STARS_PRICE = 25
PACK_GENERATIONS = 15

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

conn = sqlite3.connect("users.db")
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance INTEGER)")
conn.commit()

def get_balance(user_id: int) -> int:
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (user_id, balance) VALUES (?, ?)", (user_id, FREE_GENERATIONS))
        conn.commit()
        return FREE_GENERATIONS
    return int(row[0])

def update_balance(user_id: int, amount: int):
    current = get_balance(user_id)
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (current + amount, user_id))
    conn.commit()

def buy_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"⭐ Купить {PACK_GENERATIONS} генераций за {STARS_PRICE} Звезд", callback_data="buy_pack")]
    ])

@dp.message(CommandStart())
async def start_command(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        f"Привет! Я **NeuroAva** — бот для генерации картинок и аватарок.\n\n"
        f"🎁 Твой баланс: **{balance} генераций**.\n"
        f"Просто напиши мне, что нарисовать (например: *киберпанк кот в очках*).",
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
        currency="XTR",
        prices=[LabeledPrice(label=f"{PACK_GENERATIONS} генераций", amount=STARS_PRICE)]
    )

@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: types.Message):
    user_id = message.from_user.id
    update_balance(user_id, PACK_GENERATIONS)
    new_balance = get_balance(user_id)
    await message.answer(f"✅ Оплата прошла успешно! Текущий баланс: **{new_balance}**.", parse_mode="Markdown")

@dp.message()
async def generate_image(message: types.Message):
    if not message.text:
        await message.answer("Отправь текстовое описание картинки.")
        return

    user_id = message.from_user.id
    balance = get_balance(user_id)

    if balance <= 0:
        await message.answer("😔 Бесплатные генерации закончились. Пополни баланс!", reply_markup=buy_keyboard())
        return

    wait_msg = await message.answer("🎨 Рисую твою аватарку, подожди 5–10 секунд...")

    encoded_prompt = urllib.parse.quote(message.text)
    seed = random.randint(1, 999999)
    image_url = f"https://pollinations.ai{encoded_prompt}?width=1024&height=1024&seed={seed}&nologo=true"

    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(image_url, timeout=60) as resp:
                if resp.status != 200:
                    raise Exception(f"HTTP {resp.status}")
                image_bytes = await resp.read()

        photo_file = BufferedInputFile(image_bytes, filename="avatar.jpg")
        await message.answer_photo(
            photo=photo_file,
            caption=f"✨ Готово! Запрос: *{message.text}*\nОсталось генераций: **{balance - 1}**",
            parse_mode="Markdown"
        )
        update_balance(user_id, -1)
        await wait_msg.delete()
    except Exception as e:
        await wait_msg.edit_text(f"Ошибка нейросети ({e}). Попробуй еще раз через пару секунд.")

async def handle_ping(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
