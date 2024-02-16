import errno
from flask import Flask, flash, render_template, session, url_for, request, redirect, make_response
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired, Length
from flask_socketio import SocketIO, emit
import datetime
import os
from dotenv import load_dotenv
from colorama import Fore, Style

load_dotenv()
db = SQLAlchemy()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('KRGCHAT_DATABASE_URL')
app.config["SECRET_KEY"] = os.environ.get('KRGCHAT_SECRET_KEY')
bootstrap = Bootstrap5(app)
socket = SocketIO(app)
db.init_app(app)

online_members = {}


class FormUsername(FlaskForm):
    username = StringField("", validators=[InputRequired(), Length(max=20)], render_kw={'autofocus': True})
    submit = SubmitField("Tovább")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String, nullable=False)
    time = db.Column(db.String, nullable=False)
    sender = db.Column(db.String, nullable=False)


with app.app_context():
    db.create_all()


@app.route("/", methods=['GET', 'POST'])
def home():
    username = request.cookies.get('username', '')
    if not username:
        return redirect(url_for('set_username'))
    if username in online_members.values():
        return redirect(url_for('set_username'))
    messages = db.session.query(Message).all()
    return render_template('index.html', messages=messages, username=username)


@app.route("/set-username", methods=["GET", "POST"])
def set_username():
    if request.method == "POST":
        username = request.form["username"]
        if len(username) > 20:
            return render_template('name.html', form=FormUsername(), error='A felhasználónév 20 karakternél nem lehet hosszabb.')
        if username in online_members.values():
            return render_template('name.html', form=FormUsername(), error='Valaki más is ezt a felhasználónevet használja.')
        response = make_response(redirect(url_for('home')))
        response.set_cookie('username', username, max_age=31536000)
        return response

    return render_template('name.html', form=FormUsername())


@app.template_filter('format_date')
def format_date_filter(str_date):
    datetime_object = datetime.datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")
    return datetime_object.strftime("%m-%d %H:%M")


@socket.on('message')
def hangle_msg(msg):
    print(online_members)
    time = datetime.datetime.now().replace(microsecond=0)
    new_message = Message(
        message=msg['message'],
        time=time,
        sender=msg['username']
    )
    db.session.add(new_message)
    db.session.commit()
    emit('message', {
        'data': 'new message',
        'message': msg['message'],
        'username': msg['username'],
        'time': format_date_filter(str(time))
    }, broadcast=True)


@socket.on('connect')
def connect():
    session_id = request.sid
    username = request.cookies.get('username', '')
    online_members[session_id] = username
    print(f'newly joined user sid: {Fore.CYAN + session_id + Style.RESET_ALL}')
    print(f'newly joined user: {username}')


@socket.on('disconnect')
def disconnect():
    session_id = request.sid
    username = request.cookies.get('username', '')
    try:
        online_members.pop(session_id)
    except KeyError:
        print('keyerror in deleting user from online members')
    print(f'user disconnected: {Fore.CYAN + session_id + Style.RESET_ALL}')
    print(f'left user: {username}')


app.jinja_env.filters['format_date'] = format_date_filter

if __name__ == "__main__":
    socket.run(app, debug=True, host='192.168.1.82', port=8080)
