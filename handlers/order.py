# handlers/order.py
import logging
from aiogram import Bot, Router, F
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
    create_order_acceptance,
    get_expired_orders,
    mark_order_as_expired,
    get_user_today_volume,
    is_holiday,
    get_config_by_name
)
from keyboards.inline import get_confirmation_keyboard, get_order_keyboard
from keyboards.reply import get_order_cancel_menu, get_user_main_menu
from states.order import OrderStates

load_dotenv()
order_router = Router()
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
ADMIN_CHANNEL_ID = int(os.getenv("ADMIN_CHANNEL_ID"))
tehran_tz = zoneinfo.ZoneInfo("Asia/Tehran")


ADMIN_ID = [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID


accept_order_click = {}
last_user_actions = {}


async def clean_old_clicks():
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    for k in list(accept_order_click.keys()):
        if timestamp - accept_order_click[k] > 10:
            del accept_order_click[k]
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

    user = await get_user(callback.from_user.id)

    if user:
        match user["status"]:
            case 1:
                # کاربر تایید شده، ادامه برنامه
                pass
            case 0:
                await callback.answer("درخواست شما برای استفاده از ربات ثبت شده. لطفا منتظر تایید ادمین بمانید.")
                return
            case 2:
                await callback.answer("درخواست عضویت شما توسط ادمین تأیید نشده..")
                return
            case 3:
                await callback.answer("⛔ متأسفانه حساب شما مسدود شد.")
                return
            case 4:
                await callback.answer("🚨حساب شما در حالت اضطراری قرار دارد🚨")
                return
            case _:
                await callback.answer("وضعیت کاربر نامعتبر است.")
                return

    data = await state.get_data()
    parsed = data.get("parsed_order")
    confirmation_timestamp = data.get("confirmation_timestamp")

    # ==================== چک کردن زمان (60 ثانیه) ====================
    timestamp = int(datetime.datetime.now(
        datetime.timezone.utc).timestamp())

    if timestamp - confirmation_timestamp > 60:
        await callback.message.edit_text(
            "⏳به علت گذشت زمان طولانی این لفظ منقضی شده.\n"
            "لطفاً دوباره لفظ را ثبت کنید."
        )
        # await callback.answer("زمان تایید منقضی شده است", show_alert=True)
        await state.clear()
        return

    if not parsed:
        await callback.answer("خطا: اطلاعات یافت نشد!", show_alert=True)
        await state.clear()
        return

    if callback.data == "confirm_order":

        tehran_jalali = jdatetime.datetime.fromtimestamp(
            timestamp=timestamp, tz=tehran_tz
        )
        tehran_houer = tehran_jalali.strftime("%H")

        if (parsed["trade_date"] == 2):
            order_date = tehran_jalali + datetime.timedelta(days=1)
        else:
            order_date = tehran_jalali

        if (int(tehran_houer) > 14 and parsed["trade_date"] == 1):
            await callback.message.edit_text("بعد از ساعت 15 امکان ثبت لفظ امروزی و نقدی حاضر وجود ندارد.\n❌ لفظ لغو شد.")
            await callback.answer("لغو شد")
            await state.clear()
            return

        while True:
            order_weekday = order_date.weekday()
            order_date_str = order_date.strftime("%Y%m%d")

            isـorder_date_holiday = await is_holiday(order_date_str)

            if order_weekday not in [5, 6] and not isـorder_date_holiday:
                break

            order_date += jdatetime.timedelta(days=1)

        # ==================== ابطال لفظ‌های قبلی ====================
        canceled_orders = None
        if not is_admin(data["user_id"]):
            canceled_orders = await cancel_last_user_order(offerer_id=int(data["user_id"]))

        # لوپ برای ویرایش پیام‌های قبلی در گروه
        if canceled_orders:
            for order in canceled_orders:
                if order.get("group_message_id") and order.get("group_chat_id"):
                    try:

                        if order['description']:
                            order["group_text"] += f"{order['description']}"

                        await callback.bot.edit_message_text(
                            chat_id=order["group_chat_id"],
                            message_id=order["group_message_id"],
                            text=order["group_text"] +
                            "\n❌",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logging.error(f"خطا در ویرایش پیام گروه: {e}")

        # ساخت متن برای گروه
        group_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} 💵 {parsed['volume']} تا"""

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

        if parsed['description']:
            group_text += f"{parsed['description']}"

        # ارسال به گروه
        sent_msg = await callback.bot.send_message(
            chat_id=CHANNEL_ID,
            text=group_text,
            parse_mode="HTML",
            reply_markup=get_order_keyboard(
                order_id,
                parsed['volume'])
        )

        await update_order_group_info(order_id, sent_msg.message_id, sent_msg.chat.id)

        await callback.message.edit_text(
            text=callback.message.text,
            parse_mode="HTML"
        )

        # نمایش منوی نشد / بازگشت
        await callback.message.answer(
            "✅لفظ توسط شما تایید شد.",
            reply_markup=get_order_cancel_menu(
                last_action=last_user_actions[callback.from_user.id])
        )

        # ==================== ارسال نسخه کامل به کانال ادمین‌ها ====================

        chat_id_str = str(sent_msg.chat.id)
        if chat_id_str.startswith('-100'):
            channel_id = chat_id_str[4:]  # Remove -100
            public_link = f"https://t.me/c/{channel_id}/{sent_msg.message_id}"
        else:
            public_link = "#"

        admin_text = f"""🆔 <b>شماره سفارش:</b> <code>{order_id}</code>\n👤 <b>کاربر: {user['name']}</b>\n🔗 <b>یوزرنیم تلگرام:</b> @{callback.from_user.username or 'No username'}\n🆔 <b>شناسه تلگرام کاربر:</b> <code>{callback.from_user.id}</code>\n💰 {group_text}\n📍 <a href="{public_link}">مشاهده پیام در کانال</a>\n⏰ {tehran_jalali.strftime("%Y/%m/%d %H:%M:%S")}"""

        await callback.bot.send_message(
            chat_id=ADMIN_CHANNEL_ID,
            text=admin_text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    elif callback.data == "cancel_order":
        await callback.message.edit_text(text=callback.message.text + "\n لفظ لغو شد. ❌")
        await callback.answer("لغو شد")
        await state.clear()

# ==================== ایجاد کردن لفظ ====================


@order_router.message(F.text, IsOrderText())
async def handle_order_message(message: Message, state: FSMContext):

    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    tehran_jalali = jdatetime.datetime.fromtimestamp(
        timestamp=timestamp, tz=tehran_tz)

    tehran_houer = tehran_jalali.strftime("%H")
    tehran_houer_minut = tehran_jalali.strftime("%H%M")

    working_hours = await get_config_by_name("ساعت-کاری")

    if working_hours:
        working_hours = working_hours[0]['value']

        start, end = working_hours.split('-')

        start_hour = start[:2]
        start_min = start[2:]
        end_hour = end[:2]
        end_min = end[2:]

        if (not (int(start) < int(tehran_houer_minut) and int(tehran_houer_minut) < int(end))):
            await message.answer(
                "⛔ ربات در حال حاضر فعال نیست.\n\n"
                f"ساعت کاری ما از {start_hour}:{start_min} تا {end_hour}:{end_min} است.\n"
                "لطفاً در این بازه زمانی سفارش خود را ثبت کنید.\n\n"
                "ممنون از همراهی شما 😊"
            )
            return

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
        elif user["status"] == 4:
            await message.answer("🚨حساب شما در حالت اضطراری قرار دارد🚨")
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

    today = tehran_jalali.strftime("%Y%m%d")

    # چک کردن تعطیلی
    is_today_holiday = await is_holiday(today)

    weekday = tehran_jalali.weekday()  # 0 sat 1 sun 2 mon 3 tue 4 wed 5 thu 6 fri

    force_tomorrow = (
        is_today_holiday or
        weekday in [5, 6] or
        int(tehran_houer) > 14
    )

    parsed = parse_order_text(
        message.text,
        force_tomorrow
    )

    if not parsed:
        await message.answer(
            "⚠️ ساختار لفظ صحیح نمی‌باشد .\n"
        )
        return
    # check dayli user capacity
    today_volume = int(await get_user_today_volume(user_id))

    if (int(parsed['volume']) + today_volume) > int(user["capacity"]):
        await message.answer(
            f"⚠️ شما دسترسی معامله بیشتر از {user["capacity"]} کیلو را در روز ندارید.\n"
        )
        return
    if parsed['volume'] < 1:
        await message.answer(
            "⚠️ کمترین وزن 1 می‌باشد.\n"
        )
        return
    if parsed['volume'] > 3:
        await message.answer(
            "⚠️ بیشترین وزن 3 کیلو می‌باشد.\n"
        )
        return

    lastOrder = await get_last_order() or {"price": 50000000, "expires_at":0}
    if (len(parsed['price']) == 3):
        parsed['price'] = int(str(lastOrder["price"])[
            :-6] + (parsed['price']+"000"))
    else:
        parsed['price'] = int(parsed['price'])*1000

    if not is_admin(message.from_user.id):
        if (abs(parsed['price'] - lastOrder["price"]) > 1000000):
            await message.answer(
                f"⚠️ تفاوت قیمت لفظ شما با آخرین لفظ نباید بیشتر یا کمتر از 1000 .خط باشد\nبازه قیمت:\n{format(int(lastOrder["price"]+1000000), ",")} الی {format(int(lastOrder["price"]-1000000), ",")}\n"
            )
            return
        if (lastOrder["expires_at"] > timestamp and parsed['price'] > lastOrder["price"]):
            await message.answer(
                f"⚠️ در حال حاضر لفظ فعالی با قیمت کمتر از این لفظ وجود دارد."
            )
            return

    order_text = f"""{format(int(parsed['price']), ",")} {"🔴" if parsed['order_type'] == "فروش" else "🔵"} {parsed['order_type']} {parsed["order"]} 💵 {parsed['volume']} تا"""
    if parsed['description']:
        order_text += f"{parsed['description']}"

    # ذخیره اطلاعات در FSM
    await state.update_data(
        parsed_order=parsed,
        user_id=user["id"],
        confirmation_timestamp=int(datetime.datetime.now(
            datetime.timezone.utc).timestamp()),
    )

    # تأیید به کاربر در خصوصی
    await message.answer(
        text=order_text,
        parse_mode="HTML",
        reply_markup=get_confirmation_keyboard()
    )
    await state.set_state(OrderStates.waiting_for_confirmation)
    last_user_actions[message.from_user.id] = message.text


@order_router.message(F.text.in_({"ن", "❌ نشد"}))
async def show_pending_users(message: Message):
    user = await get_user(message.from_user.id)
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    # ==================== ابطال لفظ‌های قبلی ====================
    canceled_orders = await cancel_last_user_order(offerer_id=int(user["id"]))

    # لوپ برای ویرایش پیام‌های قبلی در گروه
    if canceled_orders:
        for order in canceled_orders:
            if (order.get("created_at") > timestamp+10):
                await message.answer(
                    text="🤖 پس از گذشت 10 ثانیه از دادن لفظ، میتوان میتوان را منقضی کرد.",
                    parse_mode="HTML",
                    reply_markup=get_user_main_menu()
                )

            if order.get("group_message_id") and order.get("group_chat_id"):
                try:
                    if order['description']:
                        order["group_text"] += f"{order['description']}"
                    await message.bot.edit_message_text(
                        chat_id=order["group_chat_id"],
                        message_id=order["group_message_id"],
                        text=order["group_text"] +
                        "\n❌",
                        parse_mode="HTML"
                    )
                    # await message.answer(
                    #     text=order["group_text"] +
                    #     "\n\n❌",
                    #     parse_mode="HTML",
                    #     reply_markup=get_user_main_menu()
                    # )
                    await message.answer(
                        text="🤖کلیه لفظ ها منقضی شدند.",
                        parse_mode="HTML",
                        reply_markup=get_user_main_menu()
                    )
                except Exception as e:
                    logging.error(f"خطا در ویرایش پیام گروه: {e}")


# ======================================== قبول کردن لفظ ========================================

@order_router.callback_query(F.data.startswith("accept_order_"))
async def handle_accept_order(callback: CallbackQuery, bot: Bot):
    try:
        _, _, order_id_str, volume_str = callback.data.split("_")
        order_id = int(order_id_str)
        volume = int(volume_str)
    except:
        await callback.answer("خطا در پردازش درخواست")
        return

    # ======================== date and time ========================
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    tehran_jalali = jdatetime.datetime.fromtimestamp(
        timestamp=timestamp, tz=tehran_tz)
    tehran_date_and_time = tehran_jalali.strftime("%Y/%m/%d - %H:%M:%S")

    # ================================================

    user_id = callback.from_user.id
    key = f"{user_id}_{order_id_str}_{volume_str}"
    # ======================== چک کردن کلیک قبلی ========================
    last_click = accept_order_click.get(key)

    if not last_click or (timestamp - last_click) > 4:
        accept_order_click[key] = timestamp
        return
    await clean_old_clicks()

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
        elif user["status"] == 4:
            await callback.answer("⛔ حساب شما مسدود شده است.")
        return

    # ======================== permission 20 = accept order ========================
    user_id = user["id"]  # id داخلی دیتابیس

    has_permission = await user_has_permission(user_id, permission=1)

    if not has_permission:
        await callback.answer(
            "⚠️ شما دسترسی ندارید.\n"
        )
        return
    # ========================

    order = await get_order(order_id)
    if not order:
        await callback.answer("سفارش یافت نشد", show_alert=True)
        return
    if (user_id == order['offerer_id']):
        await callback.answer("این لفظ متعلق به خود شما میباشد", show_alert=True)
        return

    # check dayli user capacity
    today_volume = int(await get_user_today_volume(user_id))

    if (volume + today_volume) > int(user["capacity"]):
        await callback.answer(
            f"⚠️ شما دسترسی معامله بیشتر از {user["capacity"]} کیلو را در روز ندارید.\n"
        )
        return

    # ======================== reject if expired ========================
    if order['status'] == "expired":
        await callback.answer("این لفظ منقضی شد!", show_alert=True)
        return

    if int(order['expires_at']) < int(timestamp):
        await mark_order_as_expired(order['id'])
        await callback.answer("این لفظ منقضی شد!", show_alert=True)

        # تغییر وضعیت در دیتابیس

        # ویرایش پیام در گروه (اینجا منطق تلگرام است)
        # if order.get('group_chat_id') and order.get('group_message_id'):
        #     new_text = order.get('group_text', '') + \
        #         "\n\n⏰ **این لفظ منقضی شد**"

        #     await callback.bot.edit_message_text(
        #         chat_id=order['group_chat_id'],
        #         message_id=order['group_message_id'],
        #         text=new_text,
        #         parse_mode="HTML"
        #     )
        return
    # ========================

    if order['remaining_volume'] < volume:
        await callback.answer("این مقدار دیگر موجود نیست!", show_alert=True)
        return

    # ثبت پذیرش
    order_acceptance_id = await create_order_acceptance(
        order_id=order_id,
        offerer_id=order['offerer_id'],
        offerer_tel_id=order['offerer_tel_id'],
        acceptor_id=user_id,
        acceptor_tel_id=callback.from_user.id,
        volume=volume,
        accepted_at=timestamp
    )

    # محاسبه باقی‌مانده جدید
    new_remaining = order['remaining_volume'] - volume

    # کیبورد جدید
    new_keyboard = get_order_keyboard(order_id, new_remaining)

    if new_remaining == 0:
        order['group_text'] += f" 🤝🏻✅"

    try:
        if order['description']:
            order["group_text"] += f"{order['description']}"
        await callback.bot.edit_message_text(
            chat_id=order['group_chat_id'],
            message_id=order['group_message_id'],
            text=order['group_text'],
            reply_markup=new_keyboard
        )
    except Exception as e:
        logging.error(f"ویرایش پیام گروه شکست: {e}")

    try:
        await bot.send_message(
            chat_id=order['offerer_tel_id'],
            text=f"{"🔴" if order['order_type'] == "فروش" else "🔵"} {order['order_type']}\n" +
            "🤝🏻 معامله\n" +
            f"فی: {format(int(order["price"]), ",")}\n" +
            f"مقدار: {volume} کیلو\n" +
            f"برای: {order["trade_date"]}\n" +
            f"شناسه: {order_acceptance_id}\n" +
            # f"({order['group_text'][9:-7]})\n" +
            f"زمان معامله: \n{tehran_date_and_time}\n"
        )
        await bot.send_message(
            chat_id=callback.from_user.id,
            text=f"{"🔵" if order['order_type'] == "فروش" else "🔴"} {"خرید" if order['order_type'] == "فروش" else "فروش"}\n" +
            "🤝🏻 معامله\n" +
            f"فی: {format(int(order["price"]), ",")}\n" +
            f"مقدار: {volume} کیلو\n" +
            f"برای: {order["trade_date"]}\n" +
            f"شناسه: {order_acceptance_id}\n" +
            # f"({order['group_text'][9:-7]})\n" +
            f"زمان معامله: {tehran_date_and_time}\n"
        )
    except:
        pass  # کاربر بات را بلاک کرده یا شروع نکرده


# ================================================================================
# ======================== mark expired orders as expired ========================

async def process_expired_orders(bot: Bot):
    timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    expired_orders = await get_expired_orders(timestamp)

    if not expired_orders:
        return

    for order in expired_orders:
        try:
            # تغییر وضعیت در دیتابیس
            await mark_order_as_expired(order['id'])

            # if order.get('group_chat_id') and order.get('group_message_id'):
            #     new_text = order.get('group_text', '') + \
            #         "\n\n⏰ **این لفظ منقضی شد**"

            #     await bot.edit_message_text(
            #         chat_id=order['group_chat_id'],
            #         message_id=order['group_message_id'],
            #         text=new_text,
            #         parse_mode="HTML"
            #     )

        except Exception as e:
            logging.error(
                f"خطا در پردازش منقضی کردن سفارش {order.get('id')}: {e}")
# ================================================================================
