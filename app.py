from flask import Flask
from datetime import datetime
import os

import prompts as p
from text_generation import TextGenerationGCP

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
  
  tg = TextGenerationGCP()
  today = datetime.today()

  if today.date() == birthday_datetime.date():
    birthday_prompt = p.birthday
    birthday_haiku = tg.generate_text(contents=birthday_prompt)

    return f"""<body>
  <p>Today is your birthday! Good for you.</p>
  <p>"{birthday_haiku}"</p>
  <img src="https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExMDJqMTRuanRocnhxazE3cW05Y2dtNGhpNnJuZ3IwaWxlYW42M2t0bSZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/Qvns6NmhC1MBLKGbL1/giphy.gif"/>
</body>"""

  else:
    not_birthday_prompt = p.not_birthday
    not_birthday_haiku = tg.generate_text(contents=not_birthday_prompt)
    return f"""<body>
  <p>Today is not your birthday.</p>  
  <p>"{not_birthday_haiku}"</p>
  <img src="https://media3.giphy.com/media/v1.Y2lkPTc5MGI3NjExanJkMmUyeDN0ZnI4bDNzZDM0NTk4N3J5M3hvNDk3d2RvcTN3cWU2ayZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/LpQuxhwDhzLCEKVYFh/giphy.gif"/>
</body>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)