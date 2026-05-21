# handlers/order.py
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import BaseFilter
from dotenv import load_dotenv
from persiantools import jdatetime
import datetime
import zoneinfo
import jdatetime
import os
import re


from utils.parser import parse_order_text, fa_to_en_digits
from database import (
    get_user,
    user_has_permission,
    create_order,
    update_order_group_info,
    get_last_order,
    cancel_last_user_order,
    get_order,
    create_order_acceptance
)
from keyboards.inline import get_confirmation_keyboard, get_order_keyboard
from states.order import OrderStates

load_dotenv()
order_router = Router()
GROUP_ID = int(os.getenv("GROUP_ID"))
tehran_tz = zoneinfo.ZoneInfo("Asia/Tehran")


# ==================== Custom Filter ====================
class IsOrderText(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        text = fa_to_en_digits(message.text)

        if not text:
            return False
        # فقط پیام‌هایی که با ۳ تا ۵ رقم شروع مبشوند و بعد از آن ها خ یا ف باشد
        return bool(re.match(r'^\d{3,5}[ف|خ]', text.strip()))
# ==================== Router & Handler ====================


# ==================== تایید و ارسال به گروه ====================
@order_router.callback_query(OrderStates.waiting_for_confirmation)
async def process_confirmation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    parsed = data.get("parsed_order")
    if not parsed:
        await callback.answer("خطا: اطلاعات یافت نشد!", show_alert=True)
        await state.clear()
        return

    if callback.data == "confirm_order":
        timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()
        tehran_jalali = jdatetime.datetime.fromtimestamp(
            timestamp=timestamp, tz=tehran_tz
        )
        tehran_houer = tehran_jalali.strftime("%H")

        if (parsed["trade_date"] == 2):
            order_date = tehran_jalali + datetime.timedelta(days=1)
        else:
            order_date = tehran_jalali

        if (int(tehran_houer) > 15 and parsed["trade_date"] == 1):
            await callback.message.edit_text("بعد از ساعت 15 امکان ثبت لفظ امروزی و نقدی حاضر وجود ندارد.\n❌ لفظ لغو شد.")
            await callback.answer("لغو شد")
            await state.clear()
            return

        # ==================== ابطال لفظ‌های قبلی ====================
        canceled_orders = await cancel_last_user_order(offerer_id=int(data["user_id"]))

        # لوپ برای ویرایش پیام‌های قبلی در گروه
        if canceled_orders:
            for order in canceled_orders:
                if order.get("group_message_id") and order.get("group_chat_id"):
                    try:
                        await callback.bot.edit_message_text(
                            chat_id=order["group_chat_id"],
                            message_id=order["group_message_id"],
                            text=order["group_text"] +
                            "\n\n❌",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.error(f"خطا در ویرایش پیام گروه: {e}")

        # ساخت متن برای گروه
        group_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} 💵 {parsed['volume']} تا"""
        if parsed['description']:
            group_text += f"\n- {parsed['description']}\n"

        # ==================== ثبت سفارش جدید ====================
        order_id = await create_order(
            offerer_id=data["user_id"],
            offerer_tel_id=callback.from_user.id,
            price=parsed["price"],
            order_type=parsed["order_type"],   # خرید یا فروش
            total_volume=parsed["volume"],
            payment_type=parsed["payment_type"],
            trade_date=order_date.strftime("%Y/%m/%d"),
            description=parsed["description"],
            group_text=group_text,
            created_at=timestamp,
            status="active"
        )

        # ارسال به گروه
        sent_msg = await callback.bot.send_message(
            chat_id=GROUP_ID,
            text=group_text,
            parse_mode="HTML",
            reply_markup=get_order_keyboard(
                order_id,
                parsed['volume'])
        )

        await update_order_group_info(order_id, sent_msg.message_id, sent_msg.chat.id)

        await callback.message.edit_text(
            text=callback.message.text + "\n✅ تأیید و ارسال",
            parse_mode="HTML"
        )
        await callback.answer("ارسال شد ✅")

    elif callback.data == "cancel_order":
        await callback.message.edit_text(text=callback.message.text + "\n لفظ لغو شد. ❌")
        await callback.answer("لغو شد")
        await state.clear()

# ==================== ایجاد کردن لفظ ====================


@order_router.message(F.text, IsOrderText())
async def handle_order_message(message: Message, state: FSMContext):

    timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()

    tehran_jalali = jdatetime.datetime.fromtimestamp(
        timestamp=timestamp, tz=tehran_tz)
    tehran_houer = tehran_jalali.strftime("%H")

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

    parsed = parse_order_text(
        message.text,
        int(tehran_houer) > 15
    )

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

    lastOrder = await get_last_order() or {"price": 50000}
    if (len(parsed['price']) == 3):
        parsed['price'] = str(lastOrder["price"])[:-3] + parsed['price']
    parsed['price'] = int(parsed['price'])

    if (abs(parsed['price'] - lastOrder["price"]) > 500):
        await message.answer(
            f"⚠️ تفاوت قیمت لفظ شما با آخرین لفظ نباید بیشتر یا کمتر از 500 خط باشد\nبازه قیمت:\n{format(int(lastOrder["price"]+500), ",")} الی {format(int(lastOrder["price"]-500), ",")}\n"
        )
        return

    order_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} 💵 {parsed['volume']} تا"""
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


@order_router.message(F.text == "ن")
async def show_pending_users(message: Message):
    user = await get_user(message.from_user.id)

    # ==================== ابطال لفظ‌های قبلی ====================
    canceled_orders = await cancel_last_user_order(offerer_id=int(user["id"]))

    # لوپ برای ویرایش پیام‌های قبلی در گروه
    if canceled_orders:
        for order in canceled_orders:
            if order.get("group_message_id") and order.get("group_chat_id"):
                try:
                    await message.bot.edit_message_text(
                        chat_id=order["group_chat_id"],
                        message_id=order["group_message_id"],
                        text=order["group_text"] +
                        "\n\n❌",
                        parse_mode="HTML"
                    )
                    await message.answer(
                        text=order["group_text"] +
                        "\n\n❌",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logging.error(f"خطا در ویرایش پیام گروه: {e}")


# ======================================== قبول کردن لفظ ========================================

@order_router.callback_query(F.data.startswith("accept_order_"))
async def handle_accept_order(callback: CallbackQuery):

    user = await get_user(callback.from_user.id)
    if not user:
        await callback.answer(
            "⛔ متأسفانه شما دسترسی ندارید."
        )
        return

    # ======================== check status and permission check ========================

    # ======================== status 1 = approved & capacity ========================

    if user["status"] != 1:
        if user["status"] == 0:
            await callback.answer("⏳ درخواست شما هنوز توسط ادمین تأیید نشده است.")
        elif user["status"] == 2:
            await callback.answer("❌ درخواست شما رد شده است.")
        elif user["status"] == 3:
            await callback.answer("⛔ حساب شما مسدود شده است.")
        return

    # ======================== permission 0 = set order ========================
    user_id = user["id"]  # id داخلی دیتابیس

    has_permission = await user_has_permission(user_id, permission=0)

    if not has_permission:
        await callback.answer(
            "⚠️ شما دسترسی ثبت لفظ ندارید.\n"
        )
        return
    # ========================

    try:
        _, _, order_id_str, volume_str = callback.data.split("_")
        order_id = int(order_id_str)
        volume = int(volume_str)
    except:
        await callback.answer("خطا در پردازش درخواست")
        return

    order = await get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return

    if order['remaining_volume'] < volume:
        await callback.answer("این مقدار دیگر موجود نیست!", show_alert=True)
        return

    # ثبت پذیرش
    await create_order_acceptance(
        order_id=order_id,
        offerer_id=order['offerer_id'],
        offerer_tel_id=order['offerer_tel_id'],
        acceptor_id=user_id,
        acceptor_tel_id=callback.from_user.id,
        volume=volume
    )

    # محاسبه باقی‌مانده جدید
    new_remaining = order['remaining_volume'] - volume

    # کیبورد جدید
    new_keyboard = get_order_keyboard(order_id, new_remaining)

    try:
        await callback.bot.edit_message_text(
            chat_id=order['group_chat_id'],
            message_id=order['group_message_id'],
            text=order['group_text'],
            reply_markup=new_keyboard
        )
    except Exception as e:
        logging.error(f"ویرایش پیام گروه شکست: {e}")

    await callback.answer(f"✅ {volume} کیلو با موفقیت ثبت شد", show_alert=False)
