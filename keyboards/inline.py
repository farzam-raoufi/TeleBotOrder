from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="📋 درخواست عضویت", callback_data="request_membership")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = [
        [InlineKeyboardButton(text="📋 کاربران در انتظار تأیید", callback_data="show_pending")],
        [InlineKeyboardButton(text="👥 لیست همه کاربران", callback_data="show_all_users")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_approval_keyboard(tel_id: int):
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تأیید", callback_data=f"approve_{tel_id}"),
            InlineKeyboardButton(text="❌ رد کردن", callback_data=f"reject_{tel_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)