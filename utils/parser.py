# utils/parser.py
import re
from typing import Dict, Optional, Tuple

# تبدیل اعداد فارسی به انگلیسی


def fa_to_en_digits(text):
    persian_digits = "۰۱۲۳۴۵۶۷۸۹"
    english_digits = "0123456789"

    translation_table = str.maketrans(
        persian_digits,
        english_digits
    )

    return text.translate(translation_table)


# date-type
def data_to_order(date: int, type: int):
    orders = {
        "1-1": "امروزی",
        "1-2": "نقدی حاضر",
        "2-1": "با حواله",
        "2-2": "بی حواله فردا",
    }
    return orders.get(f"{date}-{type}")


def parse_order_text(text: str, force_tomorrow: bool) -> Optional[Dict]:
    """
    پارس کردن لفظ کاربر
    """
    text = text.strip().replace(" ", "").replace("،", "").replace("ً", "")
    text = fa_to_en_digits(text)

    price = re.match(r'^(\d+)', text)

    if price:
        number = price.group(1)
        # فقط 3 یا 5 رقم مجاز
        if len(number) in [3, 5]:
            price = number
            text = text[len(number):]
            letters = list(text)
        else:
            return None
    else:
        return None

    volume = 1
    trade_date = 1  # "امروز"
    payment_type = 1  # "غیر نقدی"
    description = None

    for index, char in enumerate(letters):
        if index == 0:
            if char == "خ":
                order_type = "خرید"
            elif char == "ف":
                order_type = "فروش"
            else:
                return None

        if index == 1:
            if char == "ف":
                trade_date = 2  # "فردا"
            else:
                trade_date = 1  # "امروز"
            if char == "ن":
                payment_type = 2  # "نقدی"
            else:
                payment_type = 1  # "غیر نقدی"

        if index == 2:
            if char.isdigit():
                volume = int(char)
            elif char == "ن":
                payment_type = 2  # "نقدی"
            else:
                payment_type = 1  # "غیر نقدی"

        if char.isdigit():
            volume = int(char)

        if len(letters) > (index + 2):
            if letters[index + 1] == ":":
                description = text[index + 2:]

    if (force_tomorrow):
        trade_date = 2

    return {
        "price": price,
        "order_type": order_type,
        "volume": volume,
        "payment_type": payment_type,
        "trade_date": trade_date,
        "order": data_to_order(trade_date, payment_type),
        "description": description,
    }
