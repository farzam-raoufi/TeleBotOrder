from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command

from database import get_users_by_status, set_user_status
from keyboards.inline import get_admin_approval_keyboard, get_start_keyboard
from dotenv import load_dotenv
import os

admin_router = Router()
load_dotenv()

ADMIN_ID =  [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID



@admin_router.message(F.text == "📋 کاربران در انتظار تأیید")
async def show_pending_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    pending = await get_users_by_status(0)
    
    if not pending:
        await message.answer("✅ در حال حاضر کاربری در انتظار تأیید نیست.")
        return

    for user in pending:
        text = f"👤 <b>{user['name']}</b>\n🆔 <code>{user['tel_id']}</code>\n📅 {user['created_at'][:16]}"
        
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_approval_keyboard(user['tel_id'])
        )

    await message.answer(f"✅ {len(pending)} کاربر در انتظار بررسی نمایش داده شد.")



@admin_router.message(F.text == "👥 لیست همه کاربران")
async def show_all_users(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    users = await get_users_by_status(1)
    
    if not users:
        await message.answer("Currently no user.", show_alert=True)
        return
    
    for user in users:
        text = f"👤 نام: {user['name']}\n🆔 آیدی: `{user['tel_id']}`\n📅 تاریخ: {user['created_at'][:16]}"
        
        await message.answer(
            text,
            parse_mode="HTML"
        )
    
    await message.answer(f"{len(users)} کاربر فعال.")



@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 1)  # approved

    # ارسال پیام به کاربر
    try:
        await bot.send_message(
            chat_id=user_tel_id,
            text="✅ **تبریک!**\n\n"
                 "درخواست ثبت‌نام شما توسط ادمین تأیید شد.\n"
                 "حالا می‌توانید از امکانات ربات استفاده کنید."
        )
    except:
        pass  # کاربر بات را بلاک کرده یا شروع نکرده
    
    await callback.answer("✅ کاربر تأیید شد", show_alert=True)
    await callback.message.edit_text(callback.message.text + "\n\n✅ تأیید شد")


@admin_router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    
    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 2)  # rejected
    
    # ارسال پیام به کاربر
    try:
        await bot.send_message(
            chat_id=user_tel_id,
            text="❌ متأسفانه درخواست ثبت‌نام شما توسط ادمین رد شد.\n\n"
                 "در صورت تمایل می‌توانید دوباره درخواست دهید:",
            reply_markup=get_start_keyboard()   # ← دکمه درخواست اضافه شد
        )
    except:
        pass

    await callback.answer("❌ کاربر رد شد", show_alert=True)
    await callback.message.edit_text(callback.message.text + "\n\n❌ رد شد")



@admin_router.callback_query(F.data.startswith("banned_"))
async def banned_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    
    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 3)  # banned
    
    # ارسال پیام به کاربر
    try:
        await bot.send_message(
            chat_id=user_tel_id,
            text="⛔ متأسفانه حساب شما مسدود شد."
        )
    except:
        pass

    await callback.answer("⛔ کاربر مسدود شد.", show_alert=True)
    await callback.message.edit_text(callback.message.text + "\n⛔ مسدود شد")