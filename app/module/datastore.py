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

        current_time = datetime.datetime.now()
        stage_path = get_stage_path(user)

        metadata_db = os.path.join(stage_path, '_meta.db')
        if not os.path.exists(metadata_db):
            with open(metadata_db, 'w') as _:
                pass
        
        user.archive_state = current_time.strftime(f"{path}::%Y-%m-%d_%H:%M:%S")
        borg_api.create(user.archive_state, stage_path)
        
        db.session.commit()
        
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

def select_archive_or_create(user):
    pass



@datastore.route('/retrieve')
@login_required
def retrieve_user_store():
    if current_user.is_authenticated:
        stage_path = get_stage_path(current_user)
        metadata_db = os.path.join(stage_path, '_meta.db') 
        
        if not os.path.exists(metadata_db):
            repo_path = get_repo_path(current_user)
            
            if not current_user.archive_state:
                select_archive_or_create(current_user)
                
            borg_api.extract(current_user.archive_state, stage_path)
            return os.listdir(stage_path)

        # TODO: once metadata db is implemented, pull files from there instead of listing directory.
        return [(file, os.path.getsize(os.path.join(stage_path, file)), '-rwxr-----')
                for file in os.listdir(stage_path)
                if file != "_meta.db"]

@datastore.route('/add', methods=['POST'])
@login_required
def add_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    permissions = request.form.get('permissions', '-rwxr-----')
    filename = secure_filename(file.filename)
    filepath = os.path.join(get_user_tree_path(current_user), filename)
        
    file.save(filepath)
        
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'size': file_size,
        'permissions': permissions
    }), 201

@datastore.route('/delete/<filename>', methods=['DELETE'])
@login_required
def delete_file(filename):
    stage_path = get_stage_path(current_user)
    filepath = os.path.join(stage_path, filename)
    
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
    
    return jsonify({'message': 'File deleted successfully'}), 200
