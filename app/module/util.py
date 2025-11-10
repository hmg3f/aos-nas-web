from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt

import re
import os

db = SQLAlchemy()
app = Flask("__main__")
bcrypt = Bcrypt(app)

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
