from flask import Flask, render_template, request, redirect, url_for, session
from database import db
from model import Question, User
import random

app = Flask(__name__)
app.secret_key = "test123"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

with app.app_context():
    db.create_all()

@app.route("/")
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return render_template("login.html", error="ログインに失敗しました")

        # Create new user
        new_user = User(email=email)
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/try_login", methods=["POST"])
def try_login():
    email = request.form.get("email")
    pw = request.form.get("password")

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(pw):
        session["user"] = user.email
        session["is_admin"] = user.is_admin
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
    
    # Get all question IDs that were part of the test, preserving order
    all_q_ids = request.form.get('all_q_ids').split(',')
    
    # Fetch the questions from the database
    questions_from_db = Question.query.filter(Question.id.in_(all_q_ids)).all()
    
    # The database query does not guarantee order, so we reorder them.
    # Create a mapping from ID to Question object
    question_map = {str(q.id): q for q in questions_from_db}
    
    # Re-order the questions based on the original ID list
    q_list = [question_map[qid] for qid in all_q_ids if qid in question_map]

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
    if not session.get("is_admin"):
        return redirect("/")
    return render_template("admin.html")

if __name__ == "__main__":
    app.run(debug=True)