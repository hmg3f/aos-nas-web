import os
import subprocess
import sqlite3
import borgapi

from flask import Blueprint

datastore= Blueprint('/store', __name__)

borg_api = borgapi.BorgAPI(defaults={}, options={})
borg_api.set_environ(BORG_PASSPHRASE="pass")

DATA_STORE_DIR = '/opt/store'

def get_user_store_path(username):
    return os.path.join(DATA_STORE_DIR, username)

@datastore.route('/user/create')
def create_user(username):
    user_dir = os.path.join(DATA_STORE_DIR, username)
    
    repo_path = os.path.join(user_dir, 'repo')
    stage_path = os.path.join(user_dir, 'stage')
    mount_path = os.path.join(user_dir, 'mount')

    if not os.path.exists(repo_path):
        borg_api.init(repo_path, make_parent_dirs=True)

    if not os.path.exists(stage_path):
        os.makedir(stage_path)

    if not os.path.exists(mount_path):
        os.makedir(mount_path)
        
def login_user(username):
    # stage filesystem
    pass

def logout_user(username):
    # stage filesystem and other cleanup tasks
    pass

def add_file(username, path, file, meta):
    user_dir = os.path.join(DATA_STORE_DIR, username)
    stage_path = os.path.join(user_dir, 'stage')
    file_path = os.path.join(stage_path, path, file)

    if not os.path.exists(stage_path):
        raise Exception()

    with open(file_path, 'w') as fd:
        fd.write(file)

    

    
