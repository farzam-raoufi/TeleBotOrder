import datetime
import jdatetime
import logging
import os
import zoneinfo
from jinja2 import Template
from weasyprint import HTML

from database import get_user_today_trades
from utils.today_iran_timestamps import get_today_iran_timestamps

# ================ کاهش شدید لاگ‌ها ================
logging.getLogger('weasyprint').setLevel(logging.ERROR)
logging.getLogger('fontTools').setLevel(logging.ERROR)
logging.getLogger('fontTools.subset').setLevel(logging.ERROR)
logging.getLogger('fontTools.ttLib').setLevel(logging.ERROR)

# خاموش کردن لاگ‌های خاص subsetting
for logger_name in ['fontTools.subset.timer', 'fontTools.subset']:
    if logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(logging.CRITICAL)


def format_price(value):
    try:
        return f"{int(value):,}"
    except:
        return str(value)


# date-type
def data_to_order(date: int, type: int):
    orders = {
        "1-1": "امروزی",
        "1-2": "نقدی حاضر",
        "2-1": "با حواله",
        "2-2": "بی حواله فردا",
    }
    return orders.get(f"{date}-{type}")


def get_today_report_html(trades, username: str, report_date: str, report_datetime: str):
    font_path = os.path.abspath("fonts/Vazirmatn.ttf")

    template_str = """
<!DOCTYPE html>
    <html lang="fa" dir="rtl">
    <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>گزارش معاملات</title>
    <style>
    * {
        box-sizing: border-box;
        font-family: Tahoma, sans-serif;
    }
    body {
        margin: 0;
        padding: 5px;
        background: #f5f5f5;
        color: #222;
    }
    .report-container {
        width: 100%;
        max-width: 100٪;
        margin: 0 auto;
        background: #fff;
        padding: 5px;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.08);
    }
    .header {
        margin-bottom: 25px;
        line-height: 2;
    }
    .header h1 {
        margin: 0;
        font-size: 16px;
        color: #111827;
    }
    .header-info {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        margin-top: 10px;
        font-size: 14px;
        color: #444;
    }
    .table-wrapper {
        width: 100%;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 14px;

        
    }
    thead {
        background: #1f2937;
        color: white;
    }
    th, td {
        padding: 6px 4px;
        border: 1px solid #d1d5db;
        text-align: center;
        font-size: 14px;
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    tbody tr:nth-child(even) {
        background: #f9fafb;
    }
    .buy {
        color: #114635;
        font-weight: bold;
    }
    .sell {
        color: #7c1515;
        font-weight: bold;
    }
    .footer {
        margin-top: 20px;
        text-align: left;
        color: #666;
        font-size: 13px;
    }
    @media print {
        body {
            background: white;
            padding: 0;
        }
        .report-container {
            box-shadow: none;
            border-radius: 0;
        }
    }
    </style>
    </head>
    <body>
    <div class="report-container">
        <div class="header">
            <h1>لیست معاملات برای تاریخ {{ report_date }}</h1>
            <div class="header-info">
                <div><strong>گزارش برای:</strong> {{ username }}</div>
                <div><strong>تاریخ گزارش:</strong> {{ report_datetime }}</div>
                <div><strong> لفظ بدید - کتاب </strong></div>
            </div>
        </div>
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th>ردیف</th>
                        <th>شماره</th>
                        <th>نوع</th>
                        <th>حجم</th>
                        <th>حالت</th>
                        <th>فرم</th>
                        <th>توضیحات</th>
                        <th>فی (تومان)</th>
                        <th>تاریخ</th>
                    </tr>
                </thead>
                <tbody>
                    {% for i, t in trades %}
                    <tr>
                        <td>{{ i }}</td>
                        <td>{{ t.id }}</td>
                        <td class="{{ 'buy' if t.order_type == 'خرید' else 'sell' }}">{{ t.order_type }}</td>
                        <td>{{ t.accepted_volume }}</td>
                        <td>عادی</td>
                        <td>{{ t.payAndDate }}</td>
                        <td>{{ t.description or '-' }}</td>
                        <td>{{ t.formatted_price }}</td>
                        <td>{{ t.trade_time }}</td>
                    </tr>
                    {% endfor %}
                    {% if not trades %}
                    <tr>
                        <td colspan="10" style="padding: 40px; color: #666;">
                            هیچ معامله‌ای در امروز ثبت نشده است.
                        </td>
                    </tr>
                    {% endif %}
                </tbody>
            </table>
         </div>
        <div class="footer">1</div>
    </div>
    </body>
    </html>
    """
    template = Template(template_str)
    return template.render(
        trades=enumerate(trades, 1),
        username=username,
        report_date=report_date,
        report_datetime=report_datetime,
        font_path=font_path.replace("\\", "/")  # برای ویندوز/لینوکس
    )


async def generate_today_report(user_id: int, username: str = None):
    tehran_tz = zoneinfo.ZoneInfo("Asia/Tehran")
    timestamp = datetime.datetime.now(datetime.timezone.utc).timestamp()
    tehran_jalali = jdatetime.datetime.fromtimestamp(
        timestamp=timestamp, tz=tehran_tz)

    report_date = tehran_jalali.strftime("%Y/%m/%d")
    report_datetime = tehran_jalali.strftime("%Y/%m/%d %H:%M:%S")

    timestamps = get_today_iran_timestamps()
    raw_trades = await get_user_today_trades(user_id, timestamps[0], timestamps[1])

    trades = []
    for trade in raw_trades:
        trade_copy = dict(trade)
        trade_copy['formatted_price'] = format_price(trade.get('price', 0))
        trade_copy['payAndDate'] = data_to_order(trade.get('date_type'), trade.get('payment_type'))
        trade_copy['trade_time'] = jdatetime.datetime.fromtimestamp(timestamp=trade.get(
            'accepted_at', ''), tz=tehran_tz).strftime("%H:%M:%S %Y/%m/%d ")
        trades.append(trade_copy)

    html_content = get_today_report_html(
        trades, username or str(user_id), report_date, report_datetime)

    pdf_path = f"reports/report_{str(timestamp)[-4:]}_{tehran_jalali.strftime('%Y%m%d_%H%M%S')}.pdf"
    os.makedirs("reports", exist_ok=True)

    HTML(string=html_content).write_pdf(pdf_path)
    return pdf_path
