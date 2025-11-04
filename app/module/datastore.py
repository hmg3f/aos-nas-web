import os
import subprocess
import sqlite3
import borgapi
import tempfile

import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from module.util import db

datastore = Blueprint('/store', __name__)

borg_api = borgapi.BorgAPI(defaults={}, options={})
borg_api.set_environ(BORG_PASSPHRASE="pass")

def get_repo_path(user):
    path = os.path.join(user.store_path, 'repo')
    if not os.path.exists(path):
        print(f'user.quota: {user.quota} ({type(user.quota)})')
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

def create_archive(user):
    """create a new archive for USER."""
    current_time = datetime.datetime.now()
    
    stage_path = get_stage_path(user)
    repo_path = get_repo_path(user)

    user.archive_state = current_time.strftime(f"{repo_path}::%Y-%m-%d_%H:%M:%S")
    borg_api.create(user.archive_state, stage_path)
        
    db.session.commit()

@datastore.route('/archive-list')
@login_required
def list_archives():
    repo_path = get_repo_path(current_user)
    return borg_api.list(repo_path, json=True)

@datastore.route('/retrieve')
@login_required
def retrieve_user_store():
    if current_user.is_authenticated:
        user_tree_path = get_user_tree_path(current_user)
        metadata_db = get_metadb_path(current_user)

        # TODO: once metadata db is implemented, pull files from there instead of listing directory.
        return [(file, os.path.getsize(os.path.join(user_tree_path, file)), '-rwxr-----')
                for file in os.listdir(user_tree_path)]

@datastore.route('/add', methods=['POST'])
@login_required
def add_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    # Get permissions (octal string like "664")
    permissions = request.form.get('permissions', '740')
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(get_user_tree_path(current_user), filename)
        
    file.save(filepath)

    create_archive(current_user)
        
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'permissions': permissions
    }), 201
    

    
