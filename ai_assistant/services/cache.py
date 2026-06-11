import os
import sqlite3


class CacheService:
    def __init__(self, db_path="data/cache.db"):
        self.db_path = db_path

        folder = os.path.dirname(self.db_path)
        if folder:
            os.makedirs(folder, exist_ok=True)

        self._create_table()

    def _create_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                query TEXT PRIMARY KEY,
                response TEXT
            )
        """)

        conn.commit()
        conn.close()

    def save(self, query: str, response: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO cache (query, response)
            VALUES (?, ?)
        """, (query, response))

        conn.commit()
        conn.close()

    def lookup(self, query: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT response FROM cache WHERE query = ?
        """, (query,))

        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None