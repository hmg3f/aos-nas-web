import os
import subprocess
import sqlite3
import borgapi
import tempfile
import hashlib

import datetime
from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from module.util import db
from module.metadata import UserMetadata

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

def octal_to_string(octal):
    permission = ["---", "--x", "-w-", "-wx", "r--", "r-x", "rw-", "rwx"]
    result = "-"

    for i in [int(n) for n in str(octal)]:
        result += permission[i]

    return result

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

        # Use metadata database for file listing
        metadata = UserMetadata(current_user.store_path)
        try:
            files = metadata.get_files()
            if files:
                return files
            else:
                return []
        except:
            pass

@datastore.route('/add', methods=['POST'])
@login_required
def add_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    permissions = request.form.get('permissions', 740)
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(get_user_tree_path(current_user), filename)
        
    file.save(filepath)
    
    # Add to metadata database
    file_size = os.path.getsize(filepath)
    metadata = UserMetadata(current_user.store_path)
    metadata.add_file(filename, file_size, permissions)

    create_archive(current_user)
        
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'size': file_size,
        'permissions': permissions
    }), 201

@datastore.route('/delete/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename, archive=True):
    tree_path = get_user_tree_path(current_user)
    filename = secure_filename(filename)
    filepath = os.path.join(tree_path, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
    
    # Remove from filesystem
    os.remove(filepath)
    
    # Remove from metadata
    metadata = UserMetadata(current_user.store_path)
    metadata.remove_file(filename)
    
    # Update user file count
    current_user.num_files = max(0, current_user.num_files - 1)
    db.session.commit()

    if archive:
        create_archive(current_user)
    
    return jsonify({'message': 'File deleted successfully'}), 200

@datastore.route('/delete-multiple', methods=['DELETE'])
@login_required
def delete_multiple():
    files = request.get_json().get('files', [])
    
    for file in files:
        delete_file(file, archive=False)

    create_archive(current_user)

    return jsonify({'message': 'Files deleted successfully'}), 200
