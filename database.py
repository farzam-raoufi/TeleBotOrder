import aiosqlite
import logging
from datetime import datetime

DB_NAME = "TeleBotOrder.db"

async def init_db():
    """ساخت جدول‌های دیتابیس با ساختار مورد نظر شما"""
    async with aiosqlite.connect(DB_NAME) as db:
        
        # جدول کاربران
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tel_id INTEGER UNIQUE NOT NULL,           -- آیدی تلگرام (user_id)
                name TEXT,                                -- نام کاربر در تلگرام
                status INTEGER DEFAULT 0,                 -- 0=pending, 1=approved, 2=rejected, 3=banned, 4 emergency exit
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # جدول نقش و دسترسی‌ها
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                permission INTEGER NOT NULL,              -- عدد دسترسی‌ها
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """)

        await db.commit()
        logging.info("✅ دیتابیس و جدول‌ها با موفقیت ساخته شدند")


# تابع کمکی برای ثبت یا گرفتن کاربر
async def get_or_create_user(tel_id: int, name: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # چک کنیم کاربر وجود دارد یا نه
        async with db.execute("SELECT * FROM users WHERE tel_id = ?", (tel_id,)) as cursor:
            user = await cursor.fetchone()
            
            if not user:
                # کاربر جدید
                await db.execute(
                    "INSERT INTO users (tel_id, name) VALUES (?, ?)", 
                    (tel_id, name)
                )
                await db.commit()
                
                # گرفتن id کاربر تازه ساخته شده
                async with db.execute("SELECT id FROM users WHERE tel_id = ?", (tel_id,)) as c:
                    user_id = (await c.fetchone())[0]
                
                # دادن دسترسی اولیه (مثلاً 0 = دسترسی معمولی)
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
        
        # دریافت کاربر تازه ایجاد شده
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


async def get_pending_users():
    """دریافت لیست کاربران در انتظار تأیید"""
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT id, tel_id, name, created_at 
            FROM users 
            WHERE status = 0 
            ORDER BY created_at DESC
        """) as cursor:
            rows = await cursor.fetchall()
            return [dict(zip([c[0] for c in cursor.description], row)) for row in rows]