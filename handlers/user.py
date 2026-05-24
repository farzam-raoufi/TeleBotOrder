from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatJoinRequest, FSInputFile
from aiogram.filters import Command
from dotenv import load_dotenv
from datetime import datetime
import os

from database import get_user, create_user, set_user_status, is_banned
from keyboards.inline import get_start_keyboard, get_admin_main_menu
from keyboards.reply import get_user_main_menu, get_admin_main_menu
from utils.report_generator import generate_today_report


user_router = Router()

load_dotenv()

ADMIN_ID = [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]
GROUP_ID = int(os.getenv("GROUP_ID"))


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

# ------------------- Chat Join Request -------------------


@user_router.chat_join_request(F.chat.id == GROUP_ID)
async def handle_join_request(join_request: ChatJoinRequest, bot: Bot):
    user_id = join_request.from_user.id

    user = await get_user(user_id)

    if user and user["status"] == 1:           # فقط کاربران تأیید شده
        await bot.approve_chat_join_request(
            chat_id=join_request.chat.id,
            user_id=user_id
        )
        # پیام خوش‌آمدگویی اختیاری
        try:
            await bot.send_message(
                chat_id=user_id,
                text="✅ شما با موفقیت به گروه اضافه شدید.\n\n"
                     "حالا می‌توانید از تمام امکانات ربات استفاده کنید."
            )
        except:
            pass
    else:
        # رد درخواست اگر تأیید نشده باشد
        await bot.decline_chat_join_request(
            chat_id=join_request.chat.id,
            user_id=user_id
        )


@user_router.message(F.text == "📊 گزارش معاملات امروز")
async def send_today_report(message: Message):
    user = await get_user(message.from_user.id)

    try:
        pdf_path = await generate_today_report(
            user_id=user["id"],
            username=message.from_user.full_name
        )

        # استفاده از FSInputFile (روش درست در aiogram 3)
        document = FSInputFile(pdf_path)

        await message.answer_document(
            document=document,
            caption=f"📊 گزارش معاملات امروز شما\n",
            parse_mode="HTML"
        )

        # حذف فایل بعد از ارسال (برای جلوگیری از پر شدن حافظه)
        os.remove(pdf_path)

    except Exception as e:
        await message.answer("❌ خطا در تولید گزارش. لطفا مجددا تلاش کنید.")
        print(f"Report error: {e}")


@user_router.message(F.text == "🔙 بازگشت به منو")
async def back_to_main_menu(message: Message):

    if is_admin(message.from_user.id):
        await message.answer(
            "🔙 به منوی اصلی بازگشتید.",
            reply_markup=get_admin_main_menu()
        )
    else:
        await message.answer("🔙 به منوی اصلی بازگشتید.", reply_markup=get_user_main_menu())
