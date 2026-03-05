from pydantic import BaseModel

class StudentCreate(BaseModel):
    name: str
    email: str

class AnswerSubmission(BaseModel):
    student_id: int
    topic: str
    question_text: str
    student_answer: str
    correct_answer: str
    time_taken: int

class QuestionRequest(BaseModel):
    topic: str
    difficulty: str

class TeacherQuestionCreate(BaseModel):
    topic: str
    difficulty: str
    question_text: str
    correct_answer: str