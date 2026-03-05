import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("AIVEN_DATABASE_URL")

async def get_db_connection():
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        return None
    
async def init_db():
    conn = await get_db_connection()
    
    if not conn:
        print("Could not initialiaze database tables because connection failed")
        return
    
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS quiz_results (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id),
                topic VARCHAR(100) NOT NULL,
                question_text TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                correct_answer TEXT,
                is_correct BOOLEAN,
                time_taken INTEGER,
                ai_feedback TEXT,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS performance_history (
                id SERIAL PRIMARY KEY,
                student_id INTEGER REFERENCES students(id),
                topic VARCHAR(100) NOT NULL,
                total_questions_attempted INTEGER DEFAULT 0,
                total_correct_answers INTEGER DEFAULT 0,
                average_time_taken FLOAT DEFAULT 0.0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- NEW TABLE FOR TEACHER QUESTIONS --
            CREATE TABLE IF NOT EXISTS teacher_questions (
                id SERIAL PRIMARY KEY,
                topic VARCHAR(100) NOT NULL,
                difficulty VARCHAR(50) NOT NULL,
                question_text TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("Database tables initialized successfully.")
    except Exception as e:
        print(f"Error initializing database tables: {e}")
        
    finally:
        await conn.close()
        