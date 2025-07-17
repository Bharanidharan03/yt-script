from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from pakka import generate_scripts, fetch_trending_topics, get_youtube_categories

import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
import json
import os
import base64
from dotenv import load_dotenv
load_dotenv()

# Store notifications per freelancer email
freelancer_notifications = {}

TASK_FILE = "data/tasks.json"

def load_tasks():
    if os.path.exists(TASK_FILE):
        with open(TASK_FILE, 'r') as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    with open(TASK_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

# Firebase Admin





# Decode the Firebase key from environment variable
firebase_b64 = os.getenv("FIREBASE_KEY_B64")
firebase_json_path = "firebase-service-account.json"

with open(firebase_json_path, "wb") as f:
    f.write(base64.b64decode(firebase_b64))

# Initialize Firebase
cred = credentials.Certificate(firebase_json_path)


firebase_admin.initialize_app(cred)

# ------------------- AUTH -------------------
def verify_firebase_token(id_token):
    try:
        return auth.verify_id_token(id_token)
    except Exception as e:
        print("Token verification failed:", e)
        return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'firebase_id_token' not in session:
            return redirect(url_for('login'))
        decoded_token = verify_firebase_token(session['firebase_id_token'])
        if decoded_token is None:
            session.pop('firebase_id_token', None)
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/sessionLogin", methods=["POST"])
def session_login():
    data = request.json
    id_token = data.get("idToken")
    user = verify_firebase_token(id_token)
    if user:
        session["firebase_id_token"] = id_token
        session["user_email"] = user.get("email")
        return jsonify({"message": "Logged in"}), 200
    else:
        return jsonify({"message": "Invalid token"}), 401

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ------------------- ROUTES -------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup')
def signup():
    return render_template("signup.html")

@app.route('/login')
def login():
    return render_template('login.html')

# ------------------- Trending Scripts -------------------

@app.route('/trending', methods=['GET', 'POST'])
def trending():
    youtube_categories = get_youtube_categories()
    if request.method == 'POST':
        domain = request.form['domain']
        max_topics = int(request.form['count'])
        length = request.form['length']
        language = request.form['language']
        tone = request.form['tone']

        topics = fetch_trending_topics(source="youtube", domain=domain, max_topics=max_topics)
        if topics:
            return render_template('result.html', topics=topics, length=length, language=language, tone=tone, source="youtube")
        else:
            return render_template('trending.html', error="No topics found.",
                                   youtube_categories=youtube_categories,
                                   fallback_data={'domain': domain, 'max_topics': max_topics, 'length': length, 'language': language, 'tone': tone})
    return render_template('trending.html', youtube_categories=youtube_categories, fallback_data=None, error=None)

@app.route('/fallback_trending', methods=['POST'])
def fallback_trending():
    max_topics = int(request.form['count'])
    length = request.form['length']
    language = request.form['language']
    tone = request.form['tone']

    topics = fetch_trending_topics(source="fallback", max_topics=max_topics)
    if topics:
        return render_template('result.html', topics=topics, length=length, language=language, tone=tone, source="fallback")
    else:
        return render_template('trending.html', error="No fallback topics found.",
                               youtube_categories=get_youtube_categories(),
                               fallback_data={'domain': 'all', 'max_topics': max_topics, 'length': length, 'language': language, 'tone': tone})

@app.route('/generate', methods=['POST'])
def generate():
    selected_topics = request.form.getlist('selected_topics')
    length = request.form['length']
    language = request.form['language']
    tone = request.form['tone']
    source = request.form.get('source')

    if not selected_topics:
        return render_template('result.html', error="Please select at least one topic.",
                               topics=request.form.getlist('original_topics'),
                               length=length, language=language, tone=tone, source=source)

    scripts = generate_scripts(selected_topics, length, language, tone)
    return render_template('result.html', scripts=scripts, topics=selected_topics)

@app.route('/manual-script', methods=['GET', 'POST'])
def manual_script():
    if request.method == 'POST':
        topic = request.form['topic']
        tone = request.form['tone']
        language = request.form['language']
        length = request.form['length']
        scripts = generate_scripts([topic], length, language, tone)
        return render_template('result.html', scripts=scripts, topics=[topic])
    return render_template('manual_script.html')

@app.route('/result', methods=['GET'])
def result():
    topics = request.args.getlist('topics')
    length = request.args.get('length')
    language = request.args.get('language')
    tone = request.args.get('tone')
    source = request.args.get('source')

    if topics and length and language and tone:
        return render_template('result.html', topics=topics, length=length, language=language, tone=tone, source=source)
    else:
        return redirect(url_for('trending'))

# ------------------- Creator–Freelancer Hub -------------------

@app.route('/hub')
@login_required
def hub():
    return render_template('hub.html')

@app.route('/creator', methods=['GET', 'POST'])
@login_required
def creator_page():
    if request.method == 'POST':
        tasks = load_tasks()
        need = request.form.get('need')
        duration = request.form.get('duration')
        budget = request.form.get('budget')
        posted_by = session.get('user_email', 'Unknown')

        if need and duration and budget:
            tasks.append({
                'need': need,
                'duration': duration,
                'budget': budget,
                'posted_by': posted_by,
                'status': 'open',
                'freelancer_email': None,
                'freelancer_message': None
            })
            save_tasks(tasks)
            flash("Task posted successfully!")

        return redirect(url_for('creator_page'))

    tasks = load_tasks()
    return render_template('creator.html', posts=tasks, user_email=session.get('user_email'))

@app.route('/freelancer', methods=['GET', 'POST'])
@login_required
def freelancer_page():
    global freelancer_notifications
    creator_posts = load_tasks()
    user_email = session.get('user_email')

    # ✅ Check for notification
    notification = freelancer_notifications.pop(user_email, None)

    return render_template('freelancer.html', posts=creator_posts, user_email=user_email, notification=notification)


@app.route('/respond', methods=['POST'])
@login_required
def respond():
    post_id = int(request.form.get('post_id'))
    freelancer_email = session.get("user_email")
    freelancer_message = request.form.get("message")

    tasks = load_tasks()

    if 0 <= post_id < len(tasks):
        tasks[post_id]['freelancer_email'] = freelancer_email
        tasks[post_id]['freelancer_message'] = freelancer_message
        tasks[post_id]['status'] = 'pending'
        save_tasks(tasks)
        flash("✅ Request sent to creator!")

    return redirect(url_for('freelancer_page'))

@app.route('/creator-requests', methods=['GET', 'POST'])
@login_required
def creator_requests():
    global creator_posts, freelancer_notifications
    creator_email = session.get('user_email')

    if request.method == 'POST':
        post_id = int(request.form.get('post_id'))
        action = request.form.get('action')

        if 0 <= post_id < len(creator_posts):
            task = creator_posts[post_id]
            if action == 'accept':
                task['status'] = 'accepted'

                # ✅ Notify the freelancer
                freelancer_email = task.get('freelancer_email')
                if freelancer_email:
                    freelancer_notifications[freelancer_email] = f"🎉 Your request for '{task['need']}' was accepted!"
            elif action == 'reject':
                task['status'] = 'rejected'

        return redirect(url_for('creator_requests'))

    return render_template('creator_requests.html', posts=creator_posts, creator_email=creator_email)



# ------------------- RUN -------------------
if __name__ == "__main__":
    # Render sets a PORT env variable; default to 5000 for local testing
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)