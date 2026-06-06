import os
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, ChatJoinRequest, FSInputFile
from datetime import datetime
from dotenv import load_dotenv

from database import get_user, create_user, set_user_status, is_banned
from keyboards.inline import get_start_keyboard, get_emergency_confirmation_keyboard
from keyboards.reply import get_user_main_menu, get_admin_main_menu
from utils.report_generator import generate_today_report

user_router = Router()

load_dotenv()

ADMIN_ID = [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))


class Registration(StatesGroup):
    waiting_for_fullname = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID


# @user_router.message(Command("getgroupid"))
# async def get_CHANNEL_ID(message: Message):
#     chat_id = message.chat.id
#     chat_type = message.chat.type

#     await message.answer(
#         f"📌 <b>Group ID:</b> <code>{chat_id}</code>\n"
#         f"👥 <b>Chat Type:</b> {chat_type}",
#         parse_mode="HTML"
#     )


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
async def request_membership(callback: CallbackQuery, state: FSMContext):
    user = await get_user(callback.from_user.id)

    if user:
        if await is_banned(callback.from_user.id):
            await callback.answer("⛔ متأسفانه حساب شما مسدود شد.")
            return

        if user["status"] == 0:  # pending
            await callback.answer("درخواست شما قبلاً ثبت شده و در حال بررسی است.", show_alert=True)
        elif user["status"] == 1:
            await callback.answer("شما قبلاً تأیید شدید!", show_alert=True)
        elif user["status"] == 2:
            await set_user_status(callback.from_user.id, 0)
            await callback.answer("درخواست شما مجدد ارسال شد.", show_alert=True)
            await callback.message.edit_text("✅ درخواست عضویت شما ارسال شد.\nادمین به‌زودی بررسی خواهد کرد.")
        return

    await callback.message.edit_text(
        "👤 لطفاً **نام و نام خانوادگی** خود را وارد کنید:",
        parse_mode="HTML"
    )
    await state.set_state(Registration.waiting_for_fullname)
    await callback.answer()


@user_router.message(Registration.waiting_for_fullname)
async def process_fullname(message: Message, state: FSMContext):
    full_name = message.text.strip()

    # ایجاد کاربر با نام دلخواه کاربر
    user = await create_user(message.from_user.id, full_name)

    await message.answer(
        "✅ درخواست عضویت شما ثبت شد.\n"
        "ادمین به‌زودی بررسی خواهد کرد.",
        reply_markup=None
    )
    await state.clear()


# ------------------- Chat Join Request -------------------


@user_router.chat_join_request(F.chat.id == CHANNEL_ID)
async def handle_channel_join_request(join_request: ChatJoinRequest, bot: Bot):
    user_id = join_request.from_user.id

    # Check if user is registered and approved in your database
    user = await get_user(user_id)

    if user and user.get("status") == 1:  # User is allowed
        await bot.approve_chat_join_request(
            chat_id=join_request.chat.id,
            user_id=user_id
        )

        try:
            await bot.send_message(
                chat_id=user_id,
                text="✅ شما با موفقیت به کانال اضافه شدید.\n\n"
                     "حالا می‌توانید سفارش خرید یا فروش ثبت کنید.",
                reply_markup=get_user_main_menu()
            )
        except:
            pass
    else:
        # Reject if not approved
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


# ==================== خروج اضطراری - مرحله اول ====================


@user_router.message(F.text == "🚨 خروج اضطراری 🚨")
async def emergency_exit_request(message: Message, state: FSMContext):
    await message.answer(
        "⚠️ **هشدار مهم**\n\n"
        "آیا واقعاً می‌خواهید **خروج اضطراری** انجام دهید؟\n"
        "با این کار وضعیت شما به حالت اضطراری تغییر کرده و ممکن است تا اطلاع ثانوی نتوانید سفارش ثبت کنید.",
        reply_markup=get_emergency_confirmation_keyboard()
    )
    await state.set_state("waiting_for_emergency_confirmation")


# ==================== پردازش تأیید یا انصراف ====================


@user_router.callback_query(F.data.startswith("confirm_emergency_exit"))
async def confirm_emergency_exit(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id

    await set_user_status(user_id, 4)  # 4 = emergency exit

    await callback.message.edit_text(
        "🚨 **خروج اضطراری با موفقیت انجام شد.**\n\n"
        "وضعیت شما به حالت اضطراری تغییر کرد.",
        reply_markup=None
    )

    try:
        await bot.ban_chat_member(
            chat_id=CHANNEL_ID,
            user_id=user_id,
            revoke_messages=True
        )
        await callback.answer("✅ کاربر از گروه حذف شد", show_alert=True)
    except Exception as e:
        await callback.answer("⚠️ خطا در حذف کاربر از گروه", show_alert=True)
        print(f"Error kicking user: {e}")

    await state.clear()


@user_router.callback_query(F.data.startswith("cancel_emergency_exit"))
async def cancel_emergency_exit(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✅ انصراف از خروج اضطراری.\n"
        "عملیاتی انجام نشد.",
        reply_markup=None
    )
    await state.clear()


# ==================== راهنما ====================

@user_router.message(F.text == "ℹ️ راهنما")
async def back_to_main_menu(message: Message):
    await message.answer(
        "🟨 نحوه لفظ دادن:\n\n"
        "💡 فرمول:\n"
        "قیمت (۳ یا ۵ رقمی) + نوع معامله + حجم (تا ۳ کیلو)\n\n"
        "🔸 (خ = خرید یا ف = فروش) + (ف‌ = فردا)+ (ن = نقدی)\n\n"
        "📌 نمونه‌ها:\n"
        "۴۵۳۰۰ف۲ → ۲ کیلو فروش حواله روز فی ۴۵۳۰۰\n"
        "۳۰۰خف۳ → ۳ کیلو خرید حواله فردا فی ۴۵۳۰۰\n"
        "۳۰۰خن۲ → ۲ کیلو خرید نقد حاضر فی ۴۵۳۰۰\n"
        "۳۰۰خفن۱: فوری → ۱ کیلو نقد بی حواله فردا فی ۴۵۳۰۰\n\n"
        "📄 توضیحات: برای لفظ های نقدی پس از علامت دو نقطه (:) امکان نوشتن توضیحات می باشد.(اختیاری)\n\n"
        "⏱ اعتبار: ۶۰ ثانیه پس از تایید و ارسال\n\n"
        "❌ برای لغو: کلیک روی «نشد» یا نوشتن«ن» در خصوصی\n\n"
    )
