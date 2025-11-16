import os
import subprocess
import time
import datetime
import shutil
import sqlite3

from flask import Blueprint, request, jsonify, send_from_directory, render_template, url_for, redirect, flash
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField, StringField
from wtforms.validators import InputRequired, Length, Regexp
from werkzeug.utils import secure_filename

from module.auth import list_users, get_user_by_id, evaluate_read_permission, evaluate_write_permission, evaluate_exec_permission
from module.util import db, borg_api, store_logger, convert_from_bytes, octal_to_string, get_repo_path, get_mount_path, get_metadb_path, get_user_tree_path, get_stage_path
from module.metadata import UserMetadata

datastore = Blueprint('/store', __name__)


class SharedFilesForm(FlaskForm):
    owner = SelectField('Owner:', coerce=int,
                        validators=[InputRequired()],
                        render_kw={'placeholder': 'Select a User'})
    submit = SubmitField('View Files')

    def __init__(self, owner_choices=None, *args, **kwargs):
        super(SharedFilesForm, self).__init__(*args, **kwargs)
        if owner_choices:
            self.owner.choices = [(str(user_id), username) for user_id, username in owner_choices]


class NewFolderForm(FlaskForm):
    name = StringField('Folder name:',
                       validators=[InputRequired()],
                       render_kw={'placeholder': 'name'})
    perms = StringField('Folder Permissions:',
                        validators=[InputRequired(), Length(min=3, max=3), Regexp('^[0-7]{3}$')],
                        default='744'
                        )
    submit = SubmitField('Create Folder')


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


@login_required
def create_folder(folder_name, folder_perms, path):
    folder_name = folder_name.strip()
    permissions = folder_perms.strip()
    parent_path = path

    if not folder_name:
        flash('Folder name required', 'error')
        return

    folder_name = secure_filename(folder_name)

    metadata = UserMetadata(get_metadb_path(current_user))
    parent_path = metadata._sanitize_path(parent_path)

    abs_dir = os.path.join(get_user_tree_path(current_user), parent_path.strip('/'), folder_name)
    if os.path.exists(abs_dir):
        flash('Folder already exists', 'error')
        return

    os.makedirs(abs_dir)

    metadata.add_file(
        filename=folder_name,
        owner=current_user.id,
        file_group=current_user.username,
        size=0,
        is_directory=True,
        permissions=int(permissions),
        path=parent_path
    )

    store_logger.info(f'User {current_user.username} created folder: {abs_dir}')
    flash('Folder created successfully', 'success')


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
            if evaluate_read_permission(current_user, file)]


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
                'file_group': user.username,
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
    # Multiple files are sent as "file[]" field
    files = request.files.getlist("file[]")
    if not files or files == ['']:
        return jsonify({'error': 'No files provided'}), 400

    permissions = request.form.get('permissions', 740)
    file_group = request.form.get('file-group', current_user.username)
    upload_path = request.form.get('path', '/')

    metadata = UserMetadata(get_metadb_path(current_user))
    upload_path = metadata._sanitize_path(upload_path)

    base_path = get_user_tree_path(current_user)
    abs_dir = os.path.join(base_path, upload_path.strip('/'))
    if not os.path.exists(abs_dir):
        os.makedirs(abs_dir)

    uploaded = []

    for file in files:
        if file.filename == '':
            continue

        filename = secure_filename(file.filename)
        filepath = os.path.join(abs_dir, filename)
        file.save(filepath)

        file_size = os.path.getsize(filepath)

        metadata.add_file(
            filename=filename,
            owner=current_user.id,
            file_group=file_group,
            size=file_size,
            is_directory=False,
            permissions=permissions,
            path=upload_path
        )

        uploaded.append(filename)
        store_logger.info(
            f'User {current_user.username} uploaded file: {filename} to {upload_path}'
        )

    if uploaded:
        current_user.num_files += len(uploaded)
        db.session.commit()
        create_archive(current_user)

    return jsonify({
        'message': f"Uploaded {len(uploaded)} file(s) successfully",
        'count': len(uploaded),
        'files': uploaded
    }), 201


@datastore.route('/delete-files', methods=['DELETE'])
@login_required
def delete_files():
    data = request.get_json() or {}
    file_ids = data.get('file_ids', [])

    user_id = data.get('user_id')
    user = get_user_by_id(user_id)

    raw_path = data.get('path', '/')

    metadata = UserMetadata(get_metadb_path(user))
    current_path = metadata._sanitize_path(raw_path)

    base_tree = get_user_tree_path(user)
    deleted_count = 0

    for file_id in file_ids:
        file_data = metadata.get_file_by_id(file_id)

        if not evaluate_write_permission(current_user, file_data.__dict__):
            flash(f'No write permission granted for {file_data.filename}', 'error')
            continue

        abs_target = os.path.join(base_tree, current_path.strip('/'), file_data.filename)

        if os.path.isdir(abs_target):
            shutil.rmtree(abs_target)
        elif os.path.isfile(abs_target):
            os.remove(abs_target)
        else:
            continue

        metadata.remove_file(file_id)
        deleted_count += 1

    # Update user stats and archive once after the batch
    if deleted_count > 0:
        user.num_files = max(0, user.num_files - deleted_count)
        db.session.commit()
        create_archive(user)

        flash(f'{deleted_count} files successfuly deleted.', 'success')
        if deleted_count < len(file_ids):
            flash(f'{len(file_ids - deleted_count)} files could not be deleted.', 'error')
    else:
        flash('Could not complete operation, no files deleted.', 'error')

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
        flash(f'File not found: id={file_id}', 'error')
        return jsonify({'error': 'File not found'}), 404

    file_name, file_path = file_data
    if file_path == '/':
        file_path = get_user_tree_path(user)
    else:
        file_path = os.path.join(get_user_tree_path(user), file_path.lstrip('/'))
        print(file_path)

    store_logger.info(f'User {current_user.username} downloaded file: <store:{user.username}>{file_path}')

    return send_from_directory(file_path, file_name, as_attachment=True)


@datastore.route('/rename', methods=['POST'])
@login_required
def rename_file():
    user_id = request.json.get('user_id')
    user = get_user_by_id(user_id)

    metadata = UserMetadata(get_metadb_path(user))
    file_id = request.json.get('file_id')
    file_data = metadata.get_file_by_id(file_id)

    if not file_data:
        flash(f'File not found: id={file_id}', 'error')
        return jsonify({'error': 'File not found'}), 404

    if not evaluate_write_permission(current_user, file_data.__dict__):
        flash(f'No write permission granted for {file_data.filename}', 'error')
        return jsonify({'error': f'No write permission granted for file {file_data.filename}'}), 403

    if file_data.path == '/':
        current_path = get_user_tree_path(user)
    else:
        current_path = os.path.join(get_user_tree_path(user), file_data.path.lstrip('/'))

    current_file = os.path.join(current_path, file_data.filename)

    new_name = request.json.get('new_name').strip()

    if not new_name:
        flash('No name given during file rename', 'error')
        return jsonify({'error': 'No name given'}), 400

    # TODO: support directory rename
    new_file = os.path.join(current_path, new_name)

    os.rename(current_file, new_file)
    metadata.rename_file(new_name, file_data.path, file_id)

    store_logger.info(f'User {current_user.username} renamed file: {current_file} to: {new_file}')

    flash('File successfully renamed', 'success')
    return jsonify({'success': 'File renamed successfully'}), 200


@datastore.route('set-group', methods=['POST'])
@login_required
def set_file_group():
    user_id = request.json.get('user_id')
    user = get_user_by_id(user_id)

    metadata = UserMetadata(get_metadb_path(user))
    file_id = request.json.get('file_id')
    file_data = metadata.get_file_by_id(file_id)

    group = request.json.get('group')

    if not file_data:
        flash('File not found', 'error')
        return jsonify({'error': 'File not found'}), 404

    if evaluate_exec_permission(current_user, file_data.__dict__):
        metadata.set_file_group(file_id, group)
        flash(f'File group has been changed to {group} for file: {file_data.filename}', 'success')
        return jsonify({'success': 'File group changed successfully'}), 200
    else:
        flash(f'Execute permission not granted for {user.username} to file: {file_data.name}')
        return jsonify({'error': 'Permission not granted'}), 403


@datastore.route('set-perms', methods=['POST'])
@login_required
def set_file_perms():
    user_id = request.json.get('user_id')
    user = get_user_by_id(user_id)

    metadata = UserMetadata(get_metadb_path(user))
    file_id = request.json.get('file_id')
    file_data = metadata.get_file_by_id(file_id)

    perms = request.json.get('perms')

    if not file_data:
        flash('File not found', 'error')
        return jsonify({'error': 'File not found'}), 404

    if not perms:
        flash('Permissions not found', 'error')
        return jsonify({'error': 'Permissions not given'}), 400

    if evaluate_exec_permission(current_user, file_data.__dict__):
        metadata.set_file_perms(file_id, perms)
        flash(f'File permissions have been changed to {perms} for file: {file_data.filename}', 'success')
        return jsonify({'success': 'File permissions changed successfully'}), 200
    else:
        flash(f'Execute permission not granted for {user.username} to file: {file_data.name}')
        return jsonify({'error': 'Permission not granted'}), 403


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
        file['permissions'] = octal_to_string(file['permissions'], dir=file['is_directory'])

    users_list = [(user['id'], user['username']) for user in list_users()]
    shareform = SharedFilesForm(owner_choices=users_list)
    folderform = NewFolderForm()

    if shareform.validate_on_submit():
        return redirect(url_for('/store.get_shared_fs', user_id=shareform.owner.data))

    if folderform.validate_on_submit():
        folder_name = secure_filename(folderform.name.data)
        create_folder(folder_name=folder_name, folder_perms=folderform.perms.data, path=current_path)
        return redirect(request.url)

    return render_template(
        'file-viewer.html',
        file_list=file_list,
        dir_list=dir_list,
        current_path=current_path,
        archive_list=archive_list,
        shareform=shareform,
        folderform=folderform
    )
