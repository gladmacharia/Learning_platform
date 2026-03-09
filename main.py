import os
from fastapi import FastAPI
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from database import init_db, get_db_connection
from schemas import StudentCreate,AnswerSubmission,QuestionRequest,TeacherQuestionCreate
from ai import get_ai_feedback,generate_question
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up... Connecting to Aiven Database...")
    await init_db()
    yield
    print("Shutting down...")

app = FastAPI(title="Learning Platform API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {
        "message": "Welcome to the Learning Platform API!",
        "AIVEN_DATABASE_URL": os.getenv("AIVEN_DATABASE_URL") is not None,
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY") is not None
    }

# Student Endpoints
@app.post("/students/")
async def create_student(student: StudentCreate):
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        new_id = await conn.fetchval(
            "INSERT INTO students (name, email) VALUES ($1, $2) RETURNING id",
            student.name, student.email
        )
        return {"message": "Student created!", "student_id": new_id}
    except Exception as e:
        return {"error": str(e)}
    finally:
        await conn.close()

@app.post("/submit-answer/")
async def submit_answer(submission: AnswerSubmission):
    is_correct = submission.student_answer.strip().lower() == submission.correct_answer.strip().lower()
    
    # Get AI feedback based on the student's answer and whether it was correct
    ai_feedback = await get_ai_feedback(
        topic=submission.topic, question=submission.question_text,
        student_answer=submission.student_answer, correct_answer=submission.correct_answer,
        is_correct=is_correct
    )
    
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        # Save individual attempt to quiz_results
        await conn.execute(
            """
            INSERT INTO quiz_results 
            (student_id, topic, question_text, answer_text, correct_answer, is_correct, time_taken, ai_feedback)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            submission.student_id, submission.topic, submission.question_text, submission.student_answer,
            submission.correct_answer, is_correct, submission.time_taken, ai_feedback
        )
        
        # UPDATE PERFORMANCE HISTORY
        history = await conn.fetchrow(
            "SELECT id, total_questions_attempted, total_correct_answers, average_time_taken FROM performance_history WHERE student_id = $1 AND topic = $2",
            submission.student_id, submission.topic
        )
        
        if history:
            # Calculate new totals and averages
            new_attempts = history['total_questions_attempted'] + 1
            new_correct = history['total_correct_answers'] + (1 if is_correct else 0)
            
            # Recalculate moving average for time
            old_total_time = history['average_time_taken'] * history['total_questions_attempted']
            new_avg_time = (old_total_time + submission.time_taken) / new_attempts
            
            await conn.execute(
                """
                UPDATE performance_history 
                SET total_questions_attempted = $1, total_correct_answers = $2, 
                    average_time_taken = $3, last_updated = CURRENT_TIMESTAMP
                WHERE id = $4
                """, new_attempts, new_correct, new_avg_time, history['id']
            )
        else:
            # Create a brand new record for this topic
            await conn.execute(
                """
                INSERT INTO performance_history (student_id, topic, total_questions_attempted, total_correct_answers, average_time_taken)
                VALUES ($1, $2, 1, $3, $4)
                """, submission.student_id, submission.topic, (1 if is_correct else 0), float(submission.time_taken)
            )
            
        return {"is_correct": is_correct, "ai_feedback": ai_feedback}
        
    except Exception as e:
        return {"error": f"Failed to save to database: {str(e)}"}
    finally:
        await conn.close()

@app.post("/generate-question/")
async def get_new_question(request: QuestionRequest):
    # Ask the AI to generate a question
    question_data = await generate_question(
        topic=request.topic, 
        difficulty=request.difficulty
    )
    
    if "error" in question_data:
        return {"error": "Failed to generate question. Try again."}
        
    return {
        "topic": request.topic,
        "difficulty": request.difficulty,
        "generated_question": question_data["question"],
        "correct_answer": question_data["correct_answer"]
    }

@app.get("/analytics/struggling-students/{threshold}")
async def get_struggling_students(threshold: float):
    """
    Finds students whose average score (percentage) is below the given threshold.
    """
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        # We join students and quiz_results. 
        query = """
            SELECT s.id, s.name, 
                   (AVG(CASE WHEN q.is_correct THEN 1.0 ELSE 0.0 END) * 100) as average_score
            FROM students s
            JOIN quiz_results q ON s.id = q.student_id
            GROUP BY s.id, s.name
            HAVING (AVG(CASE WHEN q.is_correct THEN 1.0 ELSE 0.0 END) * 100) < $1
        """
        records = await conn.fetch(query, threshold)
        
        # Convert the database records to a list of dictionaries
        return {"struggling_students": [dict(record) for record in records]}
    finally:
        await conn.close()

@app.get("/analytics/hardest-topic/")
async def get_hardest_topic():
    """
    Finds the topic with the lowest average score across all students.
    """
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        query = """
            SELECT topic, 
                   (AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) * 100) as average_score
            FROM quiz_results
            GROUP BY topic
            ORDER BY average_score ASC
            LIMIT 1
        """
        record = await conn.fetchrow(query)
        
        if record:
            return dict(record)
        return {"message": "No quiz data available yet."}
    finally:
        await conn.close()

@app.get("/analytics/student-report/{student_id}")
async def get_student_report(student_id: int):
    """
    Shows a specific student's performance broken down by topic.
    """
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        query = """
            SELECT topic,
                   COUNT(id) as questions_attempted,
                   (AVG(CASE WHEN is_correct THEN 1.0 ELSE 0.0 END) * 100) as average_score,
                   AVG(time_taken) as average_time_seconds
            FROM quiz_results
            WHERE student_id = $1
            GROUP BY topic
        """
        records = await conn.fetch(query, student_id)
        
        return {
            "student_id": student_id,
            "topic_breakdown": [dict(record) for record in records]
        }
    finally:
        await conn.close()

@app.get("/students/{email}")
async def get_student_by_email(email: str):
    """Checks if a student exists by email and returns their data."""
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
    
    try:
        # Search the database for this email
        record = await conn.fetchrow(
            "SELECT id, name, email FROM students WHERE email = $1", 
            email
        )
        if record:
            return dict(record) # Student exists!
        return {"error": "Student not found"} # Student does not exist
    finally:
        await conn.close()

# TEACHER QUESTION ENDPOINTS

@app.post("/teacher-questions/")
async def add_teacher_question(q: TeacherQuestionCreate):
    """Allows a teacher to save a specific question to the database."""
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        await conn.execute(
            """
            INSERT INTO teacher_questions (topic, difficulty, question_text, correct_answer)
            VALUES ($1, $2, $3, $4)
            """,
            q.topic, q.difficulty, q.question_text, q.correct_answer
        )
        return {"message": "Question added to the Question Bank successfully!"}
    except Exception as e:
        return {"error": f"Failed to save question: {str(e)}"}
    finally:
        await conn.close()


@app.get("/teacher-questions/{topic}/{difficulty}")
async def get_teacher_questions(topic: str, difficulty: str):
    """Fetches up to 10 teacher questions for a specific topic and difficulty."""
    conn = await get_db_connection()
    if not conn:
        return {"error": "Database connection failed"}
        
    try:
        # We fetch up to 10 questions randomly from the teacher's bank
        records = await conn.fetch(
            """
            SELECT question_text as generated_question, correct_answer, topic, difficulty
            FROM teacher_questions 
            WHERE topic = $1 AND difficulty = $2
            ORDER BY RANDOM() 
            LIMIT 10
            """,
            topic, difficulty
        )
        # Convert records to a list of dictionaries
        return[dict(record) for record in records]
    finally:
        await conn.close()