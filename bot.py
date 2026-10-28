import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)

from database import get_user, create_user, update_balance

BOT_TOKEN = "9193460515:AAF0HVqTNcIUs3FJ0zOsgQMOBaj-Xbkq9i8"
WEBAPP_URL = "https://github.com/furkther3-ship-it/Koch-Gold-kaz.git"
SUPPORT_URL = "https://t.me/bobophone_orix"

CHANNEL_ID = "@suko82818"   
CHANNEL_URL = "https://t.me/suko82818"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.error(f"Ошибка проверки подписки: {e}")
        return True


def subscribed_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_URL)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏛 Играть в LORDS CASINO",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )],
        [InlineKeyboardButton(
            text="💬 Обратиться в поддержку",
            url=SUPPORT_URL
        )]
    ])


MAIN_TEXT = (
    "⭐ <b>Добро пожаловать в новую эру LORDS CASINO 🎰</b>\n\n"
    "🚀 Быстрые игры\n"
    "💵 Промокоды\n"
    "🎁 Ежедневные бонусы\n\n"
    "🔥 <b>+1000 ₽</b> на баланс для всех новых пользователей\n\n"
    "Играй и испытай свою удачу 👇\n\n"
    "Не открывается приложение?\n"
    "Обратитесь в поддержку."
)

SUB_TEXT = (
    "🔒 <b>Чтобы играть, подпишись на наш канал!</b>\n\n"
    "Жми «Подписаться», затем «Я подписался» — и откроется меню."
)


@dp.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name or "player"

    referrer_id = None
    if command.args and command.args.isdigit():
        ref = int(command.args)
        if ref != user_id:
            referrer_id = ref

    user = await get_user(user_id)
    if user is None:
        user = await create_user(user_id, username, referrer_id)
        if referrer_id:
            ref_user = await get_user(referrer_id)
            if ref_user:
                await update_balance(referrer_id, ref_user[2] + 500)

    if not await is_subscribed(user_id):
        await message.answer(SUB_TEXT, reply_markup=subscribed_keyboard(), parse_mode="HTML")
        return

    await message.answer(MAIN_TEXT, reply_markup=main_keyboard(), parse_mode="HTML")


@dp.callback_query(F.data == "check_sub")
async def check_sub(callback: CallbackQuery):
    user_id = callback.from_user.id

    if await is_subscribed(user_id):
        await callback.message.edit_text(
            MAIN_TEXT,
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ты ещё не подписался!", show_alert=True)


@dp.message(F.text == "/balance")
async def cmd_balance(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(SUB_TEXT, reply_markup=subscribed_keyboard(), parse_mode="HTML")
        return

    user = await get_user(message.from_user.id)
    if user:
        await message.answer(f"💰 Твой баланс: <b>{user[2]} ₽</b>", parse_mode="HTML")


async def main():
    from database import init_db
    await init_db()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())