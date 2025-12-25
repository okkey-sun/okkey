from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response, flash
from flask_migrate import Migrate
from database import db
from model import Question, User, QuizResult
import random
import json
import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from datetime import datetime, timedelta
from sqlalchemy import func, desc

app = Flask(__name__)
app.secret_key = "test123"

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///quiz.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JSON_AS_ASCII"] = False
db.init_app(app)
migrate = Migrate(app, db)

# トークン生成用のシリアライザ
serializer = URLSafeTimedSerializer(app.secret_key)

def send_verification_email(user_email, token_url):
    """
    認証メールを送信する関数
    """
    sender_email = os.environ.get('MAIL_ADDRESS')
    password = os.environ.get('MAIL_PASSWORD')

    if not sender_email or not password:
        print("Error: 環境変数 MAIL_ADDRESS または MAIL_PASSWORD が設定されていません。")
        return False

    subject = "【重要】登録確認メール"
    body = f"""
以下のリンクをクリックして、パスワード設定を完了してください。

{token_url}

リンクの有効期限は24時間です。
"""

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = user_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email send error: {e}")
        return False


@app.route("/")
def login():
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        # パスワード入力はまだ求めない

        # 既存ユーザーチェック
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # セキュリティ上は「送信しました」と出すのが良いが、今回はわかりやすくエラー表示
            return render_template("register.html", error="このメールアドレスは既に登録されています。")

        # 新規ユーザー作成（is_active=False, パスワード未設定）
        new_user = User(email=email, is_active=False)
        db.session.add(new_user)
        db.session.commit()

        # トークン生成（emailをシリアライズ）
        token = serializer.dumps(email, salt='email-confirm-salt')

        # 確認用URL生成
        # 指定されたURL形式を使用
        confirm_url = f"https://okkey.pythonanywhere.com/confirm/{token}"
        
        # デバッグ用：ローカルで確認しやすいようにコンソール出力
        print(f"DEBUG: Verification URL: {confirm_url}")

        # メール送信
        if send_verification_email(email, confirm_url):
            # 案内画面へ
            return render_template("email_sent.html")
        else:
            return render_template("register.html", error="メール送信に失敗しました。管理者にお問い合わせください。")

    return render_template("register.html")

@app.route("/confirm/<token>", methods=["GET", "POST"])
def confirm_email(token):
    try:
        # トークン検証（有効期限24時間 = 86400秒）
        email = serializer.loads(token, salt='email-confirm-salt', max_age=86400)
    except SignatureExpired:
        return "<h1>リンクの有効期限が切れています。もう一度登録手続きを行ってください。</h1>"
    except BadTimeSignature:
        return "<h1>無効なリンクです。</h1>"

    user = User.query.filter_by(email=email).first()
    if not user:
        return "<h1>ユーザーが見つかりません。</h1>"

    if request.method == "POST":
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        if password != confirm_password:
            return render_template("set_password.html", error="パスワードが一致しません")

        # パスワード設定 & 本登録完了
        user.set_password(password)
        user.is_active = True
        db.session.commit()

        # ログイン画面へリダイレクト（フラッシュメッセージがあれば尚良し）
        # ここではシンプルにリダイレクト
        return redirect(url_for("login"))

    # GETリクエスト時はパスワード設定フォームを表示
    return render_template("set_password.html")

@app.route("/try_login", methods=["POST"])
def try_login():
    email = request.form.get("email")
    pw = request.form.get("password")

    user = User.query.filter_by(email=email).first()

    if user and user.check_password(pw):
        if not user.is_active:
             return render_template("login.html", error="メール認証を完了してください")
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
    user = User.query.filter_by(email=session["user"]).first()
    return render_template("home.html", user=user)

@app.route("/mypage")
def mypage():
    if "user" not in session:
        return redirect("/")
    user = User.query.filter_by(email=session["user"]).first()
    return render_template("mypage.html", user=user)

@app.route('/update_nickname', methods=['POST'])
def update_nickname():
    if "user" not in session:
        return redirect("/")
    
    user = User.query.filter_by(email=session["user"]).first()
    if user:
        user.nickname = request.form.get('nickname')
        db.session.commit()
        flash('ニックネームが更新されました。', 'success')
    else:
        flash('ユーザーが見つかりませんでした。', 'error')

    return redirect(url_for('mypage'))

@app.route('/update_password', methods=['POST'])
def update_password():
    if 'user' not in session:
        return redirect('/')

    user = User.query.filter_by(email=session['user']).first()
    if not user:
        flash('ユーザーが見つかりませんでした。', 'danger')
        return redirect(url_for('mypage'))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')

    if not user.check_password(current_password):
        flash('現在のパスワードが正しくありません。', 'danger')
        return redirect(url_for('mypage'))

    if new_password != confirm_password:
        flash('新しいパスワードが一致しません。', 'danger')
        return redirect(url_for('mypage'))

    user.set_password(new_password)
    db.session.commit()
    flash('パスワードが正常に更新されました。', 'success')
    return redirect(url_for('mypage'))

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

    # Save result to DB
    user_obj = User.query.filter_by(email=session['user']).first()
    if user_obj:
        if category == 'all':
            exam_type_val = "section_all"
        else:
            exam_type_val = f"section_{category}"
        
        # Create details JSON
        details_list = []
        for r in results:
            q = r['question']
            details_list.append({
                'q_id': q.id,
                'category': q.category,
                'is_correct': r['is_correct']
            })
            
        new_result = QuizResult(
            user_id=user_obj.id,
            exam_type=exam_type_val,
            total_questions=total,
            correct_answers=score,
            details=json.dumps(details_list)
        )
        db.session.add(new_result)
        db.session.commit()

    return render_template('result.html', results=results, score=score, total=total, test_type='section')

@app.route("/practice", methods=["GET"])
def practice():
    if "user" not in session:
        return redirect("/")
    
    num_questions_str = request.args.get('num_questions')
    test_type = request.args.get('test_type') # Retrieve test_type

    if not num_questions_str:
        # Display selection screen
        options = {
            "5問": 5,
            "10問": 10,
            "20問": 20,
            "30問": 30,
            "40問": 40,
            "50問": 50,
            "100問": 100,
            "すべて": "all"
        }
        return render_template("practice_test.html", question_options=options)

    all_questions = Question.query.all()
    total_available = len(all_questions)

    if num_questions_str == 'all':
        num_to_sample = total_available
    elif num_questions_str in ['40_random_mock', '40_weakness_mock']:
        num_to_sample = 40
        if num_questions_str == '40_random_mock':
            test_type = 'random'
        elif num_questions_str == '40_weakness_mock':
            test_type = 'weakness'
    else:
        num_to_sample = int(num_questions_str)

    # Ensure we don't request more questions than available
    num_to_sample = min(num_to_sample, total_available)
    
    if num_to_sample == 0:
        return "問題がDBにありません"

    # Shuffle all questions if 'all' is selected, otherwise sample
    if num_questions_str == 'all':
        q_list = all_questions
        random.shuffle(q_list)
    elif num_questions_str == '40_weakness_mock':
        # Sort by correct rate (ascending), take first 40
        # If total_count is 0, treat as rate 0 (very weak/unknown)
        def get_rate(q):
            if q.total_count == 0: return 0.0
            return q.correct_count / q.total_count
        
        sorted_q = sorted(all_questions, key=get_rate)
        q_list = sorted_q[:num_to_sample]
        random.shuffle(q_list) # Shuffle the selected weak questions
    else:
        q_list = random.sample(all_questions, num_to_sample)

    return render_template(
        "practice_test.html",
        questions=q_list,
        total=len(q_list),
        test_type=test_type # Pass test_type to the template
    )

@app.route('/submit_practice', methods=['POST'])
def submit_practice():
    if 'user' not in session:
        return redirect('/')

    results = []
    score = 0
    test_type = request.form.get('test_type') # Retrieve test_type
    
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

    # Save result to DB
    user_obj = User.query.filter_by(email=session['user']).first()
    if user_obj:
        # Create details JSON
        details_list = []
        for r in results:
            q = r['question']
            details_list.append({
                'q_id': q.id,
                'category': q.category,
                'is_correct': r['is_correct']
            })
            
        new_result = QuizResult(
            user_id=user_obj.id,
            exam_type=test_type,
            total_questions=total,
            correct_answers=score,
            details=json.dumps(details_list)
        )
        db.session.add(new_result)
        db.session.commit()

    return render_template('result.html', results=results, score=score, total=total, test_type=test_type)

@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        return redirect("/")
    return render_template("admin.html")

@app.route("/admin/questions")
def admin_questions():
    if not session.get("is_admin"):
        return redirect("/")

    page = request.args.get('page', 1, type=int)
    section = request.args.get('section', 'all')

    query = Question.query.order_by(Question.id)

    if section != 'all':
        query = query.filter(Question.category == f"section_{section}")

    pagination = query.paginate(page=page, per_page=20, error_out=False)
    questions = pagination.items
    total_questions = query.count() # Get total count after filtering

    sections = ["all"] + [str(i) for i in range(1, 17)]

    return render_template(
        "admin_questions.html",
        questions=questions,
        pagination=pagination,
        sections=sections,
        selected_section=section,
        total_questions=total_questions
    )

@app.route("/admin/question/delete/<int:id>", methods=["POST"])
def delete_question(id):
    if not session.get("is_admin"):
        return redirect("/")
    
    question = Question.query.get_or_404(id)
    db.session.delete(question)
    db.session.commit()
    flash('質問が削除されました。', 'success')
    return redirect(url_for("admin_questions"))

@app.route("/admin/question/<int:id>", methods=["GET", "POST"])
def edit_question(id):
    if not session.get("is_admin"):
        return redirect("/")
    
    question = Question.query.get_or_404(id)

    if request.method == "POST":
        question.question = request.form["question"]
        question.choice1 = request.form["choice1"]
        question.choice2 = request.form["choice2"]
        question.choice3 = request.form["choice3"]
        question.choice4 = request.form["choice4"]
        question.correct = int(request.form["correct"])
        question.category = request.form["category"]
        question.rationale = request.form["rationale"]
        question.reference = request.form["reference"]
        db.session.commit()
        return redirect(url_for("admin_questions"))

    return render_template("edit_question.html", question=question)

@app.route("/admin/question/new", methods=["GET", "POST"])
def new_question():
    if not session.get("is_admin"):
        return redirect("/")

    if request.method == "POST":
        new_q = Question(
            question=request.form["question"],
            choice1=request.form["choice1"],
            choice2=request.form["choice2"],
            choice3=request.form["choice3"],
            choice4=request.form["choice4"],
            correct=int(request.form["correct"]),
            category=request.form["category"],
            rationale=request.form["rationale"],
            reference=request.form["reference"]
        )
        db.session.add(new_q)
        db.session.commit()
        return redirect(url_for("admin_questions"))

    return render_template("new_question.html")

@app.route("/admin/export")
def export_questions():
    if not session.get("is_admin"):
        return redirect("/")

    questions = Question.query.all()
    
    export_data = []
    for q in questions:
        export_data.append({
            "question": q.question,
            "choices": [q.choice1, q.choice2, q.choice3, q.choice4],
            "correct": q.correct,
            "category": q.category,
            "rationale": q.rationale,
            "reference": q.reference
        })
    
    json_data = json.dumps(export_data, ensure_ascii=False, indent=4)

    return Response(
        json_data,
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment;filename=questions_export.json'}
    )


@app.route('/admin/users')
def admin_users():
    if not session.get("is_admin"):
        return redirect("/")
    users = User.query.filter_by(is_admin=False).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/new', methods=['GET', 'POST'])
def new_user():
    if not session.get("is_admin"):
        return redirect("/")
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('new_user'))

        new_user = User(email=email, is_admin=False)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash('新しいユーザーが作成されました。', 'success')
        return redirect(url_for('admin_users'))
    return render_template('new_user.html')

@app.route('/admin/user/edit/<int:id>', methods=['GET', 'POST'])
def edit_user(id):
    if not session.get("is_admin"):
        return redirect("/")
    user = User.query.get_or_404(id)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if user.email != email and User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('edit_user', id=id))

        user.email = email
        if password:
            user.set_password(password)
        db.session.commit()
        flash('ユーザー情報が更新されました。', 'success')
        return redirect(url_for('admin_users'))
    return render_template('edit_user.html', user=user)

@app.route('/admin/user/delete/<int:id>', methods=['POST'])
def delete_user(id):
    if not session.get("is_admin"):
        return redirect("/")
    user = User.query.get_or_404(id)
    db.session.delete(user)
    db.session.commit()
    flash('ユーザーが削除されました。', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/admins')
def admin_admins():
    if not session.get("is_admin"):
        return redirect("/")
    admins = User.query.filter_by(is_admin=True).all()
    return render_template('admin_admins.html', admins=admins)

@app.route('/admin/admin/new', methods=['GET', 'POST'])
def new_admin():
    if not session.get("is_admin"):
        return redirect("/")
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('new_admin'))

        new_admin = User(email=email, is_admin=True)
        new_admin.set_password(password)
        db.session.add(new_admin)
        db.session.commit()
        flash('新しい管理者が作成されました。', 'success')
        return redirect(url_for('admin_admins'))
    return render_template('new_admin.html')

@app.route('/admin/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_admin(id):
    if not session.get("is_admin"):
        return redirect("/")
    admin = User.query.get_or_404(id)
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')

        if admin.email != email and User.query.filter_by(email=email).first():
            flash('このメールアドレスは既に使用されています。', 'danger')
            return redirect(url_for('edit_admin', id=id))

        admin.email = email
        if password:
            admin.set_password(password)
        db.session.commit()
        flash('管理者情報が更新されました。', 'success')
        return redirect(url_for('admin_admins'))
    return render_template('edit_admin.html', user=admin)

@app.route('/admin/admin/delete/<int:id>', methods=['POST'])
def delete_admin(id):
    if not session.get("is_admin"):
        return redirect("/")
    admin = User.query.get_or_404(id)
    # Prevent admin from deleting themselves
    if admin.email == session.get("user"):
        flash("自分自身を削除することはできません。", "danger")
        return redirect(url_for("admin_admins"))

    db.session.delete(admin)
    db.session.commit()
    flash('管理者が削除されました。', 'success')
    return redirect(url_for('admin_admins'))

@app.route('/analytics_data')
def analytics_data():
    if "user" not in session:
        return jsonify({})
    
    user = User.query.filter_by(email=session["user"]).first()
    if not user:
        return jsonify({})
    
    now = datetime.now()
    
    # 1. Weekly Trend (Last 2 months = approx 8 weeks)
    weekly_data = []
    weekly_labels = []
    
    # Start from 8 weeks ago
    start_date = now - timedelta(weeks=8)
    
    # Get all results for user in range to minimize DB hits? No, simple query is fine.
    # Actually, iterate weeks
    for i in range(8):
        w_start = start_date + timedelta(weeks=i)
        w_end = w_start + timedelta(weeks=1)
        w_label = w_start.strftime('%m/%d')
        weekly_labels.append(w_label)
        
        # Filter results in this week
        results_week = QuizResult.query.filter(
            QuizResult.user_id == user.id,
            QuizResult.timestamp >= w_start,
            QuizResult.timestamp < w_end
        ).all()
        
        if results_week:
            total_q = sum(r.total_questions for r in results_week)
            total_c = sum(r.correct_answers for r in results_week)
            rate = (total_c / total_q) * 100 if total_q > 0 else 0
            weekly_data.append(round(rate, 1))
        else:
            weekly_data.append(0)
            
    # 2. Section Rate (Last 1 month)
    section_labels = [f"{i}章" for i in range(1, 17)]
    section_data = [0] * 16
    
    start_date_month = now - timedelta(days=30)
    # Get ALL results in last month (including mocks)
    results_month = QuizResult.query.filter(
        QuizResult.user_id == user.id,
        QuizResult.timestamp >= start_date_month
    ).all()
    
    section_sums = {} # key: section_idx (0-15), val: {total_q, total_c}
    
    for r in results_month:
        # If details exist, use details (more accurate for mixed exams)
        if r.details:
            try:
                details = json.loads(r.details)
                for d in details:
                    cat = d.get('category') # e.g., "section_1"
                    if cat and cat.startswith('section_'):
                        try:
                            sec_num = int(cat.split('_')[1])
                            if 1 <= sec_num <= 16:
                                idx = sec_num - 1
                                if idx not in section_sums: section_sums[idx] = {'q': 0, 'c': 0}
                                section_sums[idx]['q'] += 1
                                if d.get('is_correct'):
                                    section_sums[idx]['c'] += 1
                        except: pass
            except: pass
        
        # Fallback for old records (section tests only) without details
        elif r.exam_type.startswith('section_') and r.exam_type != 'section_all':
            try:
                sec_num = int(r.exam_type.split('_')[1])
                if 1 <= sec_num <= 16:
                    idx = sec_num - 1
                    if idx not in section_sums:
                        section_sums[idx] = {'q': 0, 'c': 0}
                    section_sums[idx]['q'] += r.total_questions
                    section_sums[idx]['c'] += r.correct_answers
            except:
                continue
            
    for idx, vals in section_sums.items():
        if vals['q'] > 0:
            section_data[idx] = round((vals['c'] / vals['q']) * 100, 1)
            
    # 3. Random Mock Trend (Last 10)
    mock_random = QuizResult.query.filter(
        QuizResult.user_id == user.id,
        QuizResult.exam_type == 'random'
    ).order_by(QuizResult.timestamp.desc()).limit(10).all()
    
    mock_random.reverse() # Oldest to newest
    random_labels = [r.timestamp.strftime('%m/%d %H:%M') for r in mock_random]
    random_scores = [r.correct_answers for r in mock_random]
    random_rates = [round((r.correct_answers/r.total_questions)*100, 1) if r.total_questions > 0 else 0 for r in mock_random]
    
    # 4. Weakness Mock Trend (Last 10)
    mock_weakness = QuizResult.query.filter(
        QuizResult.user_id == user.id,
        QuizResult.exam_type == 'weakness'
    ).order_by(QuizResult.timestamp.desc()).limit(10).all()
    
    mock_weakness.reverse()
    weakness_labels = [r.timestamp.strftime('%m/%d %H:%M') for r in mock_weakness]
    weakness_scores = [r.correct_answers for r in mock_weakness]
    weakness_rates = [round((r.correct_answers/r.total_questions)*100, 1) if r.total_questions > 0 else 0 for r in mock_weakness]
    
    return jsonify({
        'weekly': {'labels': weekly_labels, 'data': weekly_data},
        'section': {'labels': section_labels, 'data': section_data},
        'random': {'labels': random_labels, 'scores': random_scores, 'rates': random_rates},
        'weakness': {'labels': weakness_labels, 'scores': weakness_scores, 'rates': weakness_rates}
    })

@app.route('/analytics')
def analytics():
    if "user" not in session:
        return redirect("/")
    
    user = User.query.filter_by(email=session["user"]).first()
    return render_template('analytics.html', user=user)

if __name__ == "__main__":
    app.run(debug=True)