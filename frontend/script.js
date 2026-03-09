const API_URL = "http://127.0.0.1:8000";


let studentId       = null;
let studentName     = null;
let currentTopic    = "";
let currentDifficulty = "beginner";
let currentQuestion = null;
let currentAnswer   = null;
let questionQueue   = [];
let startTime       = 0;
let aiQuestionCount = 0;
let quizFinished    = false;
let sessionTotal    = 0;
let sessionCorrect  = 0;

function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
}

function switchLoginTab(role) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.login-form').forEach(f => f.classList.remove('active'));
    document.querySelector(`.tab-btn[onclick*="${role}"]`).classList.add('active');
    document.getElementById(`login-${role}`).classList.add('active');
}

//  STUDENT LOGIN 
async function studentLogin() {
    const email = document.getElementById('s-email').value.trim();
    const name  = document.getElementById('s-name').value.trim();
    const err   = document.getElementById('s-error');
    err.textContent = '';

    if (!email) { err.textContent = '// EMAIL IS REQUIRED'; return; }

    try {
        const res  = await fetch(`${API_URL}/students/${encodeURIComponent(email)}`);
        const data = await res.json();

        if (!data.error) {
            // Returning student
            studentId   = data.id;
            studentName = data.name;
        } else {
            // New student
            if (!name) {
                err.textContent = '// EMAIL NOT FOUND — ENTER YOUR NAME TO REGISTER';
                return;
            }
            const newRes  = await fetch(`${API_URL}/students/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, email })
            });
            const newData = await newRes.json();
            if (newData.student_id) {
                studentId   = newData.student_id;
                studentName = name;
            } else {
                err.textContent = '// FAILED TO CREATE ACCOUNT';
                return;
            }
        }

        // Enter student portal
        document.getElementById('nav-student-name').textContent = studentName.toUpperCase();
        showScreen('screen-student');
        addChat('ai', `👋 **Welcome back, ${studentName}!** Select a subject and difficulty on the left, then hit **Start Quiz** to begin.`);

    } catch (e) {
        err.textContent = '// CANNOT CONNECT TO SERVER';
    }
}

//  TEACHER LOGIN 
function teacherLogin() {
    const pass = document.getElementById('t-pass').value;
    const err  = document.getElementById('t-error');
    err.textContent = '';

    if (pass === 'admin123') {
        showScreen('screen-teacher');
        loadAnalytics();
    } else {
        err.textContent = '// INCORRECT PASSCODE — ACCESS DENIED';
    }
}

//  LOGOUT 
function logout() {
    // Reset all state
    studentId = studentName = currentQuestion = currentAnswer = null;
    questionQueue = []; aiQuestionCount = 0; quizFinished = false;
    sessionTotal = sessionCorrect = 0;

    // Reset UI
    document.getElementById('chat-box').innerHTML = `
        <div class="chat-welcome">
            <div class="welcome-icon">⬡</div>
            <h2>Ready to learn?</h2>
            <p>Select a subject and difficulty, then hit <strong>Start Quiz</strong> to begin your session.</p>
        </div>`;
    document.getElementById('s-email').value = '';
    document.getElementById('s-name').value  = '';
    document.getElementById('s-error').textContent = '';
    document.getElementById('t-pass').value  = '';
    setInputEnabled(false);
    showScreen('screen-login');
}

//  STUDENT TABS 
function showStudentTab(tabId) {
    document.querySelectorAll('.student-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.topnav-tabs .nav-tab').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.currentTarget.classList.add('active');

    if (tabId === 'tab-progress') loadProgress();
}

//  TEACHER TABS 
function showTeacherTab(tabId) {
    document.querySelectorAll('.teacher-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.topnav-tabs .nav-tab').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    event.currentTarget.classList.add('active');
}

//  DIFFICULTY SELECTOR 
function setDifficulty(btn) {
    document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDifficulty = btn.dataset.val;
}

// START QUIZ 
async function startQuiz() {
    currentTopic    = document.getElementById('topic-select').value;
    aiQuestionCount = 0;
    quizFinished    = false;
    questionQueue   = [];
    sessionTotal    = 0;
    sessionCorrect  = 0;

    // Reset chat
    document.getElementById('chat-box').innerHTML = '';
    updateSidebarStats();
    document.getElementById('sidebar-stats').style.display = 'flex';

    addChat('ai', `🚀 Starting **${currentTopic}** at **${currentDifficulty}** level. Loading questions...`);
    await loadNextQuestion();
}

// LOAD NEXT QUESTION 
async function loadNextQuestion() {
    if (quizFinished) return;
    setInputEnabled(false);

    try {
        // Fill queue from teacher bank if empty
        if (questionQueue.length === 0 && aiQuestionCount === 0) {
            const res  = await fetch(`${API_URL}/teacher-questions/${encodeURIComponent(currentTopic)}/${encodeURIComponent(currentDifficulty)}`);
            const data = await res.json();
            if (Array.isArray(data) && data.length > 0) {
                questionQueue = data.sort(() => Math.random() - 0.5);
            }
        }

        if (questionQueue.length > 0) {
            // Use teacher question
            const q       = questionQueue.shift();
            currentQuestion = q.generated_question;
            currentAnswer   = q.correct_answer;

            addChat('ai', `📝 **Question (Teacher Bank):**\n\n${currentQuestion}`);

        } else {
            // AI question limit: 5
            if (aiQuestionCount >= 5) {
                quizFinished = true;
                setInputEnabled(false);
                addChat('ai', `🎉 **Excellent work! You've completed all questions for this session.**\n\nSelect a new topic in the sidebar to keep learning, or check your progress in the Progress tab!`);
                return;
            }

            // Transition message
            if (aiQuestionCount === 0) {
                addChat('ai', '🤖 Excellent! Now here are a few AI-generated questions to solidify your understanding...');
            }

            aiQuestionCount++;
            document.getElementById('stat-ai').textContent = aiQuestionCount;
            addChat('ai', `⏳ Generating AI question ${aiQuestionCount} of 5...`);

            const res  = await fetch(`${API_URL}/generate-question/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic: currentTopic, difficulty: currentDifficulty })
            });
            const data = await res.json();

            if (data.error) {
                addChat('ai', '⚠️ Failed to generate question. Please try again.');
                setInputEnabled(true);
                return;
            }

            currentQuestion = data.generated_question;
            currentAnswer   = data.correct_answer;

            addChat('ai', `🤖 **AI Question ${aiQuestionCount} of 5:**\n\n${currentQuestion}`);
        }

        startTime = Date.now();
        setInputEnabled(true);
        document.getElementById('answer-input').focus();

    } catch (e) {
        console.error(e);
        addChat('ai', '⚠️ Network error. Is the backend running?');
        setInputEnabled(true);
    }
}

// SUBMIT ANSWER 
async function submitAnswer() {
    const input  = document.getElementById('answer-input');
    const answer = input.value.trim();
    if (!answer || !currentQuestion) return;

    input.value = '';
    addChat('user', answer);
    setInputEnabled(false);

    const timeTaken = Math.round((Date.now() - startTime) / 1000);

    try {
        const res  = await fetch(`${API_URL}/submit-answer/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                student_id:    studentId,
                topic:         currentTopic,
                question_text: currentQuestion,
                student_answer: answer,
                correct_answer: currentAnswer,
                time_taken:    timeTaken
            })
        });
        const data = await res.json();

        if (data.error) {
            addChat('ai', `⚠️ Error: ${data.error}`);
            setInputEnabled(true);
            return;
        }

        // Update session stats
        sessionTotal++;
        if (data.is_correct) sessionCorrect++;
        updateSidebarStats();

        const icon  = data.is_correct ? '✅' : '❌';
        const label = data.is_correct ? 'Correct!' : 'Not quite.';
        addChat('ai', `${icon} **${label}**\n\n💬 **AI Feedback:**\n${data.ai_feedback}\n\n⏱️ Time taken: **${timeTaken}s**`);

        currentQuestion = null;
        currentAnswer   = null;

        setTimeout(() => loadNextQuestion(), 1600);

    } catch (e) {
        console.error(e);
        addChat('ai', '⚠️ Could not submit answer. Check your connection.');
        setInputEnabled(true);
    }
}

// KEY HANDLER 
function handleKey(e) {
    if (e.key === 'Enter') submitAnswer();
}

// CHAT HELPER 
function addChat(sender, text) {
    const box = document.getElementById('chat-box');

    // Remove welcome screen if present
    const welcome = box.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const div = document.createElement('div');
    div.className = `message ${sender === 'ai' ? 'ai-msg' : 'user-msg'}`;

    let html = text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    div.innerHTML = html;

    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

// INPUT STATE 
function setInputEnabled(on) {
    const input = document.getElementById('answer-input');
    const btn   = document.getElementById('send-btn');
    input.disabled = !on;
    btn.disabled   = !on;
}

// SIDEBAR STATS 
function updateSidebarStats() {
    document.getElementById('stat-q-count').textContent = sessionTotal;
    document.getElementById('stat-correct').textContent = sessionCorrect;
    document.getElementById('stat-ai').textContent      = aiQuestionCount;
}

// LOAD PROGRESS 
async function loadProgress() {
    const container = document.getElementById('progress-content');
    container.innerHTML = '<div class="empty-state">// LOADING DATA...</div>';

    try {
        const res  = await fetch(`${API_URL}/analytics/student-report/${studentId}`);
        const data = await res.json();

        if (!data.topic_breakdown || data.topic_breakdown.length === 0) {
            container.innerHTML = '<div class="empty-state">// NO DATA YET — COMPLETE A QUIZ TO SEE YOUR PROGRESS</div>';
            return;
        }

        container.innerHTML = '';
        data.topic_breakdown.forEach(row => {
            const score = parseFloat(row.average_score).toFixed(1);
            const barClass = score >= 70 ? '' : score >= 50 ? 'mid' : 'low';

            const card = document.createElement('div');
            card.className = 'progress-card';
            card.innerHTML = `
                <h3>// ${row.topic.toUpperCase()}</h3>
                <div class="metric-row">
                    <div class="metric">
                        <div class="metric-label">QUESTIONS ATTEMPTED</div>
                        <div class="metric-value">${row.questions_attempted}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">AVERAGE SCORE</div>
                        <div class="metric-value">${score}%</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">AVG TIME / QUESTION</div>
                        <div class="metric-value">${parseFloat(row.average_time_seconds).toFixed(1)}s</div>
                    </div>
                </div>
                <div class="score-bar-wrap">
                    <div class="score-bar-label">Performance</div>
                    <div class="score-bar-track">
                        <div class="score-bar-fill ${barClass}" style="width: 0%"
                             data-target="${score}"></div>
                    </div>
                </div>`;
            container.appendChild(card);

            // Animate bar after paint
            requestAnimationFrame(() => {
                setTimeout(() => {
                    card.querySelector('.score-bar-fill').style.width = `${score}%`;
                }, 50);
            });
        });

    } catch (e) {
        container.innerHTML = '<div class="empty-state">// FAILED TO LOAD — IS THE BACKEND RUNNING?</div>';
    }
}

// LOAD ANALYTICS (TEACHER) 
async function loadAnalytics() {
    // Hardest topic
    try {
        const res  = await fetch(`${API_URL}/analytics/hardest-topic/`);
        const data = await res.json();
        if (data.topic) {
            document.getElementById('hardest-topic').textContent = data.topic;
            document.getElementById('hardest-score').textContent = `${parseFloat(data.average_score).toFixed(1)}% avg score`;
        } else {
            document.getElementById('hardest-topic').textContent = 'N/A';
            document.getElementById('hardest-score').textContent = 'Not enough data yet';
        }
    } catch (e) {
        document.getElementById('hardest-topic').textContent = 'Error';
    }

    // Struggling students
    try {
        const res  = await fetch(`${API_URL}/analytics/struggling-students/60`);
        const data = await res.json();
        const list = data.struggling_students || [];
        const el   = document.getElementById('struggling-list');
        document.getElementById('atrisk-count').textContent = list.length;

        if (list.length === 0) {
            el.innerHTML = '<div class="all-good">✅ All students are performing above 60%!</div>';
        } else {
            el.innerHTML = list.map(s => `
                <div class="student-alert">
                    <span class="student-alert-name">${s.name}</span>
                    <span class="student-alert-score">${parseFloat(s.average_score).toFixed(1)}%</span>
                </div>`).join('');
        }
    } catch (e) {
        document.getElementById('struggling-list').innerHTML = '<div class="empty-state">// FAILED TO LOAD</div>';
    }
}

// SAVE QUESTION (TEACHER) 
async function saveQuestion() {
    const topic  = document.getElementById('q-topic').value;
    const diff   = document.getElementById('q-diff').value;
    const text   = document.getElementById('q-text').value.trim();
    const answer = document.getElementById('q-answer').value.trim();
    const status = document.getElementById('q-status');

    status.textContent = '';
    status.className   = 'status-msg';

    if (!text || !answer) {
        status.textContent = '// PLEASE FILL IN BOTH QUESTION TEXT AND CORRECT ANSWER';
        status.className   = 'status-msg err';
        return;
    }

    try {
        const res  = await fetch(`${API_URL}/teacher-questions/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, difficulty: diff, question_text: text, correct_answer: answer })
        });
        const data = await res.json();

        if (data.message) {
            status.textContent = '✅ QUESTION SAVED SUCCESSFULLY';
            status.className   = 'status-msg ok';
            document.getElementById('q-text').value   = '';
            document.getElementById('q-answer').value = '';
        } else {
            status.textContent = '// FAILED TO SAVE QUESTION';
            status.className   = 'status-msg err';
        }
    } catch (e) {
        status.textContent = '// NETWORK ERROR';
        status.className   = 'status-msg err';
    }
}
