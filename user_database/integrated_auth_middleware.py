from functools import wraps
from flask import abort
from flask_login import current_user
import sqlite3
import os

def check_permission(username, resource_path, action):
    db_path = "../app/store/nasinfo.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.can_read, p.can_write, p.can_delete, u.role
        FROM permissions p
        JOIN users u ON p.user_id = u.id
        WHERE u.username = ? AND (p.resource_path = ? OR p.resource_path = '*')
        ORDER BY p.resource_path DESC
    ''', (username, resource_path))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return False
    
    can_read, can_write, can_delete, role = result
    
    if role == 'admin':
        return True
    
    return {
        'read': can_read,
        'write': can_write, 
        'delete': can_delete
    }.get(action, False)

def require_permission(resource_path, action):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            if not check_permission(current_user.username, resource_path, action):
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
