from flask import render_template, url_for, redirect
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

from module.datastore import datastore, retrieve_user_store
from module.util import convert_to_bytes, app, db, bcrypt

import os
import hashlib
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, 'store')

if not os.path.exists(DATABASE_PATH):
    os.makedirs(DATABASE_PATH)

app.register_blueprint(datastore, url_prefix='/store')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATABASE_PATH, 'nasinfo.db')}'
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

# def gen_quota_selections(quotas):
#     return [(None, 'None')] + [(convert_to_bytes(size), size) for size in quotas]

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
                                       Length(min=2, max=20)],
                           render_kw={'placeholder': 'Username'})
    password = PasswordField(validators=[InputRequired(),
                                         Length(min=4, max=40)],
                           render_kw={'placeholder': 'Password'})
    submit = SubmitField('Login')

@app.route('/')
def home():
    return render_template('home.html', files_num=42)

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
    file_list = retrieve_user_store()
    return render_template('file-viewer.html', file_list=file_list)

@app.route('/create', methods=['GET', 'POST'])
def create_user():
    form = RegisterForm()

    if form.validate_on_submit():
        password_hash = bcrypt.generate_password_hash(form.password.data)
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

        return redirect(url_for('login'))
    
    return render_template('create.html', form=form)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        
    app.run(debug=True)
