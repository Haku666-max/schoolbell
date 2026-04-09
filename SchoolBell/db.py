import json
import os
import sqlite3
from typing import List, Optional


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row

    def init(self) -> None:
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                graduation_year INTEGER,
                selected_mode TEXT DEFAULT 'mixed',
                is_blocked INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT DEFAULT '',
                content TEXT DEFAULT '',
                changed_after INTEGER NOT NULL,
                tone TEXT NOT NULL,
                image TEXT DEFAULT '',
                school_version TEXT DEFAULT '',
                current_version TEXT DEFAULT '',
                explanation TEXT DEFAULT '',
                source TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS shown_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                fact_id INTEGER NOT NULL,
                shown_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(telegram_id, fact_id)
            )
        """)

        self.conn.commit()
        self.ensure_facts_columns()
        self.seed_facts_if_empty()
        self.fill_created_at_if_empty()

    def ensure_facts_columns(self) -> None:
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(facts)")
        columns = [row["name"] for row in cur.fetchall()]

        if "title" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN title TEXT DEFAULT ''")

        if "content" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN content TEXT DEFAULT ''")

        if "image" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN image TEXT DEFAULT ''")

        if "school_version" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN school_version TEXT DEFAULT ''")

        if "current_version" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN current_version TEXT DEFAULT ''")

        if "explanation" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN explanation TEXT DEFAULT ''")

        if "source" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN source TEXT DEFAULT ''")

        if "created_at" not in columns:
            cur.execute("ALTER TABLE facts ADD COLUMN created_at TIMESTAMP")

        self.conn.commit()

    def fill_created_at_if_empty(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET created_at = CURRENT_TIMESTAMP
            WHERE created_at IS NULL OR created_at = ''
        """)
        self.conn.commit()

    def seed_facts_if_empty(self) -> None:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM facts")
        count = cur.fetchone()["cnt"]

        if count > 0:
            return

        data_path = os.path.join(os.path.dirname(__file__), "data.json")
        if not os.path.exists(data_path):
            return

        with open(data_path, "r", encoding="utf-8") as f:
            seed_data = json.load(f)

        normalized_data = []
        for item in seed_data:
            content = item.get("content")
            if not content:
                parts = []
                if item.get("title"):
                    parts.append(f"<b>{item['title']}</b>")
                if item.get("school_version"):
                    parts.append(f"Как говорили в школе: {item['school_version']}")
                if item.get("current_version"):
                    parts.append(f"Сейчас: {item['current_version']}")
                if item.get("explanation"):
                    parts.append(item["explanation"])
                content = "\n\n".join(parts).strip()

            normalized_data.append({
                "category": item.get("category", "other"),
                "title": item.get("title", ""),
                "content": content or "Без описания",
                "changed_after": int(item.get("changed_after", 2000)),
                "tone": item.get("tone", "mixed"),
                "image": item.get("image", ""),
                "school_version": item.get("school_version", ""),
                "current_version": item.get("current_version", ""),
                "explanation": item.get("explanation", ""),
                "source": item.get("source", ""),
            })

        cur.executemany("""
            INSERT INTO facts (
                category,
                title,
                content,
                changed_after,
                tone,
                image,
                school_version,
                current_version,
                explanation,
                source
            ) VALUES (
                :category,
                :title,
                :content,
                :changed_after,
                :tone,
                :image,
                :school_version,
                :current_version,
                :explanation,
                :source
            )
        """, normalized_data)

        self.conn.commit()

    def upsert_user(self, telegram_id: int, username: str = "", first_name: str = "") -> None:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO users (telegram_id, username, first_name, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                updated_at = CURRENT_TIMESTAMP
        """, (telegram_id, username, first_name))
        self.conn.commit()

    def set_graduation_year(self, telegram_id: int, year: int) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE users
            SET graduation_year = ?, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        """, (year, telegram_id))
        self.conn.commit()

    def set_mode(self, telegram_id: int, mode: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE users
            SET selected_mode = ?, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
        """, (mode, telegram_id))
        self.conn.commit()

    def get_user(self, telegram_id: int) -> Optional[sqlite3.Row]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        return cur.fetchone()

    def get_total_users(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        return cur.fetchone()["cnt"]

    def get_users_with_year(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM users WHERE graduation_year IS NOT NULL")
        return cur.fetchone()["cnt"]

    def add_fact(
        self,
        category: str,
        title: str,
        content: str,
        changed_after: int,
        tone: str,
        image: str,
    ) -> int:
        cur = self.conn.cursor()

        school_version = content
        current_version = content
        explanation = ""
        source = ""

        cur.execute("""
            INSERT INTO facts (
                category,
                title,
                content,
                changed_after,
                tone,
                image,
                school_version,
                current_version,
                explanation,
                source,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            category,
            title,
            content,
            changed_after,
            tone,
            image,
            school_version,
            current_version,
            explanation,
            source,
        ))
        self.conn.commit()
        return cur.lastrowid

    def get_facts_count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM facts")
        return cur.fetchone()["cnt"]

    def get_facts_for_user(
        self,
        telegram_id: int,
        graduation_year: int,
        mode: str,
        limit: int = 5,
    ) -> List[dict]:
        cur = self.conn.cursor()

        tone_filter = {
            "serious": ["serious"],
            "funny": ["funny"],
            "mixed": ["serious", "funny", "mixed"],
        }.get(mode, ["serious", "funny", "mixed"])

        placeholders = ",".join("?" for _ in tone_filter)

        query = f"""
            SELECT *
            FROM facts
            WHERE changed_after >= ?
              AND tone IN ({placeholders})
              AND id NOT IN (
                  SELECT fact_id FROM shown_facts WHERE telegram_id = ?
              )
            ORDER BY created_at DESC, RANDOM()
            LIMIT ?
        """
        params = [graduation_year, *tone_filter, telegram_id, limit]
        cur.execute(query, params)
        rows = cur.fetchall()

        if not rows:
            query = f"""
                SELECT *
                FROM facts
                WHERE changed_after >= ?
                  AND tone IN ({placeholders})
                ORDER BY created_at DESC, RANDOM()
                LIMIT ?
            """
            params = [graduation_year, *tone_filter, limit]
            cur.execute(query, params)
            rows = cur.fetchall()

        return [dict(row) for row in rows]

    def mark_facts_shown(self, telegram_id: int, fact_ids: List[int]) -> None:
        cur = self.conn.cursor()
        cur.executemany(
            "INSERT OR IGNORE INTO shown_facts (telegram_id, fact_id) VALUES (?, ?)",
            [(telegram_id, fact_id) for fact_id in fact_ids],
        )
        self.conn.commit()

    def get_last_facts(self, limit: int = 10, offset: int = 0) -> List[dict]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT *
            FROM facts
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        return [dict(row) for row in cur.fetchall()]

    def get_fact_by_id(self, fact_id: int) -> Optional[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM facts WHERE id = ?", (fact_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def delete_fact(self, fact_id: int) -> None:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        self.conn.commit()

    def update_fact_content(self, fact_id: int, content: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET content = ?, updated_rowid = rowid
            WHERE id = ?
        """, (content, fact_id))
        self.conn.commit()

    def update_fact_image(self, fact_id: int, image: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET image = ?
            WHERE id = ?
        """, (image, fact_id))
        self.conn.commit()

    def update_fact_category(self, fact_id: int, category: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET category = ?
            WHERE id = ?
        """, (category, fact_id))
        self.conn.commit()

    def update_fact_tone(self, fact_id: int, tone: str) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET tone = ?
            WHERE id = ?
        """, (tone, fact_id))
        self.conn.commit()

    def update_fact_year(self, fact_id: int, changed_after: int) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            UPDATE facts
            SET changed_after = ?
            WHERE id = ?
        """, (changed_after, fact_id))
        self.conn.commit()