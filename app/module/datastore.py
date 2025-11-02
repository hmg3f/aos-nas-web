import os
import subprocess
import sqlite3
import borgapi

import datetime
from flask import Blueprint
from flask_login import login_required, current_user

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

        current_time = datetime.datetime.now()
        stage_path = get_stage_path(user)
        user.archive_state = current_time.strftime(f"{path}::%Y-%m-%d_%H:%M:%S")
        borg_api.create(user.archive_state, stage_path)
        
        db.session.commit()
        
    return path

def get_stage_path(user):
    path = os.path.join(user.store_path, 'stage')
    if not os.path.exists(path):
        os.makedirs(path)
        
    return path

def get_mount_path(user):
    path = os.path.join(user.store_path, 'mount')
    if not os.path.exists(path):
        os.makedirs(path)
        
    return path

def select_archive_or_create(user):
    pass

@datastore.route('/retrieve')
@login_required
def retrieve_user_store():
    if current_user.is_authenticated:
        stage_path = get_stage_path(current_user)
        
        if os.path.ismount(stage_path):
            return os.listdir(stage_path)
        else:
            repo_path = get_repo_path(current_user)
            
            if not current_user.archive_state:
                select_archive_or_create(current_user)
            
            borg_api.mount(current_user.archive_state, stage_path)
            return os.listdir(stage_path)

def add_file(user, file, meta):

    if not os.path.exists(stage_path):
        raise Exception()

    with open(file_path, 'w') as fd:
        fd.write(file)

    

    
