from flask import Blueprint, render_template, url_for, redirect, flash, jsonify, request
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField
from wtforms.validators import InputRequired, Length, EqualTo, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from module.util import DATABASE_PATH, app, db, auth_logger, octal_to_dict, get_metadb_path, convert_to_bytes
from module.metadata import UserMetadata

import hashlib
import time
import os
import shutil

auth = Blueprint('/auth', __name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/auth.login"


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and user.enabled:
        return user
    else:
        return None


def gen_quota_selections(quotas):
    return [(0, 'None')] + [(convert_to_bytes(size), size) for size in quotas]


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    quota = db.Column(db.Integer)
    store_path = db.Column(db.String, nullable=False, unique=True)
    archive_state = db.Column(db.String, nullable=True, default=None)
    num_files = db.Column(db.Integer, nullable=False, default=0)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    flags = db.Column(db.Integer, nullable=False, default=0)
    user_groups = db.Column(db.String, nullable=False)

    # Flags
    ADMIN = 1
    HIDDEN = 2

    def set_flag(self, flag):
        if not self.flags:
            self.flags = 0
        self.flags |= flag

    def unset_flag(self, flag):
        if not self.flags:
            self.flags = 0
        self.flags &= ~flag

    def has_flag(self, flag):
        if not self.flags:
            self.flags = 0
        return (self.flags & flag) > 0


class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(),
                                       Length(min=2, max=20)],
                           render_kw={'placeholder': 'Username'})
    password = PasswordField(validators=[InputRequired(),
                                         Length(min=4, max=40)],
                             render_kw={'placeholder': 'Password'})
    quota = SelectField('Quota', choices=gen_quota_selections(['100M', '512M', '1G', '5G']))
    hidden = BooleanField('Hidden', default=False)
    submit = SubmitField('Create Account')


class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(),
                                       Length(min=2, max=20)],
                           render_kw={'placeholder': 'Username'})
    password = PasswordField(validators=[InputRequired(),
                                         Length(min=4, max=40)],
                             render_kw={'placeholder': 'Password'})
    submit = SubmitField('Login')


class AccountManagementForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=2, max=20)])
    current_password = PasswordField('Current Password', validators=[InputRequired(), Length(min=4, max=40)])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=4, max=40)])
    confirm_password = PasswordField('Confirm New Password', validators=[EqualTo('new_password', message='Passwords must match')])
    submit = SubmitField('Update Account')


def get_user_by_id(user_id):
    return User.query.filter_by(id=user_id).first()


def evaluate_permission(user, file, perm):
    user_groups = user.user_groups.split(',')
    file_perms = file['permissions']
    file_owner = file['owner']
    file_group = file['file_group']

    perms_dict = octal_to_dict(int(file_perms))

    if user.has_flag(User.ADMIN):
        flash('File permissions overidden: Admin granted access', 'error')
        return True

    if user.id == file_owner:
        if perms_dict['owner'][perm]:
            return True
        else:
            flash('File permissions overidden: Owner granted access', 'error')
            return True

    if perms_dict['all'][perm]:
        return True

    if file_group in user_groups:
        if perms_dict['group'][perm]:
            return True

    return False


def evaluate_read_permission(user, file):
    return evaluate_permission(user, file, 'read')


def evaluate_write_permission(user, file):
    return evaluate_permission(user, file, 'write')


def evaluate_exec_permission(user, file):
    return evaluate_permission(user, file, 'execute')


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('/store.file_viewer'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                if user.enabled:
                    login_user(user)
                    auth_logger.info(f'User logged in: {user.username}')

                    return redirect(url_for('/store.file_viewer'))
                else:
                    auth_logger.warn(f'Login attempted for disabled account: {user.username}')
                    flash('Your account is disabled. Please contact support.', 'error')
            else:
                auth_logger.warn(f'Login failed for: {user.username}')
                flash('Invalid username or password.', 'error')
        else:
            auth_logger.warn(f'Login failed for: {form.username.data}')
            flash('Invalid username or password.', 'error')

    return render_template('login.html', form=form)


@auth.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    auth_logger.info(f'User logged out: {current_user.username}')
    logout_user()
    return redirect(url_for('home'))


@auth.route('/account', methods=['GET', 'POST'])
@login_required
def account_manager():
    form = AccountManagementForm()

    if form.validate_on_submit():
        # Handle Username change
        print(f"FORM USERNAME DATA: {form.username.data}")
        if form.username.data != current_user.username:
            current_user.username = form.username.data

        # Handle Password change
        if form.new_password.data:
            if check_password_hash(current_user.password, form.current_password.data):
                current_user.password = generate_password_hash(form.new_password.data)
            else:
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('/auth.account_manager'))

        db.session.commit()
        flash('Your account has been updated.', 'success')
        return redirect(url_for('/auth.account_manager'))

    return render_template('account.html',
                           form=form,
                           users_list=list_users(),
                           groups_list=current_user.user_groups.split(','))


@auth.route('/create', methods=['GET', 'POST'])
def create_user():
    form = RegisterForm()

    if form.validate_on_submit():
        # Check if the username already exists
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
            flash('Username already taken. Please choose a different one.', 'error')
            return redirect(url_for('/auth.create_user'))

        password_hash = generate_password_hash(form.password.data)

        m = hashlib.sha256()
        m.update(str(round(time.time())).encode('utf-8'))
        m.update(form.username.data.encode('utf-8'))

        user_dir = m.hexdigest()[:10]
        store_path = os.path.join(DATABASE_PATH, user_dir)

        user = User(username=form.username.data,
                    password=password_hash,
                    quota=form.quota.data,
                    store_path=store_path,
                    user_groups=f'{form.username.data},users')
        db.session.add(user)

        if form.hidden.data:
            user.set_flag(User.HIDDEN)

        db.session.commit()

        login_user(user)

        auth_logger.info(f'User created: {user.username}')

        return redirect(url_for('/store.file_viewer'))

    return render_template('create.html', form=form)


@auth.route('/group/add', methods=['POST'])
@login_required
def add_group():
    group = request.json.get('group')
    groups = current_user.user_groups.split(',')

    if group is None:
        flash('No group found', 'error')
        return jsonify({'error': 'Group not found'}), 404

    if group not in groups:
        if group.isalpha():
            flash(f'Added {current_user.username} to group: {group}', 'success')
            groups += [group]
            current_user.user_groups = ','.join(groups)
            db.session.commit()
        else:
            flash(f'Could not add {group} to groups, invalid character', 'error')
    else:
        flash(f'{current_user.username} is already a member of {group}', 'error')

    return jsonify({'success': 'User added to group'}), 200


@auth.route('/group/remove', methods=['POST'])
@login_required
def remove_group():
    group = request.json.get('group')
    groups = current_user.user_groups.split(',')

    print(group)

    if group is None:
        flash('No group found', 'error')
        return jsonify({'error': 'Group not found'}), 404

    if group in groups:
        current_user.user_groups = ','.join([g for g in groups if g != group])
        db.session.commit()
        flash(f'Removed {current_user.username} from group: {group}', 'success')
    else:
        flash(f'{current_user.username} is not a member of {group}', 'error')

    return jsonify({'success': 'User removed from group'}), 200


@auth.route('/disable')
@login_required
def disable_current_user():
    current_user.enabled = False
    db.session.commit()
    logout_user()
    flash('Your account has been deleted successfully.', 'success')

    return redirect(url_for('home'))


@auth.route('/admin/disable/<userid>')
@login_required
def disable_user(userid):
    if current_user.has_flag(User.ADMIN):
        user = get_user_by_id(userid)
        user.enabled = False
        db.session.commit()
        flash(f'Account <{user.username}> disabled successfully.', 'success')

    return redirect(request.referrer)


@auth.route('/admin/enable/<userid>')
@login_required
def enable_user(userid):
    if current_user.has_flag(User.ADMIN):
        user = get_user_by_id(userid)
        user.enabled = True
        db.session.commit()
        flash(f'Account <{user.username}> enabled successfully.', 'success')

    return redirect(request.referrer)


@auth.route('/admin/delete/<userid>')
@login_required
def delete_user(userid):
    if current_user.has_flag(User.ADMIN):
        user = get_user_by_id(userid)
        store_path = user.store_path

        User.query.filter(User.id == user.id).delete()
        shutil.rmtree(store_path)

        db.session.commit()
        flash(f'Account <{user.username}> deleted successfully.', 'success')

    return redirect(request.referrer)


def create_admin_user():
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin')
        password_hash = generate_password_hash(admin_password)

        m = hashlib.sha256()
        m.update(str(round(time.time())).encode('utf-8'))
        m.update('admin'.encode('utf-8'))

        user_dir = m.hexdigest()[:5]
        store_path = os.path.join(DATABASE_PATH, user_dir)

        admin_user = User(username='admin',
                          password=password_hash,
                          quota=0,
                          store_path=store_path,
                          user_groups='admin')

        admin_user.set_flag(User.ADMIN)
        admin_user.set_flag(User.HIDDEN)
        db.session.add(admin_user)
        db.session.commit()

        auth_logger.info(f'Admin user created: {admin_user.username}')


@auth.route('/list-users')
@login_required
def list_users():
    if current_user.has_flag(User.ADMIN):
        users_list = User.query.filter(User.id != current_user.id).all()
    else:
        users_list = User.query.filter(
            ~User.flags.op('&')(User.HIDDEN)
        ).filter(
            User.enabled
        ).filter(
            User.id != current_user.id
        ).all()

    users_data = []
    for user in users_list:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'enabled': user.enabled
        })

    return users_data


@auth.route('/stats/file_count/<user_id>')
def file_count(user_id):
    user = get_user_by_id(user_id)

    metadata = UserMetadata(get_metadb_path(user))

    return metadata.get_num_files()


@auth.route('/stats/total_files')
def get_total_files_num():
    users = User.query.all()
    total_files = 0

    for user in users:
        total_files += file_count(user.id)

    return total_files


# TODO: allow admin to create new admin accounts
@auth.route('/admin/create-user', methods=['POST'])
@login_required
def admin_create_user():
    if not current_user.has_flag(User.ADMIN):
        return jsonify({'error': 'Insufficient permissions'}), 403

    data = request.get_json()

    return jsonify({'success': True})
