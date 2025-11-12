from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from logging.handlers import RotatingFileHandler

import re
import os
import logging

db = SQLAlchemy()
app = Flask("__main__")

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(MODULE_DIR)
DATABASE_PATH = os.path.join(BASE_DIR, 'store')

logdir = os.path.join(os.getcwd(), 'log')
if not os.path.exists(logdir):
    os.makedirs(logdir)

log_formatter = logging.Formatter(
    '[{asctime}]::{levelname} - {message}',
    style='{',
    datefmt='%Y-%m-%d_%H:%M:%S'
)

auth_logfile = os.path.join(logdir, 'auth.log')
auth_handler = RotatingFileHandler(
    auth_logfile,
    maxBytes=1 * 1024 * 1024,  # Rotate at 1MB
    backupCount=5
)
auth_handler.setFormatter(log_formatter)

auth_logger = logging.getLogger("auth")
auth_logger.setLevel(logging.INFO)
auth_logger.addHandler(auth_handler)


store_logfile = os.path.join(logdir, 'store.log')
store_handler = RotatingFileHandler(
    store_logfile,
    maxBytes=1 * 1024 * 1024,  # Rotate at 1MB
    backupCount=5
)
store_handler.setFormatter(log_formatter)

store_logger = logging.getLogger("store-log")
store_logger.setLevel(logging.INFO)
store_logger.addHandler(store_handler)


def convert_to_bytes(size_str):
    suffixes = {
        'B': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
        'P': 1024 ** 5,
        'E': 1024 ** 6
    }

    match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGTP])?', size_str.strip(), re.IGNORECASE)

    if not match:
        raise ValueError(f"Invalid size format: {size_str}")

    number = float(match.group(1))
    suffix = match.group(2).upper() if match.group(2) else 'B'

    if suffix not in suffixes:
        raise ValueError(f"Unsupported suffix: {suffix}")

    return int(number * suffixes[suffix])


def convert_from_bytes(byte_size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]

    if byte_size < 1:
        return f"0 {units[0]}"

    unit_index = 0
    while byte_size >= 1024 and unit_index < len(units) - 1:
        byte_size /= 1024
        unit_index += 1

    return f"{byte_size:.2f} {units[unit_index]}"


def octal_to_string(octal):
    permission = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
    result = "-"

    for i in [int(n) for n in str(octal)]:
        result += permission[i]

    return result


def octal_to_dict(octal):
    user_perms = octal // 100
    group_perms = (octal // 10) % 10
    all_perms = octal % 10

    return {
        'user': {
            'read': user_perms & 4 != 0,
            'write': user_perms & 2 != 0,
            'execute': user_perms & 1 != 0
        },
        'group': {
            'read': group_perms & 4 != 0,
            'write': group_perms & 2 != 0,
            'execute': group_perms & 1 != 0
        },
        'all': {
            'read': all_perms & 4 != 0,
            'write': all_perms & 2 != 0,
            'execute': all_perms & 1 != 0
        }
    }


def evaluate_read_permission(user, file):
    user_groups = user.user_groups.split(',')
    file_perms = file['permissions']
    file_owner = file['owner']
    file_group = file['group']

    perms_dict = octal_to_dict(int(file_perms))

    if user.username == file_owner:
        return True

    if perms_dict['all']['read']:
        return True

    if file_group in user_groups:
        if perms_dict['group']['read']:
            return True

    return False
