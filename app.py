from flask import Flask, render_template, request, redirect, url_for, session
from database import db
from model import Question
import random

app = Flask(__name__)
app.secret_key = "test123"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

USERS = {
    "student@example.com": "pass123",
    "admin@example.com": "admin123"
}

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/try_login", methods=["POST"])
def try_login():
    email = request.form.get("email")
    pw = request.form.get("password")

    if email in USERS and USERS[email] == pw:
        session["user"] = email
        return redirect(url_for("home"))
    else:
        return render_template("login.html", error="ログインに失敗しました")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/home")
def home():
    if "user" not in session:
        return redirect("/")
    return render_template("home.html", user=session["user"])

@app.route("/material")
def material():
    if "user" not in session:
        return redirect("/")
    return render_template("material.html")

@app.route("/section_test", methods=["GET","POST"])
def section_test():
    if "user" not in session:
        return redirect("/")
    
    if request.method == "POST":
        answer = int(request.form.get("choice"))
        correct = int(request.form.get("correct"))
        result = (answer == correct)
        return redirect(url_for("result", ok=result))
    
    q_list = Question.query.filter_by(category="section").all()
    if not q_list:
        return "章末テスト用の問題がDBにありません"
    
    q = random.choice(q_list)
    
    return render_template(
        "section_test.html", 
        question=q.question, 
        choices=[q.choice1, q.choice2, q.choice3, q.choice4],
        correct=q.correct,
        )

@app.route("/practice", methods=["GET","POST"])
def practice():
    if "user" not in session:
        return redirect("/")
    
    if request.method == "POST":
        answer = int(request.form.get("choice"))
        correct = int(request.form.get("correct"))
        result = (answer == correct)
        return redirect(url_for("result", ok=result))
    
    q_list = Question.query.filter_by(category="practice").all()
    if not q_list:
        return "章末テスト用の問題がDBにありません"
    
    q = random.choice(q_list)

    return render_template(
        "practice.html", 
        question=q.question, 
        choices=[q.choice1, q.choice2, q.choice3, q.choice4],
        correct=q.correct,
        )

@app.route("/result")
def result():
    if "user" not in session:
        return redirect("/")
    ok = request.args.get("ok") == "True"
    return render_template("result.html",ok=ok)

@app.route("/admin")
def admin():
    if session.get("user") != "admin@example.com":
        return redirect("/")
    return render_template("admin.html")

if __name__ == "__main__":
    app.run(debug=True)