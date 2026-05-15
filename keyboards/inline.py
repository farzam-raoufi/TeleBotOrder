from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_start_keyboard():
    keyboard = [
        [InlineKeyboardButton(text="📋 درخواست عضویت",
                              callback_data="request_membership")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = [
        [InlineKeyboardButton(text="👥 لیست همه کاربران",
                              callback_data="show_all_users")]
        [InlineKeyboardButton(text="✅ لیست کاربران تایید شده",
                              callback_data="show_all_users")]
        [InlineKeyboardButton(text="⏳ کاربران در انتظار تأیید",
                              callback_data="show_pending")],
        [InlineKeyboardButton(text="🚨 کاربران خروج اضطراری",
                              callback_data="show_emergency_exit")],
        [InlineKeyboardButton(text="🚫 کاربران مسدود شده",
                              callback_data="show_banned")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_approval_keyboard(tel_id: int):
    keyboard = [
        [
            InlineKeyboardButton(
                text="✅ تأیید", callback_data=f"approve_{tel_id}"),
            InlineKeyboardButton(
                text="❌ رد کردن", callback_data=f"reject_{tel_id}"),
            InlineKeyboardButton(text="⛔ مسدود کردن",
                                 callback_data=f"banned_{tel_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_start_user_management_keyboard(tel_id: int):
    keyboard = [
        [InlineKeyboardButton(
            text="⚙️ مدیریت کاربر",
            callback_data=f"manage_user_{tel_id}"
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_user_management_keyboard(tel_id: int):
    # کیبورد مدیریت
    keyboard = [
        [
            InlineKeyboardButton(text="📊 تغییر ظرفیت",
                                 callback_data=f"set_capacity_{tel_id}"),
            InlineKeyboardButton(text="🔑 مدیریت دسترسی‌ها",
                                 callback_data=f"manage_perms_{tel_id}")
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_permissions_management_keyboard(tel_id: int, has_set_order: bool, has_accept_order: bool, user_status: int = 1):

    user_status_button = []
    # active user 0=pending, 1=approved, 2=rejected, 3=banned, 4 emergency exit
    match user_status:
        case 1:
            user_status_button = [
                InlineKeyboardButton(
                    text="⛔ مسدود کردن",
                    callback_data=f"banned_{tel_id}"
                )
            ]
        case 2 | 3 | 4:  # rejected or banned user
            user_status_button = [
                InlineKeyboardButton(
                    text="✅ فعال سازی کاربر",
                    callback_data=f"approve_{tel_id}"
                )
            ]
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{'❌ حذف' if has_set_order else '✅ دادن'} دسترسی ثبت سفارش",
                callback_data=f"toggle_perm_{tel_id}_0"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{'❌ حذف' if has_accept_order else '✅ دادن'} دسترسی تأیید سفارش",
                callback_data=f"toggle_perm_{tel_id}_1"
            )
        ],
        user_status_button,
        [
            InlineKeyboardButton(
                text="🔙 بازگشت به مدیریت کاربر",
                callback_data=f"manage_user_{tel_id}"
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
