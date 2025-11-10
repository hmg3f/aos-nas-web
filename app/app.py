from flask import render_template, url_for, redirect, flash
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import InputRequired, Length, EqualTo, Optional
from werkzeug.security import check_password_hash, generate_password_hash

from module.datastore import datastore, retrieve_user_store, list_archives
from module.util import app, db, bcrypt, auth_logger

import os
import hashlib
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'store')

if not os.path.exists(DATABASE_PATH):
    os.makedirs(DATABASE_PATH)

app.register_blueprint(datastore, url_prefix='/store')

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DATABASE_PATH, 'nasinfo.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'os3N95B6Z9cs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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

    # Flags
    ADMIN = 1

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
    

@app.route('/')
def home():
    return render_template('home.html', files_num=42)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                auth_logger.info(f'User logged in: {user.username}')
                
                return redirect(url_for('file_viewer'))
            else:
                auth_logger.warn(f'Login failed for: {user.username}')
                
    return render_template('login.html', form=form)


@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    auth_logger.info(f'User logged out: {current_user.username}')
    logout_user()
    return redirect(url_for('home'))


@app.route('/account', methods=['GET', 'POST'])
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
                return redirect(url_for('account_manager'))
        
        db.session.commit()
        flash('Your account has been updated.', 'success')
        return redirect(url_for('account_manager'))

    return render_template('account.html', form=form)


@app.route('/files', methods=['GET', 'POST'])
@login_required
def file_viewer():
    file_list = retrieve_user_store()
    archive_list = list_archives()
    return render_template('file-viewer.html', file_list=file_list, archive_list=archive_list)


@app.route('/create', methods=['GET', 'POST'])
def create_user():
    form = RegisterForm()

    if form.validate_on_submit():
        password_hash = generate_password_hash(form.password.data)
        
        m = hashlib.sha256()
        m.update(str(round(time.time())).encode('utf-8'))
        m.update(form.username.data.encode('utf-8'))
        
        user_dir = m.hexdigest()[:5]
        store_path = os.path.join(DATABASE_PATH, user_dir)
        
        user = User(username=form.username.data,
                    password=password_hash,
                    quota=form.quota.data,
                    store_path=store_path)
        db.session.add(user)
        db.session.commit()

        auth_logger.info(f'User created: {user.username}')

        return redirect(url_for('login'))
    
    return render_template('create.html', form=form)


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
                          flags=User.ADMIN)
        
        # admin_user.set_flag(User.ADMIN)
        db.session.add(admin_user)
        db.session.commit()
        
        auth_logger.info(f'Admin user created: {admin_user.username}')

        
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()
        
    app.run(debug=True)
