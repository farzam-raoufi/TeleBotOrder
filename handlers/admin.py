from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database import get_pending_users, set_user_status
from keyboards.inline import get_admin_approval_keyboard
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


@admin_router.callback_query(F.data == "show_pending")
async def show_pending_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    pending = await get_pending_users()
    
    if not pending:
        await callback.answer("✅ Currently no pending users.", show_alert=True)
        return
    
    for user in pending:
        text = f"👤 نام: {user['name']}\n🆔 آیدی: `{user['tel_id']}`\n📅 تاریخ: {user['created_at'][:16]}"
        
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_admin_approval_keyboard(user['tel_id'])
        )
    
    await callback.answer(f"{len(pending)} کاربر در انتظار بررسی.")

@admin_router.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        return
    
    pending = await get_pending_users()
    
    if not pending:
        await message.answer("✅ Currently there are no pending users.")
        return
    
    text = "📋 <b>Pending Users:</b>\n\n"
    for user in pending:
        text += f"👤 {user['name']}\n"
        text += f"🆔 `{user['tel_id']}`\n"
        text += f"📅 {user['created_at'][:16]}\n\n"
    
    await message.answer(text, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 1)  # approved
    
    await callback.answer("✅ کاربر تأیید شد", show_alert=True)
    await callback.message.edit_text(callback.message.text + "\n\n✅ تأیید شد")


@admin_router.callback_query(F.data.startswith("reject_"))
async def reject_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    
    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 2)  # rejected
    
    await callback.answer("❌ کاربر رد شد", show_alert=True)
    await callback.message.edit_text(callback.message.text + "\n\n❌ رد شد")