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
