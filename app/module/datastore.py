import os
import subprocess
import borgapi
import time
import datetime
import shutil
import sqlite3

from flask import Blueprint, request, jsonify, send_from_directory, render_template, url_for, redirect
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField
from werkzeug.utils import secure_filename

from module.auth import list_users, get_user_by_id, evaluate_read_permission
from module.util import db, store_logger, convert_from_bytes, octal_to_string
from module.metadata import UserMetadata

datastore = Blueprint('/store', __name__)

borg_api = borgapi.BorgAPI(defaults={}, options={})
borg_api.set_environ(BORG_PASSPHRASE="pass")


class SharedFilesForm(FlaskForm):
    owner = SelectField('Owner:', coerce=int)
    submit = SubmitField('View Files')

    def __init__(self, owner_choices=None, *args, **kwargs):
        super(SharedFilesForm, self).__init__(*args, **kwargs)
        if owner_choices:
            self.owner.choices = [(str(user_id), username) for user_id, username in owner_choices]


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


def create_archive(user):
    """create a new archive for USER."""
    original_cwd = os.getcwd()
    os.chdir(user.store_path)

    borg_unmount(user)

    current_time = datetime.datetime.now()
    repo_path = get_repo_path(user)

    user.archive_state = current_time.strftime(f"{repo_path}::%Y-%m-%d_%H:%M:%S")
    borg_api.create(user.archive_state, 'stage')

    db.session.commit()
    os.chdir(original_cwd)

    store_logger.info(f'User {user.username} created a new archive: {user.archive_state}')


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


@datastore.route('/create-folder', methods=['POST'])
@login_required
def create_folder():
    data = request.get_json()
    folder_name = data.get('folder_name', '').strip()
    parent_path = data.get('path', '/')

    if not folder_name:
        return jsonify({'error': 'Folder name required'}), 400

    folder_name = secure_filename(folder_name)

    metadata = UserMetadata(get_metadb_path(current_user))
    parent_path = metadata._sanitize_path(parent_path)

    abs_dir = os.path.join(get_user_tree_path(current_user), parent_path.strip('/'), folder_name)
    if os.path.exists(abs_dir):
        return jsonify({'error': 'Folder already exists'}), 400

    os.makedirs(abs_dir)

    metadata.add_file(
        filename=folder_name,
        owner=current_user.id,
        file_group=current_user.username,
        size=0,
        is_directory=True,
        permissions=744,
        path=parent_path
    )

    store_logger.info(f'User {current_user.username} created folder: {abs_dir}')
    return jsonify({'message': 'Folder created successfully'})


def calculate_folder_size(user, folder_path):
    """Return total size (bytes) of all files inside folder_path (direct + recursive)."""
    metadata = UserMetadata(get_metadb_path(user))
    norm = metadata._sanitize_path(folder_path)

    conn = sqlite3.connect(metadata.db_path)
    try:
        if norm == '/':
            cursor = conn.execute("SELECT size FROM files WHERE path = '/' OR path = ''")
            sizes = [row[0] for row in cursor.fetchall() if row[0]]
        else:
            like = norm.rstrip('/') + '/%'
            cursor = conn.execute(
                "SELECT size FROM files WHERE path = ? OR path = ? OR path LIKE ?",
                (norm, norm + '/', like)
            )
            sizes = [row[0] for row in cursor.fetchall() if row[0]]
    finally:
        conn.close()

    return sum(sizes)


@login_required
def filter_permitted_files(files):
    return [file for file in files
            if file['is_directory'] or evaluate_read_permission(current_user, file)]


@datastore.route('/retrieve/<user>')
@login_required
def retrieve_user_store(user):
    get_user_tree_path(user)
    get_metadb_path(user)

    metadata = UserMetadata(get_metadb_path(user))
    req_path = request.args.get('path', '/')
    current_path = metadata._sanitize_path(req_path)

    files = metadata.get_files(current_path)
    dirs_raw = metadata.list_subdirectories(current_path)

    folder_names_in_files = set()
    for file in files:
        if file['is_directory']:
            folder_names_in_files.add(file['name'])

    for dirname, fullpath in dirs_raw:
        if dirname not in folder_names_in_files:
            folder_size = calculate_folder_size(user, fullpath)
            files.append({
                'id': None,
                'name': dirname,
                'owner': user.id,
                'group': user.username,
                'size': folder_size,
                'permissions': 744,
                'is_directory': True
            })

    for f in files:
        if f['is_directory']:
            f['size'] = calculate_folder_size(user, current_path.rstrip('/') + '/' + f['name'])

    files.sort(key=lambda x: (not x['is_directory'], x['name'].lower()))

    files_avail = filter_permitted_files(files)

    return {'files': files_avail, 'path': current_path}


@datastore.route('/archive-list')
@login_required
def list_archives():
    repo_path = get_repo_path(current_user)
    return borg_api.list(repo_path, json=True)['archives']


@datastore.route('/diff/<archive>', methods=['GET'])
@login_required
def get_diff(archive):
    original_cwd = os.getcwd()
    os.chdir(current_user.store_path)

    mount_path = get_mount_path(current_user)
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

    store_logger.info(f'User {current_user.username} restored archive to version: {archive_name}')

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
    file_group = request.form.get('file-group', current_user.username)

    upload_path = request.form.get('path', '/')
    filename = secure_filename(file.filename)

    metadata = UserMetadata(get_metadb_path(current_user))
    upload_path = metadata._sanitize_path(upload_path)

    base_path = get_user_tree_path(current_user)
    abs_dir = os.path.join(base_path, upload_path.strip('/'))
    if not os.path.exists(abs_dir):
        os.makedirs(abs_dir)

    filepath = os.path.join(abs_dir, filename)
    file.save(filepath)

    # Add to metadata database
    file_size = os.path.getsize(filepath)
    metadata.add_file(filename=filename,
                      owner=current_user.id,
                      file_group=file_group,
                      size=file_size,
                      is_directory=False,
                      permissions=permissions,
                      path=upload_path)

    create_archive(current_user)

    store_logger.info(f'User {current_user.username} uploaded file: {filename} to {upload_path}')

    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'owner': current_user.id,
        'file_group': file_group,
        'size': file_size,
        'permissions': permissions
    }), 201


@datastore.route('/delete-files', methods=['DELETE'])
@login_required
def delete_files():
    data = request.get_json() or {}
    names = data.get('files', [])
    raw_path = data.get('path', '/')

    metadata = UserMetadata(get_metadb_path(current_user))
    current_path = metadata._sanitize_path(raw_path)

    base_tree = get_user_tree_path(current_user)
    deleted_count = 0

    # TODO: move this to metadata.py and switch to sqlalchemy
    # metadata db connection for batch ops
    conn = sqlite3.connect(metadata.db_path)

    for name in names:
        safe_name = secure_filename(name)
        abs_target = os.path.join(base_tree, current_path.strip('/'), safe_name)

        if os.path.isdir(abs_target):
            # Delete directory from disk
            shutil.rmtree(abs_target)

            # Full folder path in metadata terms
            if current_path == '/':
                folder_full_path = '/' + safe_name
            else:
                folder_full_path = current_path.rstrip('/') + '/' + safe_name

            # Remove folder entry and all contents under it from metadata
            conn.execute('DELETE FROM files WHERE filename = ? AND path = ?', (safe_name, current_path))
            conn.execute('DELETE FROM files WHERE path = ? OR path LIKE ?', (folder_full_path, folder_full_path.rstrip('/') + '/%'))
            deleted_count += 1

        elif os.path.isfile(abs_target):
            # Delete file from disk
            os.remove(abs_target)

            # Remove file entry for this exact path
            conn.execute('DELETE FROM files WHERE filename = ? AND path = ?', (safe_name, current_path))
            deleted_count += 1
        else:
            # Not found under this path – skip
            continue

    conn.commit()
    conn.close()

    # Update user stats and archive once after the batch
    if deleted_count > 0:
        current_user.num_files = max(0, current_user.num_files - deleted_count)
        db.session.commit()
        create_archive(current_user)

    store_logger.info(f'User {current_user.username} deleted {deleted_count} item(s) from {current_path}')
    return jsonify({'message': f'Deleted {deleted_count} item(s)'}), 200


@datastore.route('/download')
@login_required
def download_file():
    user_id = request.args.get('user_id')
    user = get_user_by_id(user_id)

    metadata = UserMetadata(get_metadb_path(user))
    file_id = request.args.get('file_id')
    file_data = metadata.get_file_path_by_id(file_id)

    if not file_data:
        return jsonify({'error': 'File not found'}), 404

    file_name, file_path = file_data
    if file_path == '/':
        file_path = get_user_tree_path(user)
    else:
        file_path = os.path.join(get_user_tree_path(user), file_path.lstrip('/'))
        print(file_path)

    store_logger.info(f'User {current_user.username} downloaded file: <store:{user.username}>{file_path}')

    return send_from_directory(file_path, file_name, as_attachment=True)


@datastore.route('/rename/<file_id>', methods=['POST'])
@login_required
def rename_file(file_id):
    metadata = UserMetadata(get_metadb_path(current_user))
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

    store_logger.info(f'User {current_user.username} renamed file: {current_file} to: {new_file}')

    return jsonify({'success': 'File renamed successfully'}), 200


@datastore.route('/recalc-sizes')
@login_required
def recalc_sizes():
    """Recalculate file sizes for all files in metadata"""
    base_path = get_user_tree_path(current_user)
    metadata = UserMetadata(get_metadb_path(current_user))
    conn = sqlite3.connect(metadata.db_path)
    cursor = conn.execute('SELECT id, filename, path FROM files')
    updated = 0

    for fid, fname, fpath in cursor.fetchall():
        abs_path = os.path.join(base_path, fpath.strip('/'), fname)
        if os.path.isfile(abs_path):
            size = os.path.getsize(abs_path)
            conn.execute('UPDATE files SET size = ? WHERE id = ?', (size, fid))
            updated += 1

    conn.commit()
    conn.close()
    return jsonify({'message': f'Updated {updated} file sizes.'})


@datastore.route('/shared-files')
@login_required
def get_shared_fs():
    user_id = request.args.get('user_id')
    user = get_user_by_id(user_id)

    data = retrieve_user_store(user)
    file_list = data.get('files', [])

    for file in file_list:
        file['size'] = convert_from_bytes(file['size'])
        file['owner'] = get_user_by_id(file['owner']).username
        file['permissions'] = octal_to_string(file['permissions'])

    return render_template('shared-files.html',
                           file_list=data.get('files', []),
                           dir_list=data.get('dirs', []),
                           current_path=data.get('path', '/'),
                           user_id=user_id)


@datastore.route('/files', methods=['GET', 'POST'])
@login_required
def file_viewer():
    get_metadb_path(current_user)
    data = retrieve_user_store(current_user)
    file_list = data.get('files', [])
    dir_list = data.get('dirs', [])
    current_path = data.get('path', '/')
    archive_list = list_archives()

    for file in file_list:
        file['size'] = convert_from_bytes(file['size'])
        file['owner'] = get_user_by_id(file['owner']).username
        file['permissions'] = octal_to_string(file['permissions'])

    users_list = [(user['id'], user['username']) for user in list_users()]
    shareform = SharedFilesForm(owner_choices=users_list)

    if shareform.validate_on_submit():
        return redirect(url_for('/store.get_shared_fs', user_id=shareform.owner.data))

    return render_template(
        'file-viewer.html',
        file_list=file_list,
        dir_list=dir_list,
        current_path=current_path,
        archive_list=archive_list,
        shareform=shareform
    )
