import sqlite3
import random

class Database:
    def __init__(self, path="school_facts.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def init(self):
        cur = self.conn.cursor()

        # --- USERS ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY
        )
        """)

        # --- FACTS ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            image TEXT,
            category TEXT,
            year INTEGER,
            weight INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1
        )
        """)

        # --- VIEWS ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS views (
            telegram_id INTEGER,
            fact_id INTEGER,
            PRIMARY KEY (telegram_id, fact_id)
        )
        """)

        # --- FAVORITES ---
        cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            telegram_id INTEGER,
            fact_id INTEGER,
            PRIMARY KEY (telegram_id, fact_id)
        )
        """)

        self.conn.commit()

        # 🔥 ВАЖНО: проверяем колонки
        self.ensure_columns()

    # --- FIX STRUCTURE ---
    def ensure_columns(self):
        cur = self.conn.cursor()

        # USERS
        cur.execute("PRAGMA table_info(users)")
        cols = [c["name"] for c in cur.fetchall()]
        if "birth_year" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN birth_year INTEGER")

        # FACTS
        cur.execute("PRAGMA table_info(facts)")
        cols = [c["name"] for c in cur.fetchall()]

        if "weight" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN weight INTEGER DEFAULT 1")

        if "is_active" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN is_active INTEGER DEFAULT 1")

        if "year" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN year INTEGER")

        self.conn.commit()

    # --- USERS ---
    def save_user(self, user_id, year):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR REPLACE INTO users (telegram_id, birth_year)
        VALUES (?, ?)
        """, (user_id, year))
        self.conn.commit()

    def get_user(self, user_id):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id=?", (user_id,))
        return cur.fetchone()

    # --- FACTS ---
    def add_fact(self, content, image, category, year, weight=1):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO facts (content, image, category, year, weight)
        VALUES (?, ?, ?, ?, ?)
        """, (content, image, category, year, weight))
        self.conn.commit()
        return cur.lastrowid

    def get_random_fact(self, user_id, year):
        cur = self.conn.cursor()

        cur.execute("""
        SELECT f.* FROM facts f
        LEFT JOIN views v 
        ON f.id = v.fact_id AND v.telegram_id = ?
        WHERE f.year = ? 
        AND f.is_active = 1
        AND v.fact_id IS NULL
        """, (user_id, year))

        rows = cur.fetchall()

        if not rows:
            cur.execute("DELETE FROM views WHERE telegram_id=?", (user_id,))
            self.conn.commit()
            return self.get_random_fact(user_id, year)

        weighted = []
        for row in rows:
            weighted.extend([row] * max(row["weight"], 1))

        return random.choice(weighted)

    def add_view(self, user_id, fact_id):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO views (telegram_id, fact_id)
        VALUES (?, ?)
        """, (user_id, fact_id))
        self.conn.commit()

    # --- FAVORITES ---
    def add_favorite(self, user_id, fact_id):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO favorites (telegram_id, fact_id)
        VALUES (?, ?)
        """, (user_id, fact_id))
        self.conn.commit()

    def remove_favorite(self, user_id, fact_id):
        cur = self.conn.cursor()
        cur.execute("""
        DELETE FROM favorites WHERE telegram_id=? AND fact_id=?
        """, (user_id, fact_id))
        self.conn.commit()

    def get_favorites(self, user_id):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT f.* FROM facts f
        JOIN favorites fav ON f.id = fav.fact_id
        WHERE fav.telegram_id = ?
        """, (user_id,))
        return cur.fetchall()

    def is_favorite(self, user_id, fact_id):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT 1 FROM favorites WHERE telegram_id=? AND fact_id=?
        """, (user_id, fact_id))
        return cur.fetchone() is not None

    # --- STATS ---
    def get_stats(self, user_id):
        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM views WHERE telegram_id=?", (user_id,))
        views = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM favorites WHERE telegram_id=?", (user_id,))
        favs = cur.fetchone()[0]

        return views, favs