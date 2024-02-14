from flask import Flask, render_template, url_for, request, redirect, make_response, flash
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import InputRequired, Length
from flask_socketio import SocketIO, emit
import datetime
import os
from dotenv import load_dotenv

load_dotenv()
db = SQLAlchemy()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('KRGCHAT_DATABASE_URL')
app.config["SECRET_KEY"] = os.environ.get('KRGCHAT_SECRET_KEY')
bootstrap = Bootstrap5(app)
socket = SocketIO(app)
db.init_app(app)


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
    messages = db.session.query(Message).all()
    return render_template('index.html', messages=messages, username=username)


@app.route("/set-username", methods=["GET", "POST"])
def set_username():
    if request.method == "POST":
        username = request.form["username"]
        if len(username) > 20:
            return render_template('name.html', form=FormUsername())
        response = make_response(redirect(url_for('home')))
        response.set_cookie('username', username, max_age=31536000)
        return response

    return render_template('name.html', form=FormUsername())

# Junk, not used (didnt delete because i am not 100% sure)
# @app.route("/send_message/<username>", methods=["GET", "POST"])
# def send_message(username):
#     new_record = Message(
#         message=request.form["message"],
#         time=datetime.datetime.now().replace(microsecond=0),
#         sender=username
#     )
#     db.session.add(new_record)
#     db.session.commit()
#     emit('message', {'data': 'new message sent!'})
#     return redirect(url_for('home', username=username))


@app.template_filter('format_date')
def format_date_filter(str_date):
    datetime_object = datetime.datetime.strptime(str_date, "%Y-%m-%d %H:%M:%S")
    return datetime_object.strftime("%m-%d %H:%M")


@socket.on('message')
def hangle_msg(msg):
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


app.jinja_env.filters['format_date'] = format_date_filter

if __name__ == "__main__":
    socket.run(app, debug=True, host='192.168.1.82', port=8080)
