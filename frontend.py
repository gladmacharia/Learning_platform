import streamlit as st
import requests
import time

# --- CONFIGURATION ---
API_URL = "http://127.0.0.1:8000"
st.set_page_config(page_title="AI Learning Platform", page_icon="🎓", layout="wide")

st.markdown("""
    <style>
    button, div[data-baseweb="select"], input[type="text"], input[type="password"], textarea {
        cursor: pointer !important;
    }
    </style>
""", unsafe_allow_html=True)


for key in["role", "student_id", "student_name", "current_question", "start_time", "current_topic", "current_difficulty"]:
    if key not in st.session_state:
        st.session_state[key] = None
        
if "chat_history" not in st.session_state:
    st.session_state.chat_history =[]
if "question_queue" not in st.session_state:
    st.session_state.question_queue =[]
    
# Track how many AI questions have been asked, and if the quiz is over
if "ai_question_count" not in st.session_state:
    st.session_state.ai_question_count = 0
if "quiz_finished" not in st.session_state:
    st.session_state.quiz_finished = False

# LOGOUT FUNCTION 
def logout():
    for key in st.session_state.keys():
        del st.session_state[key]
    st.rerun()

# 1. AUTHENTICATION (LOGIN SCREEN)

if st.session_state.role is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🎓 AI Learning Platform")
        st.markdown("Welcome! Please log in to access your personalized learning environment.")
        st.divider()
        
        tab_student, tab_teacher = st.tabs(["👨‍🎓 Student Login", "👨‍🏫 Teacher Login"])
        
        with tab_student:
            with st.form("student_login_form"):
                st.subheader("Student Portal")
                email = st.text_input("Email Address", placeholder="e.g., student@school.com").strip()
                name = st.text_input("Full Name", placeholder="Only required if you are a new student").strip()
                submit_student = st.form_submit_button("Access Portal", use_container_width=True)
                
                if submit_student and email:
                    with st.spinner("Connecting to database..."):
                        res = requests.get(f"{API_URL}/students/{email}")
                        data = res.json()
                        
                        if "error" not in data:
                            st.session_state.role = "student"
                            st.session_state.student_id = data["id"]
                            st.session_state.student_name = data["name"]
                            st.session_state.chat_history.append({
                                "role": "assistant", 
                                "content": f"👋 **Welcome back, {data['name']}!** Use the sidebar on the left to start a new quiz."
                            })
                            st.rerun()
                        else:
                            if not name:
                                st.error("Email not found. Please provide your Name to register a new account.")
                            else:
                                new_user = requests.post(f"{API_URL}/students/", json={"name": name, "email": email}).json()
                                if "student_id" in new_user:
                                    st.session_state.role = "student"
                                    st.session_state.student_id = new_user["student_id"]
                                    st.session_state.student_name = name
                                    st.session_state.chat_history.append({
                                        "role": "assistant", 
                                        "content": f"🎉 **Account created! Welcome, {name}!** Use the sidebar on the left to start learning."
                                    })
                                    st.rerun()

        with tab_teacher:
            with st.form("teacher_login_form"):
                st.subheader("Teacher Dashboard")
            
                passcode = st.text_input("Administrator Passcode", type="password", placeholder="Enter Passcode")
                submit_teacher = st.form_submit_button("Access Dashboard", use_container_width=True)
                
                if submit_teacher:
                    if passcode == "admin123":
                        st.session_state.role = "teacher"
                        st.rerun()
                    else:
                        st.error("❌ Incorrect passcode. Access denied.")

# 2. STUDENT PORTAL

elif st.session_state.role == "student":
    with st.sidebar:
        st.header(f"👨‍🎓 {st.session_state.student_name}")
        if st.button("Logout", use_container_width=True):
            logout()
            
        st.divider()
        st.subheader("⚙️ Lesson Setup")
        topic = st.selectbox("Select Subject", ["Python Programming", "SQL Databases", "Data Science", "Web Development"])
        difficulty = st.select_slider("Difficulty", options=["beginner", "intermediate", "advanced"])
        
        if st.button("Start New Quiz 🚀", type="primary", use_container_width=True):
            with st.spinner("Loading questions..."):
                # Reset the quiz logic variables every time they start a new quiz
                st.session_state.ai_question_count = 0
                st.session_state.quiz_finished = False
                
                st.session_state.current_topic = topic
                st.session_state.current_difficulty = difficulty
                
                res = requests.get(f"{API_URL}/teacher-questions/{topic}/{difficulty}")
                teacher_questions = res.json()
                
                if isinstance(teacher_questions, list) and len(teacher_questions) > 0:
                    st.session_state.question_queue = teacher_questions
                    st.session_state.current_question = st.session_state.question_queue.pop(0)
                    q_text = st.session_state.current_question['generated_question']
                    
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": f"📝 **Teacher's Quiz:** Let's begin with a **{difficulty}** question for **{topic}**:\n\n### {q_text}"
                    })
                else:
                    # No teacher questions, so the first question is AI-generated
                    st.session_state.ai_question_count = 1
                    res_ai = requests.post(f"{API_URL}/generate-question/", json={"topic": topic, "difficulty": difficulty})
                    if res_ai.status_code == 200:
                        st.session_state.current_question = res_ai.json()
                        q_text = st.session_state.current_question['generated_question']
                        
                        st.session_state.chat_history.append({
                            "role": "assistant",
                            "content": f"🤖 **AI Tutor:** Let's test your knowledge with a **{difficulty}** question for **{topic}**:\n\n### {q_text}"
                        })
                        
                st.session_state.start_time = time.time()
                st.rerun()
    
    tab_learn, tab_progress = st.tabs(["🤖 AI Tutor Chat", "📊 My Progress"])
    
    with tab_learn:
        st.title("Interactive AI Tutor")
        
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        if st.session_state.current_question and not st.session_state.quiz_finished:
            student_answer = st.chat_input("Type your answer here...")
            if student_answer:
                time_taken = int(time.time() - st.session_state.start_time)
                st.session_state.chat_history.append({"role": "user", "content": student_answer})
                
                q_data = st.session_state.current_question
                payload = {
                    "student_id": st.session_state.student_id,
                    "topic": q_data['topic'],
                    "question_text": q_data['generated_question'],
                    "student_answer": student_answer,
                    "correct_answer": q_data['correct_answer'],
                    "time_taken": time_taken
                }
                
                with st.chat_message("assistant"):
                    with st.spinner("Analyzing your answer..."):
                        res = requests.post(f"{API_URL}/submit-answer/", json=payload).json()
                        
                        if res.get("is_correct"):
                            feedback = f"✅ **Correct!**\n\n{res['ai_feedback']}\n\n*(Time taken: {time_taken}s)*"
                        else:
                            feedback = f"❌ **Not quite.**\n\n{res['ai_feedback']}\n\n*(Time taken: {time_taken}s)*"
                
                st.session_state.chat_history.append({"role": "assistant", "content": feedback})
                
                if len(st.session_state.question_queue) > 0:
                    # Continue with the next Teacher question
                    st.session_state.current_question = st.session_state.question_queue.pop(0)
                    next_q_text = st.session_state.current_question['generated_question']
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": f"📝 **Next Question:**\n\n### {next_q_text}"
                    })
                else:
                    # Teacher questions are done. Check if we have hit the 5 AI question limit!
                    if st.session_state.ai_question_count < 5:
                        
                    
                        if st.session_state.ai_question_count == 0:
                            transition_msg = "🤖 Excellent work finishing those questions! Here are a few more to solidify your understanding..."
                        else:
                            transition_msg = "🤖 Here is your next question..."
                            
                        st.session_state.chat_history.append({"role": "assistant", "content": transition_msg})
                        
                        # Generate the AI question
                        res_ai = requests.post(f"{API_URL}/generate-question/", json={
                            "topic": st.session_state.current_topic, 
                            "difficulty": st.session_state.current_difficulty
                        })
                        st.session_state.current_question = res_ai.json()
                        next_q_text = st.session_state.current_question['generated_question']
                        
                        st.session_state.chat_history.append({
                            "role": "assistant", 
                            "content": f"### {next_q_text}"
                        })
                        
                        # Increment the AI question counter
                        st.session_state.ai_question_count += 1
                        
                    else:
                        
                        st.session_state.quiz_finished = True
                        st.session_state.current_question = None
                        st.session_state.chat_history.append({
                            "role": "assistant", 
                            "content": "🎉 **Great job! You have successfully completed all the questions for this topic.** \n\nYou can proceed to the next topic by selecting it in the sidebar menu!"
                        })
                
                st.session_state.start_time = time.time()
                st.rerun()

    with tab_progress:
        st.title("Your Learning Dashboard")
        st.markdown("Review your performance across all subjects.")
        
        with st.spinner("Fetching your data..."):
            res = requests.get(f"{API_URL}/analytics/student-report/{st.session_state.student_id}")
            if res.status_code == 200:
                report = res.json()
                if not report.get("topic_breakdown"):
                    st.info("No data available yet. Complete a quiz to see your progress here!")
                else:
                    for row in report["topic_breakdown"]:
                        with st.container(border=True):
                            st.subheader(row['topic'])
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Questions Attempted", row['questions_attempted'])
                            c2.metric("Average Score", f"{row['average_score']:.1f}%")
                            c3.metric("Avg Time per Q", f"{row['average_time_seconds']:.1f}s")

# 3. TEACHER DASHBOARD

elif st.session_state.role == "teacher":
    with st.sidebar:
        st.header("👨‍🏫 Teacher Portal")
        st.info("Logged in as Administrator")
        if st.button("Logout", use_container_width=True):
            logout()

    st.title("School Administrator Portal")
    
    tab_analytics, tab_qbank = st.tabs(["📊 Analytics Overview", "📝 Manage Question Bank"])
    
    with tab_analytics:
        st.markdown("Monitor student performance and identify areas requiring attention.")
        st.divider()
        col_kpi1, col_kpi2 = st.columns(2)
        
        with col_kpi1:
            st.subheader("🔥 Hardest Subject")
            res2 = requests.get(f"{API_URL}/analytics/hardest-topic/")
            if res2.status_code == 200 and "topic" in res2.json():
                hardest_data = res2.json()
                st.metric(label="Subject with lowest average score", 
                          value=hardest_data['topic'], 
                          delta=f"{hardest_data['average_score']:.1f}% Average Score", 
                          delta_color="inverse")
            else:
                st.info("Not enough data to calculate the hardest subject.")
                
        with col_kpi2:
            st.subheader("⚠️ At-Risk Students")
            res = requests.get(f"{API_URL}/analytics/struggling-students/60")
            if res.status_code == 200:
                struggling_data = res.json().get("struggling_students",[])
                if struggling_data:
                    for s in struggling_data:
                        st.error(f"**{s['name']}**  —  Average Score: {s['average_score']:.1f}%")
            else:
                st.success("🎉 All students are performing above 60%!")

    with tab_qbank:
        st.markdown("Add official curriculum questions to the database. Students will see these before AI-generated questions.")
        
        with st.form("add_question_form", clear_on_submit=True):
            q_topic = st.selectbox("Topic", ["Python Programming", "SQL Databases", "Data Science", "Web Development"])
            q_diff = st.select_slider("Difficulty", options=["beginner", "intermediate", "advanced"])
            
            q_text = st.text_area("Question Text", placeholder="e.g., What keyword is used to define a function in Python?")
            q_ans = st.text_input("Correct Answer", placeholder="e.g., def")
            
            submit_q = st.form_submit_button("💾 Save Question to Database")
            
            if submit_q:
                if q_text and q_ans:
                    payload = {
                        "topic": q_topic,
                        "difficulty": q_diff,
                        "question_text": q_text,
                        "correct_answer": q_ans
                    }
                    res = requests.post(f"{API_URL}/teacher-questions/", json=payload)
                    if res.status_code == 200:
                        st.success("✅ Question added successfully! The form has been reset for your next question.")
                    else:
                        st.error("❌ Failed to add question.")
                else:
                    st.warning("Please fill in both the Question Text and Correct Answer.")