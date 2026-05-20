import aiosqlite
import logging
from datetime import datetime, timedelta

DB_NAME = "TeleBotOrder.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:

        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tel_id INTEGER UNIQUE NOT NULL,           -- آیدی تلگرام (user_id)
                name TEXT,                                -- نام کاربر در تلگرام
                capacity INTEGER DEFAULT 3,               -- محدودیت وزن معامله شده در روز
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
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,   -- زمان ثبت لفظ
                expires_at TEXT,                             -- زمان انقضا (۶۰ ثانیه بعد)
                trade_date TEXT NOT NULL,                    -- تاریخ معامله (جلالی)
                
                -- جزئیات معامله
                price INTEGER NOT NULL,                      -- قیمت
                order_type TEXT NOT NULL,                    -- خرید - فروش
                total_volume REAL NOT NULL,                  -- حجم به کیلو
                trade_volume REAL,                           -- حجم به کیلو
                payment_type TEXT NOT NULL,                  --  1 نقدی 2 - غیر نقدی
                
                -- توضیحات اضافی (اختیاری)
                description TEXT,                            -- متن بعد از ":"
                -- متن پیام
                group_text TEXT,                            -- متن ارسال شده ر گروه
                
                -- وضعیت معامله
                status TEXT DEFAULT 'active',                -- active / accepted / cancelled / expired
                acceptor_id INTEGER,                         -- آیدی کسی که قبول کرده
                acceptor_tel_id INTEGER,
                accepted_at TEXT,                            -- زمان پذیرش
                
                -- پیام در گروه (برای مدیریت دکمه‌ها)
                group_message_id INTEGER,                    -- message_id در گروه
                group_chat_id INTEGER,                       -- chat_id گروه
                
                FOREIGN KEY (offerer_id) REFERENCES users(id),
                FOREIGN KEY (acceptor_id) REFERENCES users(id)
            );
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
                payment_type,
                trade_date,
                description,
                expires_at,
                group_chat_id,
                group_message_id,
                group_text,
                created_at,
                status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            offerer_id,
            offerer_tel_id,
            price,
            order_type,
            total_volume,
            payment_type,
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
                status, created_at 
            FROM orders 
            ORDER BY created_at DESC 
            LIMIT 1
        """) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(zip([c[0] for c in cursor.description], row))
            return None


async def accept_order(order_id: int, acceptor_id: int, acceptor_tel_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            UPDATE orders 
            SET status = 'accepted', 
                acceptor_id = ?,
                acceptor_tel_id = ?,
                accepted_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (acceptor_id, acceptor_tel_id, order_id))
        await db.commit()


async def cancel_order(order_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
        await db.commit()


async def update_order_group_info(order_id: int, group_message_id: int, group_chat_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE orders SET group_message_id = ?, group_chat_id = ? WHERE id = ?", (group_message_id, group_chat_id, order_id))
        await db.commit()
