# --- ADDED 'sys' FOR PYINSTALLER PATHING ---
import sys 
# --------------------------------------------

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, sqlite3, tempfile
from datetime import datetime
from dotenv import load_dotenv
from transcriber import transcribe_audio
from pathlib import Path
from typing import List, Dict, Any
import json
import logging
from fastapi import HTTPException


logging.basicConfig(
    level=logging.INFO,  # Show INFO and above
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.info("------------------------------------------------") # Using an f-string gives more context


# --- THIS FUNCTION IS REQUIRED FOR PYINSTALLER TO FIND DATA FILES ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
# -------------------------------------------------------------------


# --- MODIFIED TO USE resource_path ---
# Load environment variables from the correct path
env_path = resource_path(".env")
load_dotenv(dotenv_path=env_path)
# --------------------------------------


# Initialize OpenAI client properly
from openai import OpenAI
import os


# Initialize OpenAI client properly using its default, robust settings.
# It will handle SSL verification correctly.
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


# Initialize FastAPI
app = FastAPI()

# Updated CORS configuration - place this right after app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODIFIED TO USE resource_path ---
# Resolve DB path using the robust function
DB_PATH = Path(resource_path("db.sqlite3"))
# --------------------------------------


# Initialize the database
def init_db():
    if not DB_PATH.exists():
        print(f"Creating new database at {DB_PATH}")
    try:
        # Ensure directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS qa (
                    id INTEGER PRIMARY KEY,
                    question TEXT,
                    answer TEXT,
                    score TEXT,
                    feedback TEXT,
                    created_at TEXT
                )
            ''')
            conn.commit()
        print("Database initialized successfully")
    except Exception as e:
        print(f"[ERROR] DB initialization failed: {e}")

init_db()

# Models
class JDRequest(BaseModel):
    job_description: str
    num_questions: int = 5
    years_experience: int = 0  # NEW FIELD

class FinalEvaluationRequest(BaseModel):
    job_description: str
    qa_pairs: List[dict]
    candidate_name: str
    years_experience: int = 0  # NEW FIELD

class AnswerRequest(BaseModel):
    question: str
    answer: str

    class Config:
        extra = 'allow'
        
# Add test endpoints
@app.get("/")
def read_root():
    return {"message": "AI Interview Assistant API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

# Routes
@app.post("/generate-questions")
def generate_questions(req: JDRequest):
    try:
        # First LLM call - Extract tech stack (no changes)
        tech_stack_prompt = f"""
        Analyze the following job description and extract the key technical skills, programming languages, frameworks, and technologies mentioned:

        Job Description: {req.job_description}

        Return only a JSON object with a "tech_stack" key containing a list of technologies:
        """
        
        tech_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": tech_stack_prompt}],
            max_tokens=500,
            temperature=0.3
        )
        
        tech_stack_text = tech_response.choices[0].message.content.strip()
        # Parse the JSON response
        tech_data = json.loads(tech_stack_text)
        tech_stack = tech_data.get("tech_stack", [])
        
        # Second LLM call - Generate general questions based on num_questions and years_experience
        general_questions_prompt = f"""
        Based on the following job description and a candidate with {req.years_experience} years of experience, generate exactly {req.num_questions} interview questions that assess the candidate's overall fit for the role, behavioral aspects, and general technical understanding.

        Job Description: {req.job_description}

        Return a JSON object with a "questions" key containing a list of {req.num_questions} questions:
        """
        
        general_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": general_questions_prompt}],
            max_tokens=1000,
            temperature=0.7
        )
        
        general_questions_text = general_response.choices[0].message.content.strip()
        general_data = json.loads(general_questions_text)
        general_questions = general_data.get("questions", [])
        
        # Third LLM call - Generate one question per tech stack
        tech_questions = []
        if tech_stack:
            tech_questions_prompt = f"""
            For each technology in this list: {tech_stack}
            
            Generate exactly one technical interview question for each technology that tests practical knowledge and understanding.
            
            Return a JSON object with a "tech_questions" key containing a list of objects, each with "technology" and "question" fields:
            """
            
            tech_questions_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": tech_questions_prompt}],
                max_tokens=1000,
                temperature=0.7
            )
            
            tech_questions_text = tech_questions_response.choices[0].message.content.strip()
            tech_questions_data = json.loads(tech_questions_text)
            tech_questions = tech_questions_data.get("tech_questions", [])
        
        # Combine all questions
        all_questions = {
            "general_questions": general_questions,
            "tech_questions": tech_questions,
            "tech_stack": tech_stack
        }
        
        return {"questions": all_questions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating questions: {str(e)}")

@app.post("/evaluate-answer")
def evaluate_answer(data: AnswerRequest):
    try:
        # prompt = f"""You are a technical interviewer. Rate the following answer on a scale of 1 to 10 and provide feedback.\n\nQuestion: {data.question}\nAnswer: {data.answer}.
        # """
        prompt = f"""
        You are a senior technical interviewer evaluating a candidate's answer to a technical question. Carefully assess the answer for:
        -Technical accuracy and depth
        -Relevance to the question
        -Use of appropriate terminology and concepts
        -Clarity and completeness of explanation

        Provide a detailed evaluation using technical language where applicable. Then rate the answer on a scale of 1 to 10, where 10 reflects an excellent, technically thorough, and well-structured response.
        Return your response strictly in the following JSON format:

        {{ "grade": "<score between 1 and 10>", "feedback": "<technically detailed feedback that summarizes the correctness, terminology used, understanding of the concept, and quality of explanation>" }}

        Question: {data.question}Answer: {data.answer}
        """
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        grade = result.get("grade", 0)
        feedback = result.get("feedback", "No feedback provided")
        
        logging.info(f"result: {result}")
        
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO qa (question, answer, score, feedback, created_at) VALUES (?, ?, ?, ?, ?)",
                (data.question, data.answer, "NA", feedback, datetime.now().isoformat())
            )
            conn.commit()
            
        return {"grade": grade, "feedback": feedback}
        
    except Exception as e:
        print(f"Error evaluating answer: {e}")
        return {"error": f"Failed to evaluate answer: {str(e)}"}, 500

@app.post("/transcribe-audio")
async def transcribe(file: UploadFile = File(...)):
    try:
        suffix = os.path.splitext(file.filename)[-1] if file.filename else ".wav"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            path = tmp.name
        
        # Pass the initialized client to the function
        result = transcribe_audio(client, path)
        os.remove(path)
        
        return {"transcript": result}
        
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        return {"error": f"Failed to transcribe audio: {str(e)}"}, 500
    

@app.post("/final-evaluation")
async def final_evaluation(data: FinalEvaluationRequest):
    try:
        # Collect feedbacks if available
        feedbacks = [qa.get('feedback', '') for qa in data.qa_pairs if qa.get('feedback')]
        feedbacks_text = "\n".join([f"Q{i+1} Feedback: {fb}" for i, fb in enumerate(feedbacks)]) if feedbacks else "No feedbacks provided."

        prompt = f"""You are a senior technical interviewer. Please provide a final evaluation for the candidate based on their interview performance.
        Be highly critical and strict in your assessment. Do NOT be generous or lenient. Point out every weakness and only praise truly exceptional strengths.

        Candidate Name: {data.candidate_name}
        Years of Experience: {getattr(data, 'years_experience', 'N/A')}

        Job Description:
        {data.job_description}

        Interview Questions and Answers:
        """
        for i, qa in enumerate(data.qa_pairs, 1):
            prompt += f"\nQuestion {i}: {qa.get('question', 'No question')}"
            prompt += f"\nAnswer: {qa.get('answer', 'No answer provided')}\n"
            if qa.get('feedback'):
                prompt += f"Feedback: {qa.get('feedback')}\n"

        prompt += f"""
        Feedbacks from previous evaluations:
        {feedbacks_text}

        Please provide a comprehensive final evaluation including:
        1. Overall score (0-100)
        2. Strengths demonstrated
        3. Areas for improvement
        4. Technical competence assessment
        5. Recommendations for next steps

        Be strict and do not inflate scores or feedback. Format your response as JSON with these keys: overall_score, strengths, areas_for_improvement, technical_assessment, recommendations
        """
        
        logging.info(f"prompt for final evaluation: {prompt}")
        
        # Call GPT-4 for evaluation
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        # log the prompt
        logging.info(f"prompt for final evaluation: {prompt}")
        
        # Parse the response
        result = json.loads(response.choices[0].message.content)
        
        # Store the evaluation in the database
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY,
                    candidate_name TEXT,
                    overall_score INTEGER,
                    evaluation_json TEXT,
                    created_at TEXT
                )
            ''')
            cursor.execute(
                """
                INSERT INTO evaluations 
                (candidate_name, overall_score, evaluation_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    data.candidate_name,
                    result.get("overall_score", 0),
                    json.dumps(result),
                    datetime.now().isoformat()
                )
            )
            conn.commit()
        
        return {
            "success": True,
            **result
        }
        
    except Exception as e:
        print(f"Error in final evaluation: {str(e)}")
        return {"error": f"Failed to generate final evaluation: {str(e)}", "success": False}, 500

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5001, reload=False)