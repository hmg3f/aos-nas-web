import sqlite3
import os

from module.util import convert_from_bytes, octal_to_string


class UserMetadata:
    def __init__(self, user_store_path):
        self.db_path = os.path.join(user_store_path, 'stage', '_meta.db')
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS files (
                id INTEGER PRIMARY KEY,
                filename TEXT DEFAULT "/",
                path TEXT NOT NULL,
                size INTEGER NOT NULL,
                owner TEXT NOT NULL,
                file_group TEXT NOT NULL,
                permissions INTEGER DEFAULT 740,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_hash TEXT,
                UNIQUE(filename, path, owner)
            )
        ''')
        conn.commit()
        conn.close()

    def add_file(self, filename, owner, file_group, size, permissions=740, path='/', file_hash=None):
        if not file_group:
            file_group = owner

        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            INSERT OR REPLACE INTO files (filename, path, owner, file_group, size, permissions, file_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (filename, path, owner, file_group, size, permissions, file_hash))
        conn.commit()
        conn.close()

    def get_files(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT id, filename, owner, file_group, size, permissions FROM files ORDER BY upload_date DESC')
        files = cursor.fetchall()
        conn.close()

        files = [
            (id, filename, owner, file_group, convert_from_bytes(size), permissions)
            for id, filename, owner, file_group, size, permissions in files
        ]

        return files

    def remove_file(self, filename):
        conn = sqlite3.connect(self.db_path)
        conn.execute('DELETE FROM files WHERE filename = ?', (filename,))
        conn.commit()
        conn.close()

    def rename_file(self, new_name, new_path, file_id):
        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE files SET filename = ?, path = ? WHERE id = ?', (new_name, new_path, file_id))
        conn.commit()
        conn.close()

    def _sanitize_path(self, path):
        if not path:
            return '/'
        norm = os.path.normpath('/' + str(path).lstrip('/'))
        return '/' if norm == '.' else norm

    def get_files_in_path(self, path):
        path = self._sanitize_path(path)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            'SELECT id, filename, owner, file_group, size, permissions '
            'FROM files WHERE path = ? ORDER BY upload_date DESC',
            (path,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            (fid, fname, owner, fgrp, convert_from_bytes(size), octal_to_string(perms))
            for fid, fname, owner, fgrp, size, perms in rows
        ]

    def list_subdirectories(self, path):
        path = self._sanitize_path(path).rstrip('/')
        like = f"{path}/%" if path else "/%"
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute('SELECT DISTINCT path FROM files WHERE path LIKE ?', (like,)).fetchall()
        conn.close()

        children = set()
        for (p,) in rows:
            if not p.startswith('/'):
                p = '/' + p.lstrip('/')
            if p == path or p == (path or '/'):
                continue
            rel = p[len(path):].lstrip('/') if path else p.lstrip('/')
            if not rel:
                continue
            first = rel.split('/', 1)[0]
            full = (path + '/' + first) if path else '/' + first
            children.add(full)

        return sorted([(os.path.basename(d), d) for d in children], key=lambda x: x[0].lower())


    def get_file_path_by_id(self, file_id):
        """Retrieve file path and name based on file ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT filename, path FROM files WHERE id = ?', (file_id,))
        file_data = cursor.fetchone()
        conn.close()

        if file_data:
            return file_data  # (filename, path)
        else:
            return None
