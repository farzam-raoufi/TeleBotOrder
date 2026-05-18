from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from dotenv import load_dotenv
import os

from database import get_user, create_user, set_user_status, is_banned
from keyboards.inline import get_start_keyboard, get_admin_main_menu
from keyboards.reply import get_user_main_menu, get_admin_main_menu

user_router = Router()

load_dotenv()

ADMIN_ID = [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID


@user_router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)

    if is_admin(message.from_user.id):
        if not user:
            await create_user(message.from_user.id, message.from_user.full_name)
            await set_user_status(message.from_user.id, 1)  # approved

        await message.answer(
            "👑 به پنل مدیریت خوش آمدید",
            reply_markup=get_admin_main_menu()
        )
        return

    if user:
        if user["status"] == 1:  # approved
            await message.answer(
                "✅ خوش آمدید!\nاز منوی پایین استفاده کنید:",
                reply_markup=get_user_main_menu()
            )
        elif user["status"] == 2:  # rejected
            await message.answer("درخواست شما توسط ادمین تأیید نشده.\nدوباره درخواست میدهید ؟.",
                                 reply_markup=get_start_keyboard())
        elif user["status"] == 0:
            await message.answer(
                "👋 خوش آمدید!\n\n"
                "درخواست شما برای استفاده از ربات ثبت شده. لطفا منتظر تایید ادمین بمانید."
            )
        elif user["status"] == 3:
            await message.answer(
                "⛔ متأسفانه حساب شما مسدود شد."
            )
    else:
        await message.answer(
            "👋 خوش آمدید!\n\n"
            "برای استفاده از ربات، ابتدا باید توسط ادمین تأیید شوید.",
            reply_markup=get_start_keyboard()
        )


@user_router.callback_query(F.data == "request_membership")
async def request_membership(callback: CallbackQuery):

    user = await get_user(callback.from_user.id)
    if user:
        if await is_banned(callback.from_user.id):
            await callback.answer("⛔ متأسفانه حساب شما مسدود شد.")
            return

        if user["status"] == 0:   # pending
            await callback.answer("درخواست شما قبلاً ثبت شده و در حال بررسی است.", show_alert=True)
        elif user["status"] == 1:
            await callback.answer("شما قبلاً تأیید شدید!", show_alert=True)
        elif user["status"] == 2:
            await set_user_status(callback.from_user.id, 0)
            await callback.answer("درخواست شما مجدد ارسال شد..", show_alert=True)
            await callback.message.edit_text(
                "✅ درخواست عضویت شما ارسال شد.\n"
                "ادمین به‌زودی بررسی خواهد کرد."
            )
        return
    user = await create_user(callback.from_user.id, callback.from_user.full_name)
    # Here we could have changed the status to 'pending', but for now we only send a notification
    await callback.answer("درخواست شما ثبت شد. منتظر تأیید ادمین باشید.", show_alert=True)

    await callback.message.edit_text(
        "✅ درخواست عضویت شما ارسال شد.\n"
        "ادمین به‌زودی بررسی خواهد کرد."
    )
