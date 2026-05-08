from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="📋 درخواست عضویت", callback_data="request_membership")]
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