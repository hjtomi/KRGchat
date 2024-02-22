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
from hashlib import sha256
from functools import wraps

load_dotenv()
db = SQLAlchemy()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('KRGCHAT_DATABASE_URL')
app.config["SECRET_KEY"] = os.environ.get('KRGCHAT_SECRET_KEY')
bootstrap = Bootstrap5(app)
socket = SocketIO(app)
db.init_app(app)

online_members = {}
PASSWORD_HASHED = sha256(os.environ.get('PASSWORD', '').encode('UTF-8')).hexdigest()
WAITING_TIME = 30
USERNAME_COOKIE_EXPIRE_SECONDS = 31536000  # 1 year
PASSWORD_COOKIE_EXPIRE_SECONDS = 1209600  # 2 weeks


class FormUsername(FlaskForm):
    username = StringField("", validators=[InputRequired(), Length(max=20)], render_kw={'autofocus': True})
    submit = SubmitField("Tovább")


class FormPassword(FlaskForm):
    password = StringField('', render_kw={'autofocus': True})
    submit = SubmitField('Belépés')


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String, nullable=False)
    time = db.Column(db.String, nullable=False)
    sender = db.Column(db.String, nullable=False)


with app.app_context():
    db.create_all()


def check_lockout(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        lockout_until = session.get('lockout_until')
        if lockout_until:
            # Ensure lockout_until is timezone-naive for comparison
            if lockout_until.tzinfo is not None and lockout_until.tzinfo.utcoffset(lockout_until) is not None:
                # Convert to timezone-naive UTC datetime if it's timezone-aware
                lockout_until = lockout_until.replace(tzinfo=None)
                
            current_time = datetime.datetime.now()
            if lockout_until > current_time:
                # Calculate remaining lockout time
                remaining_seconds = int((lockout_until - current_time).total_seconds())
                return redirect(url_for('waiting_room'))
        return func(*args, **kwargs)
    return decorated_function


@app.route("/", methods=['GET', 'POST'])
@check_lockout
def home():
    username = request.cookies.get('username', '')
    password_cookie = request.cookies.get('password', '')
    if password_cookie != PASSWORD_HASHED:
        return redirect(url_for('password'))
    if not username:
        return redirect(url_for('set_username'))
    if username in online_members.values():
        return redirect(url_for('set_username'))
    messages = db.session.query(Message).all()
    return render_template('index.html', messages=messages, username=username)


@app.route("/set-username", methods=["GET", "POST"])
@check_lockout
def set_username():
    if request.method == "POST":
        username = request.form["username"]
        if len(username) > 20:
            return render_template('name.html', form=FormUsername(), error='A felhasználónév 20 karakternél nem lehet hosszabb.')
        if username in online_members.values():
            return render_template('name.html', form=FormUsername(), error='Valaki más is ezt a felhasználónevet használja.')
        response = make_response(redirect(url_for('home')))
        response.set_cookie('username', username, max_age=USERNAME_COOKIE_EXPIRE_SECONDS)
        return response

    return render_template('name.html', form=FormUsername())


@app.route("/password", methods=['GET', 'POST'])
@check_lockout
def password():
    if request.method == 'POST':
        given_pw = request.form['password']
        if sha256(given_pw.encode('UTF-8')).hexdigest() == PASSWORD_HASHED:
            response = make_response(redirect(url_for('home')))
            response.set_cookie('password', sha256(given_pw.encode('UTF-8')).hexdigest(), max_age=PASSWORD_COOKIE_EXPIRE_SECONDS)
            session.pop('lockout_until', None)
            return response
        else:
            session['lockout_until'] = datetime.datetime.now() + datetime.timedelta(seconds=WAITING_TIME)
            return redirect(url_for('waiting_room'))
    return render_template('password.html', form=FormPassword())


@app.route('/waiting-room', methods=['GET'])
def waiting_room():
    return render_template('waiting-room.html', waiting_time=WAITING_TIME)


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
