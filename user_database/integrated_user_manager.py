#!/usr/bin/env python3
import sqlite3
import os
import sys
sys.path.append('../app')
from module.util import bcrypt

class IntegratedUserManager:
    def __init__(self):
        # Use same DB path as main app
        self.db_path = "../app/store/nasinfo.db"
        self.init_permissions_table()
    
    def init_permissions_table(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Add permissions table to existing schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS permissions (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                resource_path TEXT,
                can_read BOOLEAN DEFAULT 0,
                can_write BOOLEAN DEFAULT 0,
                can_delete BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Add role column to existing users table
        cursor.execute('''
            ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'
        ''')
        
        conn.commit()
        conn.close()
    
    def create_user(self, username, password, quota='1G', role='user'):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Use bcrypt like main app
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        store_path = f"/store/{username}"
        
        try:
            cursor.execute('''
                INSERT INTO users (username, password, quota, store_path, role, num_files)
                VALUES (?, ?, ?, ?, ?, 0)
            ''', (username, hashed_pw, quota, store_path, role))
            
            user_id = cursor.lastrowid
            conn.commit()
            print(f"User '{username}' created with ID {user_id}")
            return user_id
        except sqlite3.IntegrityError:
            print(f"User '{username}' already exists")
            return None
        finally:
            conn.close()
    
    def set_permissions(self, username, resource_path, read=False, write=False, delete=False):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if not user:
            print(f"User '{username}' not found")
            return False
        
        user_id = user[0]
        cursor.execute('''
            INSERT OR REPLACE INTO permissions 
            (user_id, resource_path, can_read, can_write, can_delete)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, resource_path, read, write, delete))
        
        conn.commit()
        conn.close()
        print(f"Permissions set for '{username}' on '{resource_path}'")
        return True

if __name__ == "__main__":
    um = IntegratedUserManager()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python integrated_user_manager.py create <username> <password> [quota] [role]")
        print("  python integrated_user_manager.py permit <username> <path> <read> <write> <delete>")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        username, password = sys.argv[2], sys.argv[3]
        quota = sys.argv[4] if len(sys.argv) > 4 else '1G'
        role = sys.argv[5] if len(sys.argv) > 5 else 'user'
        um.create_user(username, password, quota, role)
    
    elif cmd == "permit":
        username, path = sys.argv[2], sys.argv[3]
        read, write, delete = sys.argv[4] == '1', sys.argv[5] == '1', sys.argv[6] == '1'
        um.set_permissions(username, path, read, write, delete)
