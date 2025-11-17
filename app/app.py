import os
import psutil

from flask import Flask, render_template, jsonify
from flask_login import LoginManager

from module.datastore import datastore
from module.auth import User, auth, create_admin_user, get_total_files_num
from module.util import DATABASE_PATH, db

if not os.path.exists(DATABASE_PATH):
    os.makedirs(DATABASE_PATH)

app = Flask(__name__)

app.register_blueprint(datastore, url_prefix='/store')
app.register_blueprint(auth, url_prefix='/auth')

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DATABASE_PATH, 'nasinfo.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'os3N95B6Z9cs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db.init_app(app)

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


@app.route('/')
def home():
    return render_template('home.html', files_num=get_total_files_num())


@app.route('/system_perf')
def system_perf():
    return render_template('system_perf.html')


@app.route('/system_stats')
def generate_sys_stats():
    cpu_usage = psutil.cpu_percent()
    disk_usage = psutil.disk_usage('/')
    total = f"{disk_usage.total / (1024**3):.2f}"
    used = f"{disk_usage.used / (1024**3):.2f}"
    free = f"{disk_usage.free / (1024**3):.2f}"
    disk_percent = disk_usage.percent

    try:
        with open('log/auth.log', 'r') as log:
            auth_log = log.readlines()
    except FileNotFoundError:
        print("FILENOTFOUND0")
        auth_log = 'No data'

    try:
        with open('log/store.log', 'r') as log:
            store_log = log.readlines()
    except FileNotFoundError:
        print("FILENOTFOUND1")
        store_log = 'No data'

    sys_logs = {'auth': auth_log, 'store': store_log}

    stats = {
        "success": "System stats retrieved successfully.",
        "data": {
            "cpu": cpu_usage,
            "disk": disk_usage,
            "total": total,
            "used": used,
            "free": free,
            "percent": disk_percent,
            "logs": sys_logs
        }
    }
    return jsonify(stats)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()

    app.run(host='0.0.0.0', port=8000)
