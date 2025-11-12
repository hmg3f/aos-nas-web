from flask import Blueprint, render_template, url_for, redirect, flash, jsonify, request
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField, BooleanField
from wtforms.validators import InputRequired, Length, EqualTo, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from module.util import DATABASE_PATH, app, db, auth_logger

import hashlib
import time
import os

auth = Blueprint('/auth', __name__)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "/auth.login"


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user.enabled:
        return user
    else:
        return None


def gen_quota_selections(quotas):
    return [(None, 'None')] + [(size, size) for size in quotas]


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    quota = db.Column(db.String, nullable=True)
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


@auth.route('/login', methods=['GET', 'POST'])
def login():
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

    return render_template('account.html', form=form)


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

        user_dir = m.hexdigest()[:5]
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


@auth.route('/delete')
@login_required
def delete_user():
    current_user.enabled = False
    db.session.commit()
    logout_user()
    flash('Your account has been deleted successfully.', 'success')

    return redirect(url_for('home'))


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
                          quota=None,
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
    users_list = User.query.filter(
        ~User.flags.op('&')(User.HIDDEN)
    ).filter(
        User.id != current_user.id
    ).all()

    users_data = []
    for user in users_list:
        print(f'HIDDEN_FLAG: {user.has_flag(User.HIDDEN)}\nADMIN_FLAG: {user.has_flag(User.ADMIN)}\nFLAGS: {user.flags}')
        users_data.append({
            'id': user.id,
            'username': user.username,
        })

    return users_data


# TODO: allow admin to create new admin accounts
@auth.route('/admin/create-user', methods=['POST'])
@login_required
def admin_create_user():
    if current_user.username not in ['admin', 'root']:

        return jsonify({'error': 'Insufficient permissions'}), 403

    data = request.get_json()

    return jsonify({'success': True})
