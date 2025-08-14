from flask import Flask
from datetime import datetime

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route(f"/api/birthday/<birthday>", methods=["GET"])
def is_birthday(birthday):
  try:
    birthday_datetime = datetime.strptime(birthday, "%Y-%m-%d")
  except:
    raise Exception("Not correct date format")

  today = datetime.today()
  if today.date() == birthday_datetime.date()
    return "<p>Today is your birthday! Good for you.</p>"
  else 
    return "<p>Today is not your birthday.</p>"
