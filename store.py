#!/usr/bin/env python3
"""
数据存储层（MVP 版）。
用 SQLite 存 feedback + waitlist + usage（埋点）。存储被抽象成这几函数，
以后要换 Postgres 只改这个文件，业务代码不动。

注意：Render 免费层文件系统是临时的，重部署会清空本地库。
MVP 阶段够用（验证信号），正式化时把这里换成外部 DB 即可。
"""
import os
import sqlite3
import time

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")


def init():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS feedback(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario TEXT,
            market TEXT,
            rating TEXT,
            comment TEXT,
            wtp INTEGER,
            created_at REAL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS waitlist(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            source TEXT,
            uid TEXT,
            created_at REAL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS usage(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario TEXT,
            market TEXT,
            ok INTEGER,
            uid TEXT,
            created_at REAL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS free_checks(
            ip TEXT,
            day TEXT,
            count INTEGER DEFAULT 0,
            PRIMARY KEY(ip, day)
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS redeem_codes(
            code TEXT PRIMARY KEY,
            plan TEXT DEFAULT 'pro',
            credits INTEGER DEFAULT 9999,
            created_at REAL,
            redeemed_at REAL,
            redeemed_by TEXT
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS members(
            code TEXT PRIMARY KEY,
            plan TEXT,
            credits INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at REAL,
            activated_at REAL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            amount_cny REAL,
            status TEXT,
            code TEXT,
            meta TEXT,
            created_at REAL
        )"""
    )
    conn.commit()
    conn.close()


def add_feedback(scenario, market, rating, comment, wtp):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO feedback(scenario,market,rating,comment,wtp,created_at) VALUES(?,?,?,?,?,?)",
        (scenario, market, rating, comment, wtp, time.time()),
    )
    conn.commit()
    conn.close()


def add_wait(email, source="", uid=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO waitlist(email,source,uid,created_at) VALUES(?,?,?,?)",
            (email, source, uid, time.time()),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False  # 邮箱已存在


def log_usage(scenario, market, ok, uid=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO usage(scenario,market,ok,uid,created_at) VALUES(?,?,?,?,?)",
        (scenario, market, 1 if ok else 0, uid, time.time()),
    )
    conn.commit()
    conn.close()


def get_free_count(ip, day):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT count FROM free_checks WHERE ip=? AND day=?", (ip, day))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0


def inc_free_count(ip, day):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO free_checks(ip,day,count) VALUES(?,?,1) "
        "ON CONFLICT(ip,day) DO UPDATE SET count=count+1",
        (ip, day),
    )
    conn.commit()
    conn.close()


def create_redeem_code(code, plan="pro", credits=9999):
    """预先生成会员码（可批量发售；商户号就绪后由支付回调自动 mint）。"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT OR IGNORE INTO redeem_codes(code,plan,credits,created_at) VALUES(?,?,?,?)",
        (code, plan, credits, time.time()),
    )
    conn.commit()
    conn.close()


def redeem_code(code, uid=""):
    """核销会员码 → 激活 members 记录。返回 {plan,credits} 或 None（无效/已用）。"""
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT code,plan,credits FROM redeem_codes WHERE code=?", (code,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    c.execute(
        "INSERT OR REPLACE INTO members(code,plan,credits,status,created_at,activated_at) "
        "VALUES(?,?,?,?,?,?)",
        (row[0], row[1], row[2], "active", time.time(), time.time()),
    )
    c.execute(
        "UPDATE redeem_codes SET redeemed_at=?, redeemed_by=? WHERE code=?",
        (time.time(), uid, code),
    )
    conn.commit()
    conn.close()
    return {"plan": row[1], "credits": row[2]}


def is_member(code):
    if not code:
        return False
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT status FROM members WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == "active")


def get_member(code):
    if not code:
        return None
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT code,plan,credits,status FROM members WHERE code=?", (code,))
    row = c.fetchone()
    conn.close()
    return {"code": row[0], "plan": row[1], "credits": row[2], "status": row[3]} if row else None


def log_payment(channel, amount_cny, status, code="", meta=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO payments(channel,amount_cny,status,code,meta,created_at) VALUES(?,?,?,?,?,?)",
        (channel, amount_cny, status, code, meta, time.time()),
    )
    conn.commit()
    conn.close()


def stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = time.time()
    week_ago = now - 7 * 86400

    c.execute("SELECT COUNT(*) FROM waitlist")
    wl = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM feedback")
    fb = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM members WHERE status='active'")
    members = c.fetchone()[0]
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    now = time.time()
    week_ago = now - 7 * 86400

    c.execute("SELECT COUNT(*) FROM waitlist")
    wl = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM feedback")
    fb = c.fetchone()[0]

    c.execute("SELECT scenario, COUNT(*) FROM usage GROUP BY scenario")
    by_s = dict(c.fetchall())
    c.execute("SELECT COUNT(*), SUM(ok) FROM usage")
    total, ok_sum = c.fetchone()
    total = total or 0
    ok_sum = ok_sum or 0
    success_rate = round(ok_sum / total * 100, 1) if total else 0.0

    c.execute("SELECT COUNT(DISTINCT uid) FROM usage WHERE uid <> ''")
    users = c.fetchone()[0]
    c.execute("SELECT COUNT(DISTINCT uid) FROM usage WHERE uid <> '' AND created_at >= ?", (week_ago,))
    users_7d = c.fetchone()[0]

    c.execute("SELECT wtp, COUNT(*) FROM feedback WHERE wtp>0 GROUP BY wtp")
    wtp = c.fetchall()
    c.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")
    by_rating = dict(c.fetchall())
    conn.close()
    return {
        "waitlist": wl,
        "feedback": fb,
        "members": members,
        "by_scenario": by_s,
        "gen_total": total,
        "success_rate": success_rate,
        "distinct_users": users,
        "users_7d": users_7d,
        "wtp": wtp,
        "by_rating": by_rating,
    }
