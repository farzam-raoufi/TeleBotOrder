import aiosqlite
import logging
from utils.today_iran_timestamps import get_today_iran_timestamps

DB_NAME = "TeleBotOrder.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tel_id INTEGER UNIQUE NOT NULL,           -- آیدی تلگرام (user_id)
                name TEXT,                                -- نام کاربر در تلگرام
                capacity INTEGER DEFAULT 10,               -- محدودیت وزن معامله شده در روز
                status INTEGER DEFAULT 0,                 -- 0=pending, 1=approved, 2=rejected, 3=banned, 4 emergency exit
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Roles and permissions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission INTEGER NOT NULL,              -- 0= set order, 1= accept order,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        # Orders / Offers table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                
                -- اطلاعات لفظ دهنده
                offerer_id INTEGER NOT NULL,           -- آیدی کاربر لفظ دهنده (از جدول users)
                offerer_tel_id INTEGER NOT NULL,       -- tel_id برای راحتی
                
                -- وضعیت و زمان‌ها
                created_at INTEGER,                         -- زمان ثبت لفظ
                expires_at INTEGER,                         -- زمان انقضا (۶۰ ثانیه بعد)
                trade_date TEXT NOT NULL,                    -- تاریخ معامله (جلالی)
                
                -- جزئیات معامله
                price INTEGER NOT NULL,                      -- قیمت
                order_type TEXT NOT NULL,                    -- خرید - فروش
                total_volume INTEGER NOT NULL,                  -- حجم به کیلو
                remaining_volume INTEGER NOT NULL,                           -- حجم به کیلو
                payment_type TEXT NOT NULL,                  --  1 نقدی 2 - غیر نقدی
                date_type TEXT NOT NULL,                    -- 2 روز 1 - اولین روز کاری بعد
                
                -- توضیحات اضافی (اختیاری)
                description TEXT,                            -- متن بعد از ":"
                -- متن پیام
                group_text TEXT,                            -- متن ارسال شده ر گروه
                
                -- وضعیت معامله
                status TEXT DEFAULT 'active',                -- active / fully_accepted / cancelled / expired
                
                -- پیام در گروه (برای مدیریت دکمه‌ها)
                group_message_id INTEGER,                    -- message_id در گروه
                group_chat_id INTEGER,                       -- chat_id گروه
                
                FOREIGN KEY (offerer_id) REFERENCES users(id)
            );
        """)

        # Order acceptances
        await db.execute("""
            CREATE TABLE IF NOT EXISTS order_acceptances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                order_id INTEGER NOT NULL,
                offerer_id INTEGER NOT NULL,
                offerer_tel_id INTEGER NOT NULL,

                acceptor_id INTEGER NOT NULL,
                acceptor_tel_id INTEGER NOT NULL,

                accepted_volume INTEGER NOT NULL,
                accepted_at INTEGER,

                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (offerer_id) REFERENCES users(id),
                FOREIGN KEY (acceptor_id) REFERENCES users(id)
            );
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()
        logging.info("✅ data base and tables created")

# Helper function to get or register user


async def get_or_create_user(tel_id: int, name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # Check if user exists
        async with db.execute("SELECT * FROM users WHERE tel_id = ?", (tel_id,)) as cursor:
            user = await cursor.fetchone()

            if not user:
                # New user
                await db.execute(
                    "INSERT INTO users (tel_id, name) VALUES (?, ?)",
                    (tel_id, name)
                )
                await db.commit()
                # Get the ID of the newly created user
                async with db.execute("SELECT id FROM users WHERE tel_id = ?", (tel_id,)) as c:
                    user_id = (await c.fetchone())[0]
                # Assign initial access (e.g., 0 = normal access)
                await db.execute(
                    "INSERT INTO roles (user_id, permission) VALUES (?, ?)",
                    (user_id, 0)
                )
                await db.commit()

                return {"id": user_id, "tel_id": tel_id, "name": name, "status": 0}

            return dict(zip([c[0] for c in cursor.description], user))


async def get_user(tel_id: int):
    """دریافت اطلاعات کاربر"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM users WHERE tel_id = ?", (tel_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))
            return None


async def create_user(tel_id: int, name: str):
    """ایجاد کاربر جدید با وضعیت pending"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO users (tel_id, name, status) VALUES (?, ?, 0)",
            (tel_id, name)
        )
        await db.commit()

        # Get the newly created user
        return await get_user(tel_id)


async def get_user_permissions(user_id: int):
    """دریافت دسترسی‌های کاربر"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT permission FROM roles WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def set_user_status(tel_id: int, new_status: int):
    """تغییر وضعیت کاربر (0=pending, 1=approved, 2=rejected, 3=banned)"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET status = ? WHERE tel_id = ?", (new_status, tel_id))
        await db.commit()


async def get_users_by_status(*statuses: int):
    """دریافت لیست کاربران"""

    query = """
        SELECT id, tel_id, name, created_at, status
        FROM users
    """

    params = ()

    if statuses:
        placeholders = ",".join("?" for _ in statuses)

        query += f"""
            WHERE status IN ({placeholders})
        """

        params = statuses

    query += " ORDER BY created_at DESC"

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            return [
                dict(zip([c[0] for c in cursor.description], row))
                for row in rows
            ]


async def is_banned(tel_id: int) -> dict | None:
    user = await get_user(tel_id)

    if not user:
        return False

    if user["status"] in [3, 4]:   # بلاک شده
        return True
    return False


async def update_user_capacity(tel_id: int, new_capacity: int) -> bool:
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "UPDATE users SET capacity = ? WHERE tel_id = ?",
                (new_capacity, tel_id)
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"Error updating capacity: {e}")
        return False


# ======================== مدیریت دسترسی‌ها ========================

async def user_has_permission(user_id: int, permission: int) -> bool:
    """چک کند کاربر این دسترسی را دارد یا نه"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT 1 FROM roles WHERE user_id = ? AND permission = ?",
            (user_id, permission)
        ) as cursor:
            return await cursor.fetchone() is not None


async def add_permission(user_id: int, permission: int):
    """اضافه کردن دسترسی"""
    async with aiosqlite.connect(DB_NAME) as db:
        # برای جلوگیری از تکراری شدن
        await db.execute(
            "INSERT OR IGNORE INTO roles (user_id, permission) VALUES (?, ?)",
            (user_id, permission)
        )
        await db.commit()


async def remove_permission(user_id: int, permission: int):
    """حذف دسترسی"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM roles WHERE user_id = ? AND permission = ?",
            (user_id, permission)
        )
        await db.commit()


# ======================== Orders ========================

async def create_order( 
    offerer_id: int,
    offerer_tel_id: int,
    price: int,
    order_type: str,
    total_volume: float,
    payment_type: str,
    date_type: str,
    trade_date: str,
    created_at: str,
    status: str,
    description: str = None,
    group_text: str = None,
    group_chat_id: int = None,
    group_message_id: int = None
) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        expires_at = created_at + 60

        await db.execute("""
            INSERT INTO orders (
                offerer_id,
                offerer_tel_id,
                price,
                order_type,
                total_volume,
                remaining_volume,
                payment_type,
                date_type,
                trade_date,
                description,
                expires_at,
                group_chat_id,
                group_message_id,
                group_text,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            offerer_id,
            offerer_tel_id,
            price,
            order_type,
            total_volume,
            total_volume,  # remaining_volume
            payment_type,
            date_type,
            trade_date,
            description,
            expires_at,
            group_chat_id,
            group_message_id,
            group_text,
            created_at,
            status
        ))
        await db.commit()

        async with db.execute("SELECT last_insert_rowid()") as cursor:
            row = await cursor.fetchone()
            return row[0]


async def get_order(order_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))
            return None


async def cancel_last_user_order(offerer_id: int):
    canceled_orders = []

    async with aiosqlite.connect(DB_NAME) as db:
        # اول همه سفارشات فعال کاربر را می‌گیریم
        async with db.execute("""
            SELECT * FROM orders 
            WHERE offerer_id = ? 
              AND status = 'active'
            ORDER BY created_at DESC
        """, (offerer_id,)) as cursor:

            rows = await cursor.fetchall()
            if not rows:
                return []  # هیچ سفارشی برای کنسل کردن وجود ندارد

            columns = [col[0] for col in cursor.description]

            # تبدیل رکوردها به دیکشنری
            for row in rows:
                order_dict = dict(zip(columns, row))
                canceled_orders.append(order_dict)

        await db.execute(
            "UPDATE orders SET status = 'cancelled' WHERE offerer_id = ? AND status = 'active'",
            (offerer_id,)
        )

        await db.commit()

    return canceled_orders


async def get_last_order():
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, offerer_id, price, total_volume, order_type, 
                status, created_at, expires_at
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT 1
        """) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))
            return None
        
async def get_last_order_by(
    order_type, payment_type, date_type
): 
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT *
            FROM orders
            WHERE order_type = ? AND payment_type = ? AND date_type = ?
            ORDER BY created_at DESC 
            LIMIT 1
        """, (order_type, payment_type, date_type)) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))
            return None


async def cancel_order(order_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        await db.commit()


async def update_order_group_info(order_id: int, group_message_id: int, group_chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET group_message_id = ?, group_chat_id = ? WHERE id = ?", (group_message_id, group_chat_id, order_id))
        await db.commit()


async def get_expired_orders(timestamp):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, group_chat_id, group_message_id, group_text 
            FROM orders 
            WHERE status = 'active' 
              AND expires_at IS NOT NULL 
              AND expires_at < ? 
        """, (timestamp,)) as cursor:

            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]


async def mark_order_as_expired(order_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE orders SET status = 'expired' WHERE id = ?",
            (order_id,)
        )
        await db.commit()


# ======================== Orders acceptance ========================


async def create_order_acceptance(
    order_id: int,
    offerer_id: int,
    offerer_tel_id: int,
    acceptor_id: int,
    acceptor_tel_id: int,
    volume: int,
    accepted_at: int
):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("BEGIN"):
            # ایجاد رکورد پذیرش
            cursor = await db.execute("""
                INSERT INTO order_acceptances 
                (order_id, offerer_id, offerer_tel_id, acceptor_id, acceptor_tel_id, accepted_volume, accepted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (order_id, offerer_id, offerer_tel_id, acceptor_id, acceptor_tel_id, volume, accepted_at))

            acceptance_id = cursor.lastrowid
            # به‌روزرسانی remaining_volume
            await db.execute("""
                UPDATE orders 
                SET remaining_volume = remaining_volume - ?,
                    status = CASE 
                        WHEN remaining_volume - ? <= 0 THEN 'fully_accepted' 
                        ELSE status 
                    END
                WHERE id = ?
            """, (volume, volume, order_id))

            await db.commit()

            return acceptance_id

# ======================== user traded volume ========================


async def get_user_today_volume(user_id: int):

    toda = get_today_iran_timestamps()

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT COALESCE(SUM(accepted_volume), 0) as today_volume
            FROM order_acceptances 
            WHERE accepted_at BETWEEN ? AND ?
            AND (offerer_id = ? OR acceptor_id = ?)
        """, (toda[0], toda[1], user_id, user_id)) as cursor:

            result = await cursor.fetchone()
            return result[0] if result else 0


# ======================== user traded report ========================

async def get_user_today_trades(user_id: int, start_ts: int, end_ts: int):
    """دریافت معاملات امروز کاربر (هم به عنوان عرضه‌کننده هم پذیرنده)"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        async with db.execute("""
            SELECT 
                oa.id,
                oa.order_id,
                o.order_type,           -- خرید یا فروش
                o.group_text,
                o.price,
                oa.accepted_volume,
                oa.accepted_at,
                o.description,
                oa.offerer_id,
                oa.acceptor_id
            FROM order_acceptances oa
            JOIN orders o ON oa.order_id = o.id
            WHERE oa.accepted_at BETWEEN ? AND ?
              AND (oa.offerer_id = ? OR oa.acceptor_id = ?)
            ORDER BY oa.accepted_at DESC
        """, (start_ts, end_ts, user_id, user_id)) as cursor:

            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]

# ======================== admin traded report ========================


async def get_for_admin_trades(start_ts: int, end_ts: int):
    """دریافت معاملات کاربران"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        async with db.execute("""
            SELECT
                oa.id AS acceptance_id,
                oa.order_id,
                o.order_type,           -- خرید یا فروش
                o.group_text,
                o.price,
                oa.accepted_volume,
                oa.accepted_at,
                o.description,
                oa.offerer_id,
                oa.acceptor_id,
                
                -- اطلاعات لفظ دهنده (Offerer)
                offerer.name AS offerer_name,
                
                -- اطلاعات لفظ گیرنده (Acceptor)
                acceptor.name AS acceptor_name
                
            FROM order_acceptances oa
            JOIN orders o ON oa.order_id = o.id
            
            JOIN users offerer ON oa.offerer_id = offerer.id
            JOIN users acceptor ON oa.acceptor_id = acceptor.id
            
            WHERE oa.accepted_at BETWEEN ? AND ?
            ORDER BY oa.accepted_at DESC
            """, (start_ts, end_ts)) as cursor:

            rows = await cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in rows]
# ======================== Config Functions ========================


async def add_config(name: str, value: str):
    """اضافه کردن تنظیم جدید"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR IGNORE INTO config (name, value) VALUES (?, ?)",
            (name, value)
        )
        await db.commit()


async def get_config_by_name(name: str):
    """دریافت همه رکوردهای یک نام"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, value FROM config WHERE name = ? ORDER BY value",
            (name,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [{"id": row[0], "value": row[1]} for row in rows]


async def delete_config_by_id(config_id: int):
    """حذف رکورد تنظیم"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM config WHERE id = ?", (config_id,))
        await db.commit()
        return True


async def is_holiday(jalali_date: str) -> bool:
    """چک کردن اینکه آیا تاریخ داده شده تعطیلی است"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM config WHERE name = 'تعطیلی' AND value = ?",
            (jalali_date,)
        ) as cursor:
            result = await cursor.fetchone()
            return result[0] > 0


async def set_working_hours(value: str):
    """ذخیره یا بروزرسانی ساعت کاری"""
    async with aiosqlite.connect(DB_NAME) as db:
        # اول چک کنیم آیا رکورد وجود دارد
        async with db.execute(
            "SELECT id FROM config WHERE name = 'ساعت-کاری'"
        ) as cursor:
            row = await cursor.fetchone()

        if row:  # رکورد وجود دارد → UPDATE
            await db.execute(
                "UPDATE config SET value = ? WHERE name = 'ساعت-کاری'",
                (value,)
            )
        else:    # رکورد وجود ندارد → INSERT
            await db.execute(
                "INSERT INTO config (name, value) VALUES ('ساعت-کاری', ?)",
                (value,)
            )

        await db.commit()
        return True
