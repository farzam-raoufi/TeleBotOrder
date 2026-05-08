from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from database import get_user, create_user
from keyboards.inline import get_start_keyboard

user_router = Router()

@user_router.message(Command("start"))
async def cmd_start(message: Message):
    user = await get_user(message.from_user.id)
    
    if user:
        if user["status"] == 1:  # approved
            await message.answer("✅ شما تأیید شدید.\nاز منوی اصلی استفاده کنید.")
        elif user["status"] == 2:  # rejected
            await message.answer("درخواست شما توسط ادمین تأیید نشده.\nدوباره درخواست میدهید ؟.",
                reply_markup=get_start_keyboard())
        elif user["status"] == 0:
            await message.answer(
                "👋 خوش آمدید!\n\n"
                "درخواست شما برای استفاده از ربات ثبت شده. لطفا منتظر تایید ادمین بمانید."
            )
    else:
        await message.answer(
            "👋 خوش آمدید!\n\n"
            "برای استفاده از ربات، ابتدا باید توسط ادمین تأیید شوید.",
            reply_markup=get_start_keyboard()
        ) 
        
        
# await message.answer(
#     "👋 خوش آمدید!\n\n"
#     "برای استفاده از ربات، ابتدا باید توسط ادمین تأیید شوید."
# )
#


@user_router.callback_query(F.data == "request_membership")
async def request_membership(callback: CallbackQuery):
    
    user = await create_user(callback.from_user.id, callback.from_user.full_name)
     
    # اینجا می‌توانستیم وضعیت را به pending تغییر دهیم، اما فعلاً فقط اطلاع‌رسانی
    await callback.answer("درخواست شما ثبت شد. منتظر تأیید ادمین باشید.", show_alert=True)
    
    await callback.message.edit_text(
        "✅ درخواست عضویت شما ارسال شد.\n"
        "ادمین به‌زودی بررسی خواهد کرد."
    )