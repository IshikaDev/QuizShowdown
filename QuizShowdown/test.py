from flask import Flask, render_template, request, redirect, url_for, session
import pandas as pd
import random
import os
import sys
import firebase_admin
from firebase_admin import credentials, db

app = Flask(__name__)
app.secret_key = '8a5d3f7b9c2e4d67a8b5c1d2f4e6a7b9c0d1e2f3'

# Load questions from Excel files
TECHNICAL_FILE = "technical.xlsx"
LOGICAL_FILE = "logical.xlsx"

# Define the password for restarting the quiz
RESTART_PASSWORD = "EESA@123"

# Firebase Initialization
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://defuseprotocol-default-rtdb.asia-southeast1.firebasedatabase.app/'
})

# Firebase Reference
firebase_ref = db.reference("live_bomb")

def load_questions(file_name):
    try:
        file_path = file_name
        df = pd.read_excel(file_path)
        questions = df.to_dict(orient='records')
        
        for q in questions:
            for key in q:
                if isinstance(q[key], str):
                    q[key] = q[key].strip()
                elif pd.isna(q[key]):
                    q[key] = ""
                else:
                    q[key] = str(q[key])
                    
        return questions
    except FileNotFoundError as e:
        print(f"Error loading file {file_name}: {e}")
        raise

def update_firebase_time(penalty_time_seconds, bonus_time_seconds):
    try:
        firebase_ref.update({
            "penalty": penalty_time_seconds,
            "bonus": bonus_time_seconds
        })

        print("Penalty Time Updated in Firebase:", penalty_time_seconds)
        print("Bonus Time Updated in Firebase:", bonus_time_seconds)
    except Exception as e:
        print("Error updating Firebase:", str(e))


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_quiz', methods=['GET'])
def start_quiz():
    question_type = request.args.get('type', 'Technical')
    file_name = TECHNICAL_FILE if question_type == 'Technical' else LOGICAL_FILE
    questions = load_questions(file_name)
    random.shuffle(questions)
    
    session['questions'] = questions[:5]
    session['current_index'] = 0
    session['score'] = 0
    session['penalty_time'] = 0
    session['extra_attempts'] = 0
    session['question_type'] = question_type
    
    return redirect(url_for('quiz'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    index = session['current_index']
    
    if request.method == 'POST':
        submitted_answer = request.form.get('answer', '').strip()
        correct_answer = str(session['questions'][index]['Answer']).strip()
        
        if submitted_answer == correct_answer:
            session['score'] += 1
        else:
            session['penalty_time'] += 10
        
        session['current_index'] += 1
        session.modified = True
        
        if session['current_index'] >= 5:
            return redirect(url_for('result'))
        
        return redirect(url_for('quiz'))
    
    question = session['questions'][index]
    options = [question['Option1'], question['Option2'], question['Option3'], question['Option4']]
    random.shuffle(options)
    
    return render_template('quiz.html', 
                           question=question['Question'], 
                           options=options, 
                           index=index + 1,
                           question_type=session['question_type'])

@app.route('/result')
def result():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    score = session['score']
    penalty_time = session['penalty_time']
    bonus_time = 50 if score == 5 else 0
    
    if score >= 4:
        update_firebase_time(penalty_time, bonus_time)
    
    return render_template('result1.html', 
                           score=score, 
                           penalty_time=penalty_time, 
                           bonus_time=bonus_time)

@app.route('/retry', methods=['POST'])
def retry():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    if session['extra_attempts'] >= 4:
        return redirect(url_for('final_result'))
    
    question_type = session['question_type']
    file_name = TECHNICAL_FILE if question_type == 'Technical' else LOGICAL_FILE
    questions = load_questions(file_name)
    random.shuffle(questions)
    
    session['questions'] = questions[:4]
    session['current_index'] = 0
    session['extra_attempts'] += 1
    
    session.modified = True
    return redirect(url_for('retry_quiz'))

@app.route('/retry_quiz', methods=['GET', 'POST'])
def retry_quiz():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    index = session['current_index']
    
    if request.method == 'POST':
        submitted_answer = request.form.get('answer', '').strip()
        correct_answer = str(session['questions'][index]['Answer']).strip()
        
        if submitted_answer == correct_answer:
            session['score'] += 1
        else:
            session['penalty_time'] += 10
        
        session['current_index'] += 1
        session.modified = True
        
        if session['current_index'] >= 4 or session['score'] >= 4:
            return redirect(url_for('final_result'))
        
        return redirect(url_for('retry_quiz'))
    
    question = session['questions'][index]
    options = [question['Option1'], question['Option2'], question['Option3'], question['Option4']]
    random.shuffle(options)
    
    return render_template('retry.html', 
                           question=question['Question'], 
                           options=options, 
                           index=index + 1,
                           question_type=session['question_type'])

@app.route('/final_result')
def final_result():
    if 'questions' not in session:
        return redirect(url_for('index'))
    
    score = session['score']
    penalty_time = session['penalty_time']
    
    update_firebase_time(penalty_time, 0)
    
    session.clear()
    
    return render_template('result.html', 
                           score=score, 
                           penalty_time=penalty_time,
                           message="Thank You")

@app.route('/eliminated')
def eliminated():
    score = session.get('score', 0)
    penalty_time = session.get('penalty_time', 0)
    
    return render_template('result.html', 
                           score=score, 
                           penalty_time=penalty_time, 
                           message="You have been eliminated")

@app.route('/password', methods=['GET', 'POST'])
def password():
    if request.method == 'POST':
        entered_password = request.form.get('password', '').strip()
        if entered_password == RESTART_PASSWORD:
            update_firebase_time(0, 0)
            return redirect(url_for('index'))
        else:
            error = "Incorrect password. Please try again."
            return render_template('password.html', error=error)
    return render_template('password.html')

if __name__ == '__main__':
    print("Starting Flask server. Open your browser to http://127.0.0.1:5000/")
    app.run(debug=True, use_reloader=False)
