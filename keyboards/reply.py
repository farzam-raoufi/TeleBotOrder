from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_user_main_menu():
    """منوی اصلی کاربران معمولی"""
    keyboard = [
        [KeyboardButton(text="📋 ثبت درخواست معامله")],
        [KeyboardButton(text="📊 گزارش معاملات امروز")],
        [KeyboardButton(text="ℹ️ راهنما")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_order_cancel_menu(last_action: str = None):

    keyboard = []
    
    if last_action:
        keyboard.append([KeyboardButton(text=last_action)])
    
    keyboard.append([KeyboardButton(text="❌ نشد")])
    keyboard.append([KeyboardButton(text="🔙 بازگشت به منو")])
    
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)




def get_admin_main_menu():
    """منوی اصلی ادمین"""
    keyboard = [
        [KeyboardButton(text="لیست کاربران فعال ✅")],
        [KeyboardButton(text="لیست کاربران در انتظار تأیید ⏳")],
        [KeyboardButton(text="لیست کاربران خروج اضطراری 🚨")],
        [KeyboardButton(text="لیست کاربران مسدود شده 🚫")],
        [KeyboardButton(text="لیست کاربران (همه کاربران) 👥")],

        [KeyboardButton(text="📊 گزارش معاملات ده روز گذشته")],
        [KeyboardButton(text="⚙️ تنظیمات")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def remove_keyboard():
    """حذف کیبورد"""
    return ReplyKeyboardMarkup(keyboard=[], resize_keyboard=True)
