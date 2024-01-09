from flask import Flask, render_template, url_for, request, redirect
from flask_bootstrap import Bootstrap5
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired
from flask_socketio import SocketIO, emit
import datetime
import os

db = SQLAlchemy()
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get('DATABASE_URL')
app.config["SECRET_KEY"] = os.environ.get('SECRET')
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///messages.db'
app.config["SECRET_KEY"] = 'uasyvdfuyg4378t4nve8wuohrnfvy23vjdhs'
bootstrap = Bootstrap5(app)
socket = SocketIO(app)
db.init_app(app)


class FormMessage(FlaskForm):
    message = StringField("", validators=[DataRequired()], render_kw={'autofocus': True})
    send = SubmitField("Küldés")


class FormUsername(FlaskForm):
    username = StringField("", validators=[DataRequired()], render_kw={'autofocus': True})
    submit = SubmitField("Tovább")


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String, nullable=False)
    time = db.Column(db.String, nullable=False)
    sender = db.Column(db.String, nullable=False)


with app.app_context():
    db.create_all()


@app.route("/", methods=["GET", "POST"])
def set_username():
    if request.method == "POST":
        return redirect(url_for('home', username=request.form["username"]))

    return render_template('name.html', form=FormUsername())


@app.route("/<username>")
def home(username):
    messages = db.session.query(Message).all()
    return render_template('index.html', messages=messages, form=FormMessage(), username=username)


@app.route("/send_message/<username>", methods=["GET", "POST"])
def send_message(username):
    new_record = Message(
        message=request.form["message"],
        time=datetime.datetime.now().replace(microsecond=0),
        sender=username
    )
    db.session.add(new_record)
    db.session.commit()
    emit('message', {'data': 'new message sent!'})
    return redirect(url_for('home', username=username))


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
    socket.run(app, host='0.0.0.0', port=8080)
