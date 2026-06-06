import datetime
import zoneinfo


def get_today_iran_timestamps():
    tehran_tz = zoneinfo.ZoneInfo("Asia/Tehran")
    now = datetime.datetime.now(tehran_tz)

    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)

    return (
        int(start.astimezone(datetime.timezone.utc).timestamp()),
        int(end.astimezone(datetime.timezone.utc).timestamp())
    )
