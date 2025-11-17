from flask_sqlalchemy import SQLAlchemy
from logging.handlers import RotatingFileHandler

import re
import os
import logging
import borgapi

db = SQLAlchemy()

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

borg_api = borgapi.BorgAPI(defaults={}, options={})
borg_api.set_environ(BORG_PASSPHRASE="pass")


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


def octal_to_string(octal, dir=False):
    permission = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
    result = "d" if dir else "-"

    for i in [int(n) for n in str(octal)]:
        result += permission[i]

    return result


def octal_to_dict(octal):
    user_perms = octal // 100
    group_perms = (octal // 10) % 10
    all_perms = octal % 10

    return {
        'owner': {
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


def get_repo_path(user):
    path = os.path.join(user.store_path, 'repo')
    if not os.path.exists(path):
        if user.quota not in [None, 'None']:
            borg_api.init(path, make_parent_dirs=True, encryption="repokey", storage_quota=user.quota)
        else:
            borg_api.init(path, make_parent_dirs=True, encryption="repokey")

    return path


def get_or_create_dir(path):
    """return PATH, creating it if it does not exist"""
    if not os.path.exists(path):
        os.makedirs(path)

    return path


def get_stage_path(user):
    """return path to USER's archive staging directory (/store/stage/)"""
    return get_or_create_dir(os.path.join(user.store_path, 'stage'))


def get_metadb_path(user):
    """return path to USER's metadata database (/store/stage/_meta.db)"""
    path = os.path.join(get_stage_path(user), '_meta.db')
    path = os.path.abspath(path)

    if not os.path.exists(path):
        with open(path, 'w') as _:
            pass

    return path


def get_user_tree_path(user):
    """return path to USER's working filetree (/store/stage/tree/)"""
    return get_or_create_dir(os.path.join(get_stage_path(user), 'tree'))


def get_mount_path(user):
    """return path to mountpoint for USER's archives (/store/mount/)"""
    return get_or_create_dir(os.path.join(user.store_path, 'mount'))
