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

@app.route("/section_test", methods=["GET"])
def section_test():
    if "user" not in session:
        return redirect("/")

    category = request.args.get('category')

    if not category:
        # 章選択画面を表示
        chapters = list(range(1, 17))  # 1章から16章 test
        return render_template("section_test.html", chapters=chapters)

    # 問題リスト表示
    if category == 'all':
        q_list = Question.query.filter(Question.category.like('section_%')).all()
    else:
        q_list = Question.query.filter_by(category=category).all()

    if not q_list:
        return "その範囲の問題はDBにありません"  # or redirect with a message

    return render_template(
        "section_test.html",
        questions=q_list,
        category=category,
        total=len(q_list)
    )

@app.route('/submit_section', methods=['POST'])
def submit_section():
    if 'user' not in session:
        return redirect('/')

    category = request.form.get('category')
    results = []
    score = 0

    if category == 'all':
        q_list = Question.query.filter(Question.category.like('section_%')).all()
    else:
        q_list = Question.query.filter_by(category=category).all()

    for q in q_list:
        selected_choice_val = request.form.get(f'question_{q.id}')
        
        selected_choice_index = None # 1-based index
        user_answer_text = "未回答" # Default for unanswered

        if selected_choice_val is not None:
            selected_choice_index = int(selected_choice_val)
            choices = [q.choice1, q.choice2, q.choice3, q.choice4]
            user_answer_text = choices[selected_choice_index - 1] # Convert 1-based to 0-based for list access

        is_correct = (selected_choice_index == q.correct)

        if is_correct:
            score += 1
        
        results.append({
            'question': q,
            'user_answer': user_answer_text,
            'selected_choice_index': selected_choice_index, # Add selected choice index
            'correct_choice_index': q.correct, # Add correct choice index
            'is_correct': is_correct
        })
    
    total = len(q_list)

    return render_template('result.html', results=results, score=score, total=total, test_type='section')

@app.route("/practice", methods=["GET"])
def practice():
    if "user" not in session:
        return redirect("/")
    
    all_questions = Question.query.all()
    
    # Ensure there are at least 10 questions to choose from
    num_questions = min(len(all_questions), 10)
    if num_questions == 0:
        return "問題がDBにありません"

    q_list = random.sample(all_questions, num_questions)

    return render_template(
        "practice_test.html",
        questions=q_list,
        total=len(q_list)
    )

@app.route('/submit_practice', methods=['POST'])
def submit_practice():
    if 'user' not in session:
        return redirect('/')

    results = []
    score = 0
    
    # Get all question IDs submitted from the form
    submitted_q_ids = [key.split('_')[1] for key in request.form if key.startswith('question_')]
    q_list = Question.query.filter(Question.id.in_(submitted_q_ids)).all()

    for q in q_list:
        selected_choice_val = request.form.get(f'question_{q.id}')
        
        selected_choice_index = None # 1-based index
        user_answer_text = "未回答" # Default for unanswered

        if selected_choice_val is not None:
            selected_choice_index = int(selected_choice_val)
            choices = [q.choice1, q.choice2, q.choice3, q.choice4]
            user_answer_text = choices[selected_choice_index - 1]

        is_correct = (selected_choice_index == q.correct)

        if is_correct:
            score += 1
        
        results.append({
            'question': q,
            'user_answer': user_answer_text,
            'selected_choice_index': selected_choice_index,
            'correct_choice_index': q.correct,
            'is_correct': is_correct
        })
    
    total = len(q_list)

    return render_template('result.html', results=results, score=score, total=total, test_type='practice')

@app.route("/admin")
def admin():
    if session.get("user") != "admin@example.com":
        return redirect("/")
    return render_template("admin.html")

if __name__ == "__main__":
    app.run(debug=True)