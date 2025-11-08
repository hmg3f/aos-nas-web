import sqlite3
import os
from datetime import datetime
import bcrypt

class UserManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                display_name TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        
    def hash_password(self, password):
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    
    def verify_password(self, password, password_hash):
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    def get_user_role(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('SELECT role FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def can_modify_user(self, modifier_username, target_username):
        modifier_role = self.get_user_role(modifier_username)
        target_role = self.get_user_role(target_username)
        
        if modifier_username == target_username:
            return True
        
        role_hierarchy = {'user': 0, 'mod': 1, 'admin': 2, 'root': 3}
        
        return role_hierarchy.get(modifier_role, 0) > role_hierarchy.get(target_role, 0)
    
    def change_password(self, modifier_username, target_username, new_password):
        if not self.can_modify_user(modifier_username, target_username):
            return False
        
        password_hash = self.hash_password(new_password)
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            UPDATE users SET password_hash = ?, last_modified = CURRENT_TIMESTAMP 
            WHERE username = ?
        ''', (password_hash, target_username))
        conn.commit()
        conn.close()
        return True
    
    def change_display_name(self, modifier_username, target_username, new_display_name):
        if not self.can_modify_user(modifier_username, target_username):
            return False
        
        conn = sqlite3.connect(self.db_path)
        conn.execute('''
            UPDATE users SET display_name = ?, last_modified = CURRENT_TIMESTAMP 
            WHERE username = ?
        ''', (new_display_name, target_username))
        conn.commit()
        conn.close()
        return True
    
    def get_user_info(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT username, display_name, role, created_date, last_modified 
            FROM users WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        conn.close()
        return result
    
    def list_users(self, modifier_username):
        modifier_role = self.get_user_role(modifier_username)
        role_hierarchy = {'user': 0, 'mod': 1, 'admin': 2, 'root': 3}
        modifier_level = role_hierarchy.get(modifier_role, 0)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute('''
            SELECT username, display_name, role, created_date 
            FROM users ORDER BY username
        ''')
        all_users = cursor.fetchall()
        conn.close()
        
        # Filter users that modifier can see/modify
        accessible_users = []
        for user in all_users:
            username, display_name, role, created_date = user
            user_level = role_hierarchy.get(role, 0)
            if username == modifier_username or modifier_level > user_level:
                accessible_users.append(user)
        
        return accessible_users
