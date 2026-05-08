from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    """کیبورد شروع برای کاربران"""
    keyboard = [
        [InlineKeyboardButton(text="📋 درخواست عضویت", callback_data="request_membership")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_approval_keyboard(user_id: int):
    """کیبورد تأیید ادمین"""
    keyboard = [
        [
            InlineKeyboardButton(text="✅ تأیید", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ رد کردن", callback_data=f"reject_{user_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)