from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv
import os

from database import (
    get_users_by_status,
    set_user_status,
    get_user_permissions,
    get_user,
    update_user_capacity,
    user_has_permission,
    add_permission,
    remove_permission,
    get_config_by_name,
    add_config,
    delete_config_by_id,
    set_working_hours
)
from keyboards.inline import (
    get_admin_approval_keyboard,
    get_start_keyboard,
    get_user_management_keyboard,
    get_start_user_management_keyboard,
    get_permissions_management_keyboard,
    get_delete_holiday_keyboard
)
from keyboards.reply import get_settings_menu
from utils.admin_report_generator import generate_today_report
from utils.parser import fa_to_en_digits


admin_router = Router()
load_dotenv()

ADMIN_ID = [
    int(user_id)
    for user_id in os.getenv("ADMIN_ID", "").split(",")
    if user_id
]
GROUP_ID = int(os.getenv("GROUP_ID"))
INVITE_LINK = os.getenv("INVITE_LINK")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_ID


class AdminStates(StatesGroup):
    waiting_for_capacity = State()
    aiting_for_holiday_date = State()
    waiting_for_working_hours = State()


# ======================== لیست کاربران در انتظار تأیید ========================

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


# ======================== لیست کاربران ========================

# @admin_router.message(F.text.startswith("لیست کاربران"))
@admin_router.message(F.text.startswith("لیست کاربران"))
async def show_all_users(message: Message):
    if not is_admin(message.from_user.id):
        return

    # 0=pending, 1=approved, 2=rejected, 3=banned, 4
    match message.text:
        case "لیست کاربران فعال ✅":
            users = await get_users_by_status(1)
            title = "کاربر فعال"

        case "لیست کاربران در انتظار تأیید ⏳":
            users = await get_users_by_status(0)
            title = "کاربر در انتظار تأیید"

        case "لیست کاربران خروج اضطراری 🚨":
            users = await get_users_by_status(4)
            title = "کاربر خروج اضطراری"

        case "لیست کاربران مسدود شده 🚫":
            users = await get_users_by_status(3)
            title = "کاربر مسدود شده"

        case "لیست کاربران (همه کاربران) 👥":
            users = await get_users_by_status()
            title = "کاربر"
        case _:
            await message.answer("دستور نامشخص است.")
            return

    if not users:
        await message.answer(f"در حال حاضر {title} نداریم.", show_alert=True)
        return

    for user in users:

        status_dict = {
            0: "⏳ (در انتظار تأیید)",
            1: "✅ (تأیید شده)",
            2: "❌ (رد شده)",
            3: "🚫 (مسدود شده)",
            4: "🚨 (خروج اضطراری)"
        }
        status_text = status_dict.get(
            user.get('status'), f"نامشخص ({user.get('status')})")

        user_link = f'<a href="tg://user?id={user["tel_id"]}">{user['name']}</a>'

        text = f"""👤 نام: <b>{user_link}</b>
        # 🆔 آیدی: <code>{user['tel_id']}</code>
        📅 تاریخ ثبت: {user['created_at'][:16]}
        وضعیت: {status_text}"""

        if (user['status'] == 0):
            reply_markup = get_admin_approval_keyboard(user['tel_id'])
        else:
            reply_markup = get_start_user_management_keyboard(user['tel_id'])

        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    await message.answer(f"{len(users)} {title}.")

# ======================== تایید کاربر ========================


@admin_router.callback_query(F.data.startswith("approve_"))
async def approve_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما دسترسی ندارید!", show_alert=True)
        return

    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 1)  # approved

    user = await get_user(user_tel_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return
    # user_id = user['id']
    # await add_permission(user_id, 0)
    # await add_permission(user_id, 1)
    link = await bot.create_chat_invite_link(
        chat_id=GROUP_ID,
        creates_join_request=True,
        # member_limit=1,
        expire_date=None
    )

    # ارسال پیام به کاربر
    try:
        await bot.send_message(
            chat_id=user_tel_id,
            text="✅ **تبریک! حساب شما تأیید شد.**\n\n"
                 "برای دسترسی کامل به ربات، باید عضو کانال شوید:\n\n"
                 f"🔗 [عضویت در کانال]({link.invite_link})\n\n"
                 "بعد از عضویت، به‌صورت خودکار دسترسی شما فعال می‌شود.",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
    except:
        pass  # کاربر بات را بلاک کرده یا شروع نکرده

    await callback.answer("✅ کاربر تأیید شد", show_alert=True)
    await callback.message.edit_text(
        callback.message.text + "\n\n✅ تأیید شد",
        parse_mode="HTML",
        reply_markup=get_start_user_management_keyboard(user_tel_id)
    )


# ======================== رد کاربر ========================


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


# ======================== مسدید سازی کاربر ========================


@admin_router.callback_query(F.data.startswith("banned_"))
async def banned_user(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    user_tel_id = int(callback.data.split("_")[1])
    await set_user_status(user_tel_id, 3)  # banned

    user = await get_user(user_tel_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return
    user_id = user['id']
    await remove_permission(user_id, 0)
    await remove_permission(user_id, 1)

    try:
        await bot.kick_chat_member(
            chat_id=GROUP_ID,      # آیدی گروه شما
            user_id=user_tel_id
        )
        await callback.answer("✅ کاربر از گروه حذف شد", show_alert=True)
    except Exception as e:
        await callback.answer("⚠️ خطا در حذف کاربر از گروه", show_alert=True)
        print(f"Error kicking user: {e}")

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


# ======================== مدیریت کاربر ========================

@admin_router.callback_query(F.data.startswith("manage_user_"))
async def manage_user(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما ادمین نیستید!", show_alert=True)
        return

    user_tel_id = int(callback.data.split("_")[-1])

    user = await get_user(user_tel_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    permissions = await get_user_permissions(user['id'])

    perm_text = "🔑 دسترسی‌ها:\n"
    for p in permissions:
        if p == 0:
            perm_text += "• ثبت سفارش\n"
        elif p == 1:
            perm_text += "• تأیید سفارش\n"
        else:
            perm_text += f"• دسترسی ناشناخته ({p})\n"

    # === نمایش وضعیت ===
    status_dict = {
        0: "⏳ (در انتظار تأیید)",
        1: "✅ (تأیید شده)",
        2: "❌ (رد شده)",
        3: "🚫 (مسدود شده)",
        4: "🚨 (خروج اضطراری)"
    }
    status_text = status_dict.get(
        user.get('status'), f"نامشخص ({user.get('status')})")
    text = f"""👤 <b>مدیریت کاربر</b>
        نام: {user['name']}
        آیدی: <code>{user['tel_id']}</code>
        ظرفیت  روزانه: <b>{user.get('capacity', 3)}</b> کیلو
        وضعیت: {status_text}
        {perm_text}
    """

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_user_management_keyboard(user['tel_id'])
    )


# ======================== تغییر ظرفیت ========================

@admin_router.callback_query(F.data.startswith("set_capacity_"))
async def ask_for_new_capacity(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("دسترسی ندارید!", show_alert=True)
        return

    user_tel_id = int(callback.data.split("_")[-1])

    await state.update_data(user_tel_id=user_tel_id)

    await callback.message.edit_text(
        "🔢 لطفاً ظرفیت جدید کاربر را به صورت عدد وارد کنید:\n"
        "مثال: 5 یا 10",
        reply_markup=None
    )
    await state.set_state(AdminStates.waiting_for_capacity)


@admin_router.message(AdminStates.waiting_for_capacity)
async def process_new_capacity(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("شما ادمین نیستید!")
        await state.clear()
        return

    try:
        new_capacity = int(message.text.strip())
        if new_capacity < 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ لطفاً یک عدد صحیح مثبت وارد کنید.")
        return

    data = await state.get_data()
    user_tel_id = data.get("user_tel_id")

    success = await update_user_capacity(user_tel_id, new_capacity)

    if success:
        await message.answer(
            f"✅ ظرفیت کاربر با موفقیت به <b>{new_capacity}</b> کیلو تغییر یافت.",
            parse_mode="HTML"
        )

        # نمایش دوباره پنل مدیریت کاربر (به صورت پیام جدید)
        await show_updated_user_panel(message, user_tel_id)
    else:
        await message.answer("❌ خطا در تغییر ظرفیت.")

    await state.clear()


async def show_updated_user_panel(message: Message, user_tel_id: int):
    """نمایش پنل بروزرسانی شده کاربر به صورت پیام جدید"""
    user = await get_user(user_tel_id)
    if not user:
        await message.answer("❌ کاربر یافت نشد!")
        return

    permissions = await get_user_permissions(user['id'])

    perm_text = "🔑 دسترسی‌ها:\n"
    for p in permissions:
        if p == 0:
            perm_text += "• ثبت سفارش\n"
        elif p == 1:
            perm_text += "• تأیید سفارش\n"
        else:
            perm_text += f"• دسترسی ناشناخته ({p})\n"

    status_dict = {
        0: "⏳ (در انتظار تأیید)",
        1: "✅ (تأیید شده)",
        2: "❌ (رد شده)",
        3: "🚫 (مسدود شده)",
        4: "🚨 (خروج اضطراری)"
    }
    status_text = status_dict.get(
        user.get('status'), f"نامشخص ({user.get('status')})")

    text = f"""👤 <b>مدیریت کاربر</b> (بروزرسانی شده)
        نام: {user['name']}
        آیدی: <code>{user['tel_id']}</code>
        ظرفیت  هر معامله: <b>{user.get('capacity', 3)}</b> کیلو
        وضعیت: {status_text}
        {perm_text}"""

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_user_management_keyboard(user['tel_id'])
    )


# ======================== مدیریت دسترسی‌ها ========================

@admin_router.callback_query(F.data.startswith("manage_perms_"))
async def manage_permissions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما ادمین نیستید!", show_alert=True)
        return

    user_tel_id = int(callback.data.split("_")[-1])
    user = await get_user(user_tel_id)

    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    user_id = user['id']  # id اصلی جدول users

    has_set_order = await user_has_permission(user_id, 0)
    has_accept_order = await user_has_permission(user_id, 1)

    status_dict = {
        0: "⏳ (در انتظار تأیید)",
        1: "✅ (تأیید شده)",
        2: "❌ (رد شده)",
        3: "🚫 (مسدود شده)",
        4: "🚨 (خروج اضطراری)"
    }
    status_text = status_dict.get(
        user.get('status'), f"نامشخص ({user.get('status')})")

    user_link = f'<a href="tg://user?id={user["tel_id"]}">{user['name']}</a>'
    text = f"""🔑 <b>آیدی:مدیریت دسترسی‌های کاربر</b>

        👤 نام: <b>{user_link}</b>
        🆔 آیدی: <code>{user['tel_id']}</code>
        وضعیت: {status_text}

        🔸 دسترسی ثبت سفارش: {'✅ دارد' if has_set_order else '❌ ندارد'}
        🔸 دسترسی تأیید سفارش: {'✅ دارد' if has_accept_order else '❌ ندارد'}
        """

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_permissions_management_keyboard(
            user_tel_id, has_set_order, has_accept_order, user.get('status')
        )
    )


@admin_router.callback_query(F.data.startswith("toggle_perm_"))
async def toggle_permission(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("شما ادمین نیستید!", show_alert=True)
        return

    try:
        # toggle_perm_{tel_id}_{permission}
        _, _, tel_id_str, perm_str = callback.data.split("_")
        user_tel_id = int(tel_id_str)
        permission = int(perm_str)
    except Exception:
        await callback.answer("❌ خطای پردازش داده", show_alert=True)
        return

    user = await get_user(user_tel_id)
    if not user:
        await callback.answer("کاربر یافت نشد!", show_alert=True)
        return

    user_id = user['id']
    has_perm = await user_has_permission(user_id, permission)

    if has_perm:
        await remove_permission(user_id, permission)
        await callback.answer("❌ دسترسی حذف شد")
    else:
        await add_permission(user_id, permission)
        await callback.answer("✅ دسترسی اضافه شد")

    # === بروزرسانی مستقیم پیام فعلی (بهترین روش) ===
    await refresh_permissions_panel(callback, user_tel_id)


async def refresh_permissions_panel(callback: CallbackQuery, user_tel_id: int):
    """بروزرسانی مستقیم پنل دسترسی‌ها"""
    user = await get_user(user_tel_id)
    if not user:
        return

    user_id = user['id']
    has_set_order = await user_has_permission(user_id, 0)
    has_accept_order = await user_has_permission(user_id, 1)

    status_dict = {
        0: "⏳ (در انتظار تأیید)",
        1: "✅ (تأیید شده)",
        2: "❌ (رد شده)",
        3: "🚫 (مسدود شده)",
        4: "🚨 (خروج اضطراری)"
    }
    status_text = status_dict.get(
        user.get('status'), f"نامشخص ({user.get('status')})")

    user_link = f'<a href="tg://user?id={user["tel_id"]}">{user['name']}</a>'

    text = f"""🔑 <b>مدیریت دسترسی‌های کاربر</b>

    👤 نام: <b>{user_link}</b>
    🆔 آیدی: <code>{user['tel_id']}</code>
    وضعیت: {status_text}

    🔸 دسترسی ثبت سفارش را {'✅ دارد' if has_set_order else '❌ ندارد'}
    🔸 دسترسی قبول کردن سفارش را {'✅ دارد' if has_accept_order else '❌ ندارد'}
    """

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_permissions_management_keyboard(
            user_tel_id, has_set_order, has_accept_order, user.get('status'),
        )
    )


@admin_router.message(F.text == "📊 گزارش معاملات ده روز گذشته")
async def send_today_report(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("شما ادمین نیستید!", show_alert=True)
        return

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
            caption=f"📊 گزارش معاملات\n",
            parse_mode="HTML"
        )

        # حذف فایل بعد از ارسال (برای جلوگیری از پر شدن حافظه)
        os.remove(pdf_path)

    except Exception as e:
        await message.answer("❌ خطا در تولید گزارش. لطفا مجددا تلاش کنید.")
        print(f"Report error: {e}")


# ======================== منوی تنظیمات ========================
@admin_router.message(F.text == "⚙️ تنظیمات")
async def settings_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "⚙️ به منوی تنظیمات خوش آمدید:",
        reply_markup=get_settings_menu()
    )


@admin_router.message(F.text == "➕ افزودن تعطیلی")
async def add_holiday_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "📝 لطفاً تاریخ تعطیلی را به فرمت زیر وارد کنید:\n\n"
        "مثال: <code>14050304</code>\n"
        "(سال(4رقم)+ماه(2رقم)+روز(2رقم) به صورت شمسی)\n"
        "(❌ 140535)\n"
        "(❌ 14050305)\n",
        parse_mode="HTML"
    )
    await state.set_state(AdminStates.aiting_for_holiday_date)


@admin_router.message(AdminStates.aiting_for_holiday_date)
async def add_holiday_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    date = message.text.strip()
    date = fa_to_en_digits(date)
    if len(date) != 8 or not date.isdigit():
        await message.answer("❌ فرمت اشتباه! باید ۸ رقم باشد مثل")
        return

    await add_config("تعطیلی", date)
    await message.answer(f"✅ تعطیلی با تاریخ {date} با موفقیت اضافه شد.")
    await state.clear()


@admin_router.message(F.text == "📅 تعطیلی‌ها")
async def list_holidays(message: Message):
    if not is_admin(message.from_user.id):
        return

    holidays = await get_config_by_name("تعطیلی")

    if not holidays:
        await message.answer("📭 هنوز هیچ تعطیلی ثبت نشده است.")
        return

    await message.answer("📅 **تعطیلی‌های ثبت شده:**")

    for holiday in holidays:
        await message.answer(
            f"📅 تاریخ تعطیلی: <b>{holiday['value']}</b>",
            parse_mode="HTML",
            reply_markup=get_delete_holiday_keyboard(holiday['id'])
        )


@admin_router.callback_query(F.data.startswith("del_holiday_"))
async def delete_holiday(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    try:
        config_id = int(callback.data.split("_")[2])

        success = await delete_config_by_id(config_id)

        if success:
            await callback.answer("✅ تعطیلی با موفقیت حذف شد", show_alert=True)
            await callback.message.delete()   # حذف پیام حاوی آن تعطیلی
        else:
            await callback.answer("❌ خطا در حذف تعطیلی", show_alert=True)

    except Exception as e:
        await callback.answer("❌ خطایی رخ داد", show_alert=True)
        print(f"Delete holiday error: {e}")

# ======================== ساعت کاری ========================


@admin_router.message(F.text == "🕒 ساعت کاری")
async def working_hours(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # نمایش ساعت کاری فعلی (اگر وجود داشت)
    current = await get_config_by_name("ساعت-کاری")

    if current:
        current_time = current[0]['value']
        text = f"🕒 ساعت کاری فعلی:\n<code>{current_time}</code>\n\n"
    else:
        text = "🕒 هنوز ساعت کاری تنظیم نشده است.\n\n"

    text += (
        "لطفاً ساعت کاری جدید را به فرمت زیر وارد کنید:\n\n"
        "مثال: \n<code>0930-1500</code>\n"
        "• ۴ رقم اول: ساعت شروع\n"
        "• ۴ رقم دوم: ساعت پایان"
    )

    await message.answer(text, parse_mode="HTML")
    await state.set_state(AdminStates.waiting_for_working_hours)


@admin_router.message(AdminStates.waiting_for_working_hours)
async def process_working_hours(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()

    # اعتبارسنجی فرمت
    if '-' not in text or len(text.split('-')) != 2:
        await message.answer("❌ فرمت اشتباه! باید به شکل `0930-1500` باشد.")
        return

    start, end = text.split('-')

    if len(start) != 4 or len(end) != 4 or not (start.isdigit() and end.isdigit()):
        await message.answer("❌ ساعت‌ها باید دقیقاً ۴ رقم باشند (مثال: 0930-1500)")
        return

    start_hour = int(start[:2])
    start_min = int(start[2:])
    end_hour = int(end[:2])
    end_min = int(end[2:])

    if not (0 <= start_hour <= 23 and 0 <= start_min <= 59 and
            0 <= end_hour <= 23 and 0 <= end_min <= 59):
        await message.answer("❌ ساعت یا دقیقه وارد شده معتبر نیست.")
        return

    if (start_hour > end_hour) or (start_hour == end_hour and start_min >= end_min):
        await message.answer("❌ ساعت شروع باید قبل از ساعت پایان باشد.")
        return

    # ذخیره در دیتابیس
    await set_working_hours(text)

    await message.answer(
        f"✅ ساعت کاری با موفقیت بروزرسانی شد:\n\n"
        f"🕒 <code>{text}</code>",
        parse_mode="HTML"
    )
    await state.clear()
