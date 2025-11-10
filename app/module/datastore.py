import os
import subprocess
import sqlite3
import borgapi
import tempfile
import hashlib
import difflib
import time
import datetime
import shutil

from flask import Blueprint, request, jsonify, send_from_directory
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from module.util import db
from module.metadata import UserMetadata
from module.metadata_user_management import UserManager

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
    original_cwd = os.getcwd()
    os.chdir(user.store_path)

    borg_unmount(user)

    print(f"info:\ncwd: {os.getcwd()}")
    
    current_time = datetime.datetime.now()
    repo_path = get_repo_path(user)

    user.archive_state = current_time.strftime(f"{repo_path}::%Y-%m-%d_%H:%M:%S")
    print(f"archive_state: {user.archive_state}")
    borg_api.create(user.archive_state, 'stage')

    print('staged')
    
    db.session.commit()
    os.chdir(original_cwd)

def find_archive_by_id(id):
    archives = list_archives()
    
    for archive in archives:
        if archive['id'] == id:
            return archive
        
    return None

def borg_unmount(user):
    mount_path = os.path.join(user.store_path, 'mount')
    
    if os.path.ismount(mount_path):
        borg_api.umount(mount_path)

@datastore.route('/archive-list')
@login_required
def list_archives():
    repo_path = get_repo_path(current_user)
    return borg_api.list(repo_path, json=True)['archives']

@datastore.route('/retrieve')
@login_required
def retrieve_user_store():
    if current_user.is_authenticated:
        user_tree_path = get_user_tree_path(current_user)
        metadata_db = get_metadb_path(current_user)

        # Use metadata database for file listing
        metadata = UserMetadata(current_user.store_path)
        files = metadata.get_files()
        print(files)
        if files:
            return files
        else:
            return []

@datastore.route('/diff/<archive>', methods=['GET'])
@login_required
def get_diff(archive):
    original_cwd = os.getcwd()
    os.chdir(current_user.store_path)
    
    current_archive = current_user.archive_state
    mount_path = get_mount_path(current_user)
    stage_path = get_user_tree_path(current_user)
    repo_path = get_repo_path(current_user)
    
    mount_archive = find_archive_by_id(archive)['archive']

    if not mount_archive:
        return jsonify({'error': 'Archive does not exist'}), 400

    borg_unmount(current_user)

    borg_api.mount(f"{repo_path}::{mount_archive}", mount_path)
    
    while not os.path.ismount(mount_path):
        print(f"Waiting for mount at {mount_path}...")
        time.sleep(.01)

    result = subprocess.Popen(
        ['git', 'diff', '--no-index', "stage/tree", "mount/stage/tree"],
        stdout=subprocess.PIPE,
        text=True
    )
    output, error = result.communicate()

    os.chdir(original_cwd)
    borg_unmount(current_user)
    return jsonify({"diff": output})

@datastore.route('/restore/<archive>', methods=['POST'])
@login_required
def restore_archive(archive):
    stage_path = get_stage_path(current_user)
    repo_path = get_repo_path(current_user)
    archive_name = find_archive_by_id(archive)['archive']
    
    borg_unmount(current_user)

    shutil.rmtree(stage_path)

    original_cwd = os.getcwd()
    os.chdir(current_user.store_path)
    borg_api.extract(f"{repo_path}::{archive_name}", "stage")
    os.chdir(original_cwd)

    return jsonify({"message": "Archive restored successfully"}), 200

@datastore.route('/add', methods=['POST'])
@login_required
def add_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    permissions = request.form.get('permissions', 740)
    file_group = request.form.get('file-group', None)
    
    filename = secure_filename(file.filename)
    filepath = os.path.join(get_user_tree_path(current_user), filename)
    
    file.save(filepath)
    
    # Add to metadata database
    file_size = os.path.getsize(filepath)
    metadata = UserMetadata(current_user.store_path)
    metadata.add_file(filename, current_user.username, file_group, file_size, permissions)

    create_archive(current_user)
    
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'owner': current_user.username,
        'file_group': file_group,
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

@datastore.route('/download/<file_id>')
@login_required
def download_file(file_id):
    metadata = UserMetadata(current_user.store_path)
    file_data = metadata.get_file_path_by_id(file_id)

    if not file_data:
        return jsonify({'error': 'File not found'}), 404

    file_name, file_path = file_data
    if file_path == '/':
        file_path = get_user_tree_path(current_user)
    else:
        file_path = os.path.join(get_user_tree_path(current_user), file_path)

    print(f"path: {file_path}\nname: {file_name}")

    return send_from_directory(file_path, file_name, as_attachment=True)


@datastore.route('/rename/<file_id>', methods=['POST'])
@login_required
def rename_file(file_id):
    metadata = UserMetadata(current_user.store_path)
    file_data = metadata.get_file_path_by_id(file_id)

    if not file_data:
        return jsonify({'error': 'File not found'}), 404

    file_name, file_path = file_data
    if file_path == '/':
        current_path = get_user_tree_path(current_user)
    else:
        current_path = os.path.join(get_user_tree_path(current_user), file_path)
        
    current_file = os.path.join(current_path, file_name)

    new_name = request.json.get('new_name').strip()

    if not new_name:
        return jsonify({'error': 'No name given'}), 400

    # TODO: support directory rename
    new_file = os.path.join(current_path, new_name)

    os.rename(current_file, new_file)
    metadata.rename_file(new_name, file_path, file_id)

    return jsonify({'success': 'File renamed successfully'}), 200

@datastore.route('/profile')
@login_required
def profile():
    user_manager = UserManager(get_metadb_path(current_user))
    user_info = user_manager.get_user_info(current_user.username)
    return jsonify(user_info)

@datastore.route('/change-password', methods=['POST'])
@login_required
def change_password():
    user_manager = UserManager(get_metadb_path(current_user))
    data = request.get_json()
    success = user_manager.change_password(
        current_user.username,
        data['target_user'],
        data['new_password']
    )
    return jsonify({'success': success})

@datastore.route('/change-name', methods=['POST'])
@login_required
def change_display_name():
    user_manager = UserManager(get_metadb_path(current_user))
    data = request.get_json()
    success = user_manager.change_display_name(
        current_user.username,
        data['target_user'],
        data['new_display_name']
    )
    return jsonify({'success': success})
