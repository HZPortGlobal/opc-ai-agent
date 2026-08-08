#!/usr/bin/env python3
"""
数据存储层（MVP 版）。
用 SQLite 存 feedback + waitlist。存储被抽象成这几函数，
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


def add_wait(email, source=""):
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO waitlist(email,source,created_at) VALUES(?,?,?)",
            (email, source, time.time()),
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False  # 邮箱已存在


def stats():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM waitlist")
    wl = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM feedback")
    fb = c.fetchone()[0]
    c.execute("SELECT scenario, COUNT(*) FROM feedback GROUP BY scenario")
    by_s = dict(c.fetchall())
    c.execute("SELECT wtp, COUNT(*) FROM feedback WHERE wtp>0 GROUP BY wtp")
    wtp = c.fetchall()
    c.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating")
    by_rating = dict(c.fetchall())
    conn.close()
    return {
        "waitlist": wl,
        "feedback": fb,
        "by_scenario": by_s,
        "wtp": wtp,
        "by_rating": by_rating,
    }
