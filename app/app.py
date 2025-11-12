import os

from flask import render_template, jsonify

from module.datastore import datastore
from module.auth import auth, create_admin_user
from module.util import DATABASE_PATH, app, db
import psutil

if not os.path.exists(DATABASE_PATH):
    os.makedirs(DATABASE_PATH)

app.register_blueprint(datastore, url_prefix='/store')
app.register_blueprint(auth, url_prefix='/auth')

app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(DATABASE_PATH, 'nasinfo.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'os3N95B6Z9cs'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db.init_app(app)


@app.route('/')
def home():
    return render_template('home.html', files_num=42)


@app.route('/system_perf')
def system_perf():
    # this code will be changed later
    cpu_usage = psutil.cpu_percent()
    disk_usage = psutil.disk_usage('/')
    # in GB
    total = f"{disk_usage.total / (1024**3):.2f}"
    used = f"{disk_usage.used / (1024**3):.2f}"
    free = f"{disk_usage.free / (1024**3):.2f}"
    disk_percent = disk_usage.percent
    sys_logs = ["log0", "log1", "log2"]

    return render_template('system_perf.html', cpu_usage=cpu_usage, total=total, used=used, free=free, disk_percent=disk_percent, sys_logs=sys_logs)


@app.route('/system_stats')
def generate_sys_stats():
    cpu_usage = psutil.cpu_percent()
    disk_usage = psutil.disk_usage('/')
    total = f"{disk_usage.total / (1024**3):.2f}"
    used = f"{disk_usage.used / (1024**3):.2f}"
    free = f"{disk_usage.free / (1024**3):.2f}"
    disk_percent = disk_usage.percent
    sys_logs = ["log0", "log1", "log2"]

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

    app.run(debug=True)
