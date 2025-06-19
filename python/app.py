# --- ADDED 'sys' FOR PYINSTALLER PATHING ---
import sys
# --------------------------------------------

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, tempfile
# import sqlite3  # COMMENTED OUT
from datetime import datetime
from dotenv import load_dotenv
from transcriber import transcribe_audio
from pathlib import Path
from typing import List, Dict, Any
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logging.info("CCRAZyCCRAZyCCRAZyCCRAZyCCRAZyCCRAZy") # Using an f-string gives more context


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
logging.info(f"env_path: {env_path}")
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

# --- Database functionality is commented out as in the original file ---

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
        # First LLM call - Extract tech stack
        tech_stack_prompt = f"""
        Analyze the following job description and extract the key technical skills, programming languages, frameworks, and technologies mentioned.

        Job Description: {req.job_description}

        Return only a valid JSON object with a single key "tech_stack" containing a list of strings.
        Example: {{"tech_stack": ["Python", "React", "Docker"]}}
        """
        
        tech_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": tech_stack_prompt}],
            max_tokens=500,
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        tech_stack_text = tech_response.choices[0].message.content.strip()
        
        try:
            tech_data = json.loads(tech_stack_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError parsing tech stack: {e}")
            logging.error(f"--- Raw LLM response for tech_stack ---\n{tech_stack_text}")
            raise HTTPException(status_code=500, detail="Failed to parse tech stack from LLM.")

        tech_stack = tech_data.get("tech_stack", [])
        
        # Second LLM call - Generate general questions
        general_questions_prompt = f"""
        You are a senior technical interviewer. Generate exactly {req.num_questions} highly technical and concise interview questions for a candidate with {req.years_experience} years of experience.

        IMPORTANT: Adjust question complexity based on experience level:
        - 0-2 years: Focus on core programming concepts, data structures, algorithms basics
        - 3-5 years: System design fundamentals, optimization techniques, advanced algorithms
        - 6-8 years: Complex system architecture, scalability patterns, performance optimization
        - 9+ years: Distributed systems design, technical leadership challenges, enterprise architecture

        Job Description: {req.job_description}

        CRITICAL: You MUST return a JSON object with this EXACT structure. Each question must have answer_points with exactly 5 bullet points.
        CRITICAL: Ensure all double quotes inside JSON string values are properly escaped with a backslash (e.g., "a \\"quoted\\" word").

        {{
            "questions": [
                {{
                    "question": "Your concise technical question here",
                    "answer_points": [
                        "Key point 1", "Key point 2", "Key point 3", "Key point 4", "Key point 5"
                    ]
                }}
            ]
        }}
        """
        
        general_response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": general_questions_prompt}],
            max_tokens=1500,
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        general_questions_text = general_response.choices[0].message.content.strip()

        try:
            general_data = json.loads(general_questions_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError parsing general questions: {e}")
            logging.error(f"--- Raw LLM response for general_questions ---\n{general_questions_text}")
            raise HTTPException(status_code=500, detail="Failed to parse general questions from LLM.")
            
        general_questions = general_data.get("questions", [])
        
        # Third LLM call - Generate one question per tech stack
        tech_questions = []
        if tech_stack:
            tech_questions_prompt = f"""
            For each technology in this list: {tech_stack}
            
            Generate exactly one concise technical interview question for each technology that:
            1. Tests deep technical understanding
            2. Is appropriate for someone with {req.years_experience} years of experience
            
            CRITICAL: You MUST return a JSON object with this EXACT structure. Each question must have answer_points with exactly 5 bullet points.
            CRITICAL: Ensure all double quotes inside JSON string values are properly escaped with a backslash (e.g., "a \\"quoted\\" word").

            {{
                "tech_questions": [
                    {{
                        "technology": "Technology name",
                        "question": "Your concise technical question",
                        "answer_points": [
                            "Key point 1", "Key point 2", "Key point 3", "Key point 4", "Key point 5"
                        ]
                    }}
                ]
            }}
            """
            
            tech_questions_response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": tech_questions_prompt}],
                max_tokens=1500,
                temperature=0.7,
                response_format={"type": "json_object"}
            )
            tech_questions_text = tech_questions_response.choices[0].message.content.strip()

            try:
                tech_questions_data = json.loads(tech_questions_text)
            except json.JSONDecodeError as e:
                logging.error(f"JSONDecodeError parsing tech questions: {e}")
                logging.error(f"--- Raw LLM response for tech_questions ---\n{tech_questions_text}")
                raise HTTPException(status_code=500, detail="Failed to parse tech-specific questions from LLM.")

            tech_questions = tech_questions_data.get("tech_questions", [])
        
        all_questions = {
            "general_questions": general_questions,
            "tech_questions": tech_questions,
            "tech_stack": tech_stack
        }
        
        return {"questions": all_questions}
        
    except HTTPException:
        raise # Re-raise the specific HTTPException from inner blocks
    except Exception as e:
        logging.error(f"An unexpected error occurred in generate_questions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.post("/evaluate-answer")
def evaluate_answer(data: AnswerRequest):
    prompt = f"""
    You are a senior technical interviewer evaluating a candidate's answer to a technical question. Assess the answer for accuracy, depth, and clarity.
    
    Provide a score from 1 to 10 and detailed feedback.
    
    CRITICAL: Return your response strictly in the following JSON format. Ensure any double quotes in the feedback are escaped.
    {{
        "grade": "a score between 1 and 10", 
        "feedback": "technically detailed feedback"
    }}

    Question: {data.question}
    Answer: {data.answer}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError parsing evaluation: {e}")
            logging.error(f"--- Raw LLM response for evaluation ---\n{response_text}")
            raise HTTPException(status_code=500, detail="Failed to parse evaluation from LLM.")

        grade = result.get("grade", "0")
        feedback = result.get("feedback", "No feedback provided")
        
        logging.info(f"Evaluation result: {result}")
        return {"grade": grade, "feedback": feedback}
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error evaluating answer: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to evaluate answer: {str(e)}")

@app.post("/transcribe-audio")
async def transcribe(file: UploadFile = File(...)):
    path = None
    try:
        suffix = Path(file.filename).suffix if file.filename else ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            path = tmp.name
        
        result = transcribe_audio(client, path)
        return {"transcript": result}
        
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {str(e)}")
    finally:
        if path and os.path.exists(path):
            os.remove(path)
    
@app.post("/final-evaluation")
async def final_evaluation(data: FinalEvaluationRequest):
    prompt = f"""You are a senior technical interviewer providing a final, critical evaluation. Be strict and do not inflate scores.

    Candidate Name: {data.candidate_name}
    Years of Experience: {getattr(data, 'years_experience', 'N/A')}
    Job Description: {data.job_description}

    Interview Questions, Answers, and Feedback:
    """
    for i, qa in enumerate(data.qa_pairs, 1):
        prompt += f"\nQ{i}: {qa.get('question', 'N/A')}\n"
        prompt += f"A{i}: {qa.get('answer', 'N/A')}\n"
        if qa.get('feedback'):
            prompt += f"Feedback: {qa.get('feedback')}\n"

    prompt += f"""
    Based on the above, provide a comprehensive final evaluation.

    CRITICAL: Format your response as a valid JSON object with these exact keys: "overall_score", "strengths", "areas_for_improvement", "technical_assessment", "recommendations".
    - "overall_score" should be an integer from 0-100.
    - All other fields should be strings. Ensure any double quotes within these strings are properly escaped.
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Consider gpt-4-turbo for higher quality evaluation
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.5
        )
        response_text = response.choices[0].message.content.strip()

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"JSONDecodeError parsing final evaluation: {e}")
            logging.error(f"--- Raw LLM response for final_evaluation ---\n{response_text}")
            raise HTTPException(status_code=500, detail="Failed to parse final evaluation from LLM.")
            
        return {
            "success": True,
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in final evaluation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate final evaluation: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5002, reload=False)