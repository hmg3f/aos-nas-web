from flask import Flask, render_template, url_for, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from flask_bcrypt import Bcrypt
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

from module.datastore import datastore

import os
import re

TEST_FILE_LIST=[('file1.txt', '12MB', '-rwxr-xr-x'), ('file2.txt', '230Kb', '-rwxr-xr-x')]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'store')

db = SQLAlchemy()

app = Flask(__name__)
app.register_blueprint(datastore, url_prefix='/store')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATABASE_PATH, 'users.db')}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'os3N95B6Z9cs'

db.init_app(app)

bcrypt = Bcrypt(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def convert_to_bytes(size_str):
    suffixes = {
        'B': 1,
        'K': 1024,
        'M': 1024 ** 2,
        'G': 1024 ** 3,
        'T': 1024 ** 4,
        'P': 1024 ** 5,
        'E': 1024 ** 6
    }

    match = re.match(r'(\d+(?:\.\d+)?)\s*([KMGTP])?', size_str.strip(), re.IGNORECASE)
    
    if not match:
        raise ValueError(f"Invalid size format: {size_str}")
    
    number = float(match.group(1))
    suffix = match.group(2).upper() if match.group(2) else 'B'
    
    if suffix not in suffixes:
        raise ValueError(f"Unsupported suffix: {suffix}")
    
    return int(number * suffixes[suffix])

def gen_quota_selections(quotas):
    return [(None, 'None')] + [(convert_to_bytes(size), size) for size in quotas]

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String, nullable=False)
    quota = db.Column(db.Integer, nullable=True)

    # @validates('quota')
    # def validate_quota(self, key, value):
    #     if value is not None and value < 0:
    #         raise ValueError(f'Quota cannot be negative: {value}')
    #     return value

class RegisterForm(FlaskForm):
    username = StringField(validators=[InputRequired(),
                                       Length(min=4, max=20)],
                           render_kw={'placeholder': 'Username'})
    password = PasswordField(validators=[InputRequired(),
                                         Length(min=4, max=40)],
                           render_kw={'placeholder': 'Password'})
    quota = SelectField('Quota', choices=gen_quota_selections(['100M', '512M', '1G', '5G']))
    submit = SubmitField('Create Account')

class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(),
                                       Length(min=4, max=20)],
                           render_kw={'placeholder': 'Username'})
    password = PasswordField(validators=[InputRequired(),
                                         Length(min=4, max=40)],
                           render_kw={'placeholder': 'Password'})
    submit = SubmitField('Login')

@app.route('/')
def home():
    return render_template('home.html', files_num=len(TEST_FILE_LIST))

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            if bcrypt.check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('file_viewer'))
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/files', methods=['GET', 'POST'])
@login_required
def file_viewer():
    return render_template('file-viewer.html', file_list=TEST_FILE_LIST)

@app.route('/create', methods=['GET', 'POST'])
def create_user():
    form = RegisterForm()

    if form.validate_on_submit():
        password_hash = bcrypt.generate_password_hash(form.password.data)
        user = User(username=form.username.data,
                    password=password_hash,
                    quota=form.quota.data)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for('login'))
    
    return render_template('create.html', form=form)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
    app.run(debug=True)
