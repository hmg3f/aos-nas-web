from flask import Flask, render_template, url_for
from datastore import datastore

app = Flask(__name__)
app.register_blueprint(datastore, url_prefix='/store')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/create')
def create_user():
    return render_template('create.html')

if __name__ == '__main__':
    app.run(debug=True)
