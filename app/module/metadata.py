import sqlite3
import os
from datetime import datetime

class UserMetadata:
    def __init__(self, user_store_path):
        self.db_path = os.path.join(user_store_path, 'stage', '_meta.db')
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                filename TEXT UNIQUE NOT NULL,
                size INTEGER NOT NULL,
                permissions INTEGER DEFAULT 740,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def add_file(self, filename, size, permissions=740, file_hash=None):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT OR REPLACE INTO files (filename, size, permissions, file_hash)
            VALUES (?, ?, ?, ?)
        ''', (filename, size, permissions, file_hash))
        conn.commit()
        conn.close()
    
    def get_files(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT filename, size, permissions FROM files ORDER BY upload_date DESC')
        files = cursor.fetchall()
        conn.close()
        return files
    
    def remove_file(self, filename):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM files WHERE filename = ?', (filename,))
        conn.commit()
        conn.close()
