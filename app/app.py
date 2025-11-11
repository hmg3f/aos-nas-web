import os

from flask import render_template

from module.datastore import datastore
from module.auth import auth, create_admin_user
from module.util import DATABASE_PATH, app, db

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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin_user()

    app.run(debug=True)
