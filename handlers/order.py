# handlers/order.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import BaseFilter
from dotenv import load_dotenv
import os
import re


from utils.parser import parse_order_text, fa_to_en_digits
from database import (
    get_user,
    user_has_permission
)
import database as db
from keyboards.inline import get_confirmation_keyboard, get_order_keyboard
from states.order import OrderStates
from datetime import datetime

load_dotenv()
order_router = Router()
GROUP_ID = int(os.getenv("GROUP_ID"))


# ==================== Custom Filter ====================
class IsOrderText(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        text = fa_to_en_digits(message.text)

        if not text:
            return False
        # فقط پیام‌هایی که با ۳ تا ۵ رقم شروع شوند
        return bool(re.match(r'^\d{3,5}', text.strip()))
# ==================== Router & Handler ====================


# ==================== قبول کردن لفظ ====================

@order_router.callback_query(OrderStates.waiting_for_confirmation)
async def process_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parsed = data.get("parsed_order")

    if not parsed:
        await callback.answer("خطا: اطلاعات یافت نشد!", show_alert=True)
        await state.clear()
        return

    if callback.data == "confirm_order":
        # ثبت در دیتابیس
        # order_id = await db.create_order(
        #     offerer_id=data["user_id"],
        #     offerer_tel_id=callback.from_user.id,
        #     price=parsed["price"],
        #     order_type=parsed["order_type"],   # خرید یا فروش
        #     volume=parsed["volume"],
        #     payment_type=parsed["payment_type"],
        #     trade_date=parsed["trade_date"],
        #     description=parsed["description"]
        # )

        group_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} {parsed['volume']} تا"""
        if parsed['description']:
            group_text += f"\n- {parsed['description']}\n"
        # ارسال به گروه

        sent_msg = await callback.bot.send_message(
            chat_id=GROUP_ID,
            text=group_text,
            parse_mode="HTML",
            reply_markup=get_order_keyboard(
                "order_id",
                parsed['volume']
            )   # دکمه قبول کردن در گروه
        )

        # await db.update_order_group_info(order_id, sent_msg.chat.id, sent_msg.message_id)

        await callback.message.edit_text(
            text=callback.message.text + "✅ تأیید و ارسال",
            parse_mode="HTML"
        )
        await callback.answer("ارسال شد ✅")

    elif callback.data == "cancel_order":
        await callback.message.edit_text("❌ لغو لفظ.")
        await callback.answer("لغو شد")

    await state.clear()


# ==================== ایجاد کردن لفظ ====================

@order_router.message(F.text, IsOrderText())
async def handle_order_message(message: Message, state: FSMContext):

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer(
            "⛔ متأسفانه شما دسترسی ندارید."
        )
        return

    # ======================== check status and permission check ========================

    # ======================== status 1 = approved & capacity ========================

    if user["status"] != 1:
        if user["status"] == 0:
            await message.answer("⏳ درخواست شما هنوز توسط ادمین تأیید نشده است.")
        elif user["status"] == 2:
            await message.answer("❌ درخواست شما رد شده است.")
        elif user["status"] == 3:
            await message.answer("⛔ حساب شما مسدود شده است.")
        return

    # ======================== permission 0 = set order ========================
    user_id = user["id"]  # id داخلی دیتابیس

    has_permission = await user_has_permission(user_id, permission=0)

    if not has_permission:
        await message.answer(
            "⚠️ شما دسترسی ثبت لفظ ندارید.\n"
        )
        return

    # ======================== ۳. پردازش لفظ ========================

    """دریافت و پردازش لفظ کاربر"""
    if not message.text or len(message.text.strip()) < 4:
        return

    parsed = parse_order_text(message.text, False)

    if not parsed:
        await message.answer(
            "⚠️ ساختار لفظ صحیح نمی‌باشد .\n"
        )
        return

    if parsed['volume'] > int(user["capacity"]):
        await message.answer(
            f"⚠️ شما دسترسی ثبت لفظ بیشتر از {user["capacity"]} کیلو را ندارید.\n"
        )
        return
    if parsed['volume'] < 1:
        await message.answer(
            "⚠️ کمترین وزن 1 می‌باشد.\n"
        )
        return

    # order_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {"نقدی💵" if parsed['order_type'] == "فروش" else "" } {"حاظر" if parsed['trade_date'] == "امروز" else "فردا" } تا {parsed['volume']}"""
    order_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} تا {parsed['volume']}"""
    if parsed['description']:
        order_text += f"\n- {parsed['description']}\n"

    # ذخیره اطلاعات در FSM
    await state.update_data(parsed_order=parsed, user_id=user["id"])

    # تأیید به کاربر در خصوصی
    await message.answer(
        text=order_text,
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_confirmation)
