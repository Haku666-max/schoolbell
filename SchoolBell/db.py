import sqlite3
import random


class Database:
    def __init__(self, path="school_facts.db"):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row

    def init(self):
        cur = self.conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id INTEGER PRIMARY KEY
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT,
            image TEXT,
            category TEXT,
            year INTEGER,
            weight INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS views (
            telegram_id INTEGER,
            fact_id INTEGER,
            PRIMARY KEY (telegram_id, fact_id)
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            telegram_id INTEGER,
            fact_id INTEGER,
            PRIMARY KEY (telegram_id, fact_id)
        )
        """)

        self.conn.commit()
        self.ensure_columns()

    def ensure_columns(self):
        cur = self.conn.cursor()

        cur.execute("PRAGMA table_info(users)")
        cols = [c["name"] for c in cur.fetchall()]
        if "birth_year" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN birth_year INTEGER")

        cur.execute("PRAGMA table_info(facts)")
        cols = [c["name"] for c in cur.fetchall()]

        if "content" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN content TEXT")
        if "image" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN image TEXT")
        if "category" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN category TEXT")
        if "year" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN year INTEGER")
        if "weight" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN weight INTEGER DEFAULT 1")
        if "is_active" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN is_active INTEGER DEFAULT 1")
        if "created_at" not in cols:
            cur.execute("ALTER TABLE facts ADD COLUMN created_at TIMESTAMP")

        self.conn.commit()

    # ---------------- USERS ----------------
    def save_user(self, user_id: int, year: int):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO users (telegram_id, birth_year)
        VALUES (?, ?)
        ON CONFLICT(telegram_id) DO UPDATE SET birth_year=excluded.birth_year
        """, (user_id, year))
        self.conn.commit()

    def get_user(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (user_id,))
        return cur.fetchone()

    def get_total_users(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        return cur.fetchone()[0]

    def get_users_with_year(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM users WHERE birth_year IS NOT NULL")
        return cur.fetchone()[0]

    # ---------------- FACTS ----------------
    def add_fact(self, content: str, image: str, category: str, year: int, weight: int = 1) -> int:
        cur = self.conn.cursor()
        cur.execute("""
        INSERT INTO facts (content, image, category, year, weight, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """, (content, image, category, year, weight))
        self.conn.commit()
        return cur.lastrowid

    def get_fact_by_id(self, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
        row = cur.fetchone()
        return row

    def get_last_facts(self, limit: int = 10):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT * FROM facts
        ORDER BY id DESC
        LIMIT ?
        """, (limit,))
        return cur.fetchall()

    def search_facts_by_text(self, query: str, limit: int = 10):
        cur = self.conn.cursor()
        like = f"%{query}%"
        cur.execute("""
        SELECT * FROM facts
        WHERE content LIKE ? OR category LIKE ?
        ORDER BY id DESC
        LIMIT ?
        """, (like, like, limit))
        return cur.fetchall()

    def get_facts_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facts")
        return cur.fetchone()[0]

    def get_active_facts_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM facts WHERE is_active = 1")
        return cur.fetchone()[0]

    def delete_fact(self, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        cur.execute("DELETE FROM favorites WHERE fact_id = ?", (fact_id,))
        cur.execute("DELETE FROM views WHERE fact_id = ?", (fact_id,))
        self.conn.commit()

    def update_fact_content(self, fact_id: int, content: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE facts SET content = ? WHERE id = ?", (content, fact_id))
        self.conn.commit()

    def update_fact_image(self, fact_id: int, image: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE facts SET image = ? WHERE id = ?", (image, fact_id))
        self.conn.commit()

    def update_fact_category(self, fact_id: int, category: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE facts SET category = ? WHERE id = ?", (category, fact_id))
        self.conn.commit()

    def update_fact_year(self, fact_id: int, year: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE facts SET year = ? WHERE id = ?", (year, fact_id))
        self.conn.commit()

    def update_fact_weight(self, fact_id: int, weight: int):
        cur = self.conn.cursor()
        cur.execute("UPDATE facts SET weight = ? WHERE id = ?", (weight, fact_id))
        self.conn.commit()

    def toggle_fact_active(self, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        UPDATE facts
        SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
        WHERE id = ?
        """, (fact_id,))
        self.conn.commit()

    # ---------------- RANDOM FACTS ----------------
    def get_random_fact(self, user_id: int, year: int):
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
            cur.execute("DELETE FROM views WHERE telegram_id = ?", (user_id,))
            self.conn.commit()

            cur.execute("""
            SELECT * FROM facts
            WHERE year = ?
              AND is_active = 1
            """, (year,))
            rows = cur.fetchall()

            if not rows:
                return None

        weighted = []
        for row in rows:
            weight = row["weight"] if row["weight"] and row["weight"] > 0 else 1
            weighted.extend([row] * weight)

        return random.choice(weighted) if weighted else None

    def add_view(self, user_id: int, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO views (telegram_id, fact_id)
        VALUES (?, ?)
        """, (user_id, fact_id))
        self.conn.commit()

    def get_total_views(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM views")
        return cur.fetchone()[0]

    # ---------------- FAVORITES ----------------
    def add_favorite(self, user_id: int, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        INSERT OR IGNORE INTO favorites (telegram_id, fact_id)
        VALUES (?, ?)
        """, (user_id, fact_id))
        self.conn.commit()

    def remove_favorite(self, user_id: int, fact_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        DELETE FROM favorites
        WHERE telegram_id = ? AND fact_id = ?
        """, (user_id, fact_id))
        self.conn.commit()

    def get_favorites(self, user_id: int):
        cur = self.conn.cursor()
        cur.execute("""
        SELECT f.* FROM facts f
        JOIN favorites fav ON f.id = fav.fact_id
        WHERE fav.telegram_id = ?
        ORDER BY f.id DESC
        """, (user_id,))
        return cur.fetchall()

    def is_favorite(self, user_id: int, fact_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute("""
        SELECT 1 FROM favorites
        WHERE telegram_id = ? AND fact_id = ?
        """, (user_id, fact_id))
        return cur.fetchone() is not None

    def get_total_favorites(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM favorites")
        return cur.fetchone()[0]

    # ---------------- USER STATS ----------------
    def get_stats(self, user_id: int):
        cur = self.conn.cursor()

        cur.execute("SELECT COUNT(*) FROM views WHERE telegram_id = ?", (user_id,))
        views = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM favorites WHERE telegram_id = ?", (user_id,))
        favs = cur.fetchone()[0]

        return views, favs