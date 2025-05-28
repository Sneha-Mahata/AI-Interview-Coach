import os
import streamlit as st
import json
from dotenv import load_dotenv
import google.generativeai as gen_ai
from Agents.agent import Agents
import PyPDF2
from docx import Document
import io

# Initialize Agents
agents = Agents()

# Streamlit Page Configuration
st.set_page_config(
    page_title="InterviewMate",
    page_icon="👨‍💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS [Previous CSS remains the same]
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        width: 100%;
        border-radius: 5px;
        height: 3em;
        background-color: #ff4b4b;
        color: white;
        font-weight: bold;
    }
    .stTextInput>div>div>input {
        border-radius: 5px;
    }
    .stHeader {
        background-color: #262730;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .success-message {
        padding: 1rem;
        border-radius: 5px;
        background-color: #d4edda;
        color: #155724;
        margin: 1rem 0;
    }
    .resume-preview {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #dee2e6;
        margin-top: 1rem;
    }
    .analysis-section {
        background-color: #e9ecef;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# Initialize Session State
def initialize_session_state():
    state_defaults = {
        "chat_session": agents.model.start_chat(history=[]),
        "user_data": {},
        "evaluation_data": {},
        "resume_text": "",
        "resume_analysis": None,
        "position_selected": False,
        "technical_questions": None,
        "current_question_index": 0,
        "answers": {},
        "evaluation_complete": False
    }
    for key, value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# [File Processing Functions remain the same]
def extract_text_from_pdf(pdf_file):
    try:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}")
        return ""

def extract_text_from_docx(docx_file):
    try:
        docx_bytes = io.BytesIO(docx_file.read())
        doc = Document(docx_bytes)
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text
    except Exception as e:
        st.error(f"Error reading DOCX: {str(e)}")
        return ""

def handle_file_upload(uploaded_file):
    try:
        if uploaded_file.type == "application/pdf":
            return extract_text_from_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return extract_text_from_docx(uploaded_file)
        else:
            st.error("Unsupported file format. Please upload a PDF or DOCX file.")
            return ""
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
        return ""

def analyze_resume(resume_text):
    analysis_prompt = f"""
    Analyze the following resume to extract key technical information and generate a structured summary:
    {resume_text}

    Focus on:
    1. Technical skills and proficiency levels
    2. Years of experience with each technology
    3. Project highlights and technical achievements
    4. Technical roles and responsibilities
    5. Areas that need clarification or more detail

    Provide analysis in JSON format with these keys:
    - primary_skills
    - experience_summary
    - key_projects
    - areas_for_clarification
    - suggested_question_topics
    
    Return ONLY the JSON object with no surrounding text, code blocks, or markdown.
    """
    
    response = None
    
    try:
        response = agents.model.generate_content(analysis_prompt)
        response_text = response.text.strip()
        
        # Check if response is wrapped in code blocks and extract just the JSON
        if response_text.startswith("```") and "```" in response_text:
            # Extract text between the first and last backtick markers
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx >= 0 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]
        
        # Now try to parse the JSON
        return json.loads(response_text)
    except Exception as e:
        st.error(f"Error analyzing resume: {str(e)}")
        
        if response is not None:
            st.error(f"Raw response: {response.text}")
            
            # Try to extract and parse the JSON as a fallback
            try:
                response_text = response.text.strip()
                if "```json" in response_text:
                    # Extract text between ```json and the last ```
                    json_content = response_text.split("```json")[1].split("```")[0].strip()
                    return json.loads(json_content)
            except:
                pass  # If this fails too, we'll use the default fallback
        
        # Return a fallback structure
        return {
            "primary_skills": ["Could not parse skills"],
            "experience_summary": "Could not parse experience",
            "key_projects": ["Could not parse projects"],
            "areas_for_clarification": ["Need complete resume review"],
            "suggested_question_topics": ["Basic skills assessment"]
        }


# Modified Question Generation Based on Resume and Position
def generate_technical_questions(resume_analysis, position):
    def format_list(items):
        if not items:
            return []
        formatted = []
        for item in items:
            if isinstance(item, dict):
                formatted.append(str(item.get('name', item.get('skill', str(item)))))
            elif isinstance(item, str):
                formatted.append(item)
            else:
                formatted.append(str(item))
        return formatted

    skills = format_list(resume_analysis.get('primary_skills', []))
    projects = format_list(resume_analysis.get('key_projects', []))
    experience = str(resume_analysis.get('experience_summary', ''))
    suggested_topics = format_list(resume_analysis.get('suggested_question_topics', []))

    # Ensure there are enough skills to avoid out-of-range errors
    skill_1 = skills[0] if len(skills) > 0 else "a relevant skill"
    skill_2 = skills[1] if len(skills) > 1 else "another relevant skill"

    # Prompt with safe skill placeholders
    question_prompt = f"""
    You are a technical interviewer. Generate **10 UNIQUE and DIVERSE** interview questions for a candidate.

    **Candidate Resume Details:**
    - **Position Applied:** {position}
    - **Skills:** {', '.join(skills) if skills else 'Not specified'}
    - **Projects:** {', '.join(projects) if projects else 'Not specified'}
    - **Experience Summary:** {experience}
    - **Suggested Topics:** {', '.join(suggested_topics) if suggested_topics else 'Not specified'}

    **STRICT RULES FOR QUESTION DIVERSITY:**
    - **2 questions about past projects** (real-world challenges).
    - **3 questions about primary technical skills** (deep-dive into hands-on experience).
    - **2 system design or architecture questions** (scalability and performance).
    - **3 problem-solving or algorithm-based questions** (require explanations).
    - **Each question must be unique.**
    - **Ensure the difficulty level increases from Question 1 to 10.**
    
    **Examples of Unique Questions (DO NOT COPY, FOLLOW THIS PATTERN):**
    1. **(Project-Based)** "Can you describe a challenging problem you faced in {projects[0] if projects else 'one of your projects'} and how you solved it?"
    2. **(Skill-Based)** "How does {skill_1} compare to {skill_2} in terms of performance and scalability?"
    3. **(System Design)** "How would you design a fault-tolerant system for a {position} role?"
    
    **Output JSON Format (STRICTLY JSON ONLY, NO EXTRA TEXT):**
    {{
        "question1": {{ "question": "...", "type": "project/skill/design/problem", "focus_area": "specific skill or project" }},
        ...
        "question10": {{ "question": "...", "type": "project/skill/design/problem", "focus_area": "specific skill or project" }}
    }}
    """

    try:
        response = agents.model.generate_content(question_prompt)
        response_text = response.text.strip()

        if response_text.startswith("```") and "```" in response_text:
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            response_text = response_text[start_idx:end_idx]

        questions = json.loads(response_text)

        # Ensure all 10 questions exist, otherwise fill with defaults
        for i in range(1, 11):
            question_key = f"question{i}"
            if question_key not in questions:
                questions[question_key] = {
                    "question": f"Describe your experience with {position} related technologies.",
                    "type": "general",
                    "focus_area": "general experience"
                }

        return questions

    except Exception as e:
        st.error(f"Error generating questions: {str(e)}")

        fallback_questions = {}
        for i in range(1, 11):
            fallback_questions[f"question{i}"] = {
                "question": f"Question {i}: Please describe your experience with {position} related technologies.",
                "type": "general",
                "focus_area": "general experience"
            }
        return fallback_questions


# UI Components
def display_header():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image("https://t3.ftcdn.net/jpg/01/59/70/58/360_F_159705804_8pLFABYtKSR5rCnQf8TbmIxgBpWfZC0X.jpg", caption="InterviewMate", width=150)
        st.title("InterviewMate")
        st.markdown("""
        <div class='stHeader'>
            <p>Welcome to <b>InterviewMate</b>! Let's analyze your profile and find the perfect match.</p>
            <ol>
                <li>Upload your resume/CV </li>
                <li>Select the position you're applying for</li>
                <li>Complete the technical assessment</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)

def display_position_selection():
    st.subheader("🎯 Select Position")
    positions = [
        "Software Engineer",
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "DevOps Engineer",
        "Data Scientist",
        "Machine Learning Engineer",
        "Other"
    ]
    
    selected_position = st.selectbox(
        "What position are you applying for?",
        positions
    )
    
    if selected_position == "Other":
        custom_position = st.text_input("Please specify the position:")
        if custom_position:
            selected_position = custom_position
    
    if st.button("Continue with Assessment"):
        st.session_state.position_selected = True
        with st.spinner("Generating position-specific questions..."):
            st.session_state.technical_questions = generate_technical_questions(
                st.session_state.resume_analysis,
                selected_position
            )
        st.rerun()

def display_technical_assessment():
    if not st.session_state.technical_questions or st.session_state.evaluation_complete:
        return

    current_question_data = st.session_state.technical_questions.get(
        f"question{st.session_state.current_question_index + 1}"
    )
    
    # Handle both dict and string formats for backward compatibility
    if isinstance(current_question_data, dict):
        current_question = current_question_data.get('question')
        question_type = current_question_data.get('type', 'general')
        focus_area = current_question_data.get('focus_area', 'general')
    else:
        current_question = current_question_data
        question_type = 'general'
        focus_area = 'general'
    
    # Display progress
    st.progress((st.session_state.current_question_index) / 10)
    st.write(f"Question {st.session_state.current_question_index + 1} of 10")
    
    # Display question metadata
    st.markdown(f"**Type:** {question_type.capitalize()}")
    st.markdown(f"**Focus Area:** {focus_area.capitalize()}")
    
    # Display current question
    st.markdown(f"### {current_question}")
    
    # Use a unique key for the text area to force clearing
    answer = st.text_area(
        "Your Answer:", 
        height=150, 
        key=f"answer_area_{st.session_state.current_question_index}"
    )
    
    if st.button("Next Question" if st.session_state.current_question_index < 9 else "Submit Assessment"):
        if answer.strip():
            # Save answer with metadata
            question_key = f"question{st.session_state.current_question_index + 1}"
            st.session_state.answers[question_key] = {
                'question': current_question,
                'type': question_type,
                'focus_area': focus_area,
                'answer': answer
            }
            
            if st.session_state.current_question_index < 9:
                st.session_state.current_question_index += 1
                st.rerun()
            else:
                evaluate_responses()
        else:
            st.warning("Please provide an answer before continuing.")


def evaluate_responses():
    """
    Evaluates candidate interview responses and generates a detailed assessment.
    """
    # Input validation
    if 'answers' not in st.session_state or 'resume_analysis' not in st.session_state:
        st.error("Missing required session state data")
        return None
        
    if len(st.session_state.answers) != 10:
        st.warning(f"Expected 10 answers, got {len(st.session_state.answers)}")
        return None

    # Evaluation process
    with st.spinner("Evaluating your responses..."):
        try:
            # Prepare evaluation data - ensure clean JSON serialization
            evaluation_data = {
                "resume_analysis": st.session_state.resume_analysis,
                "answers": st.session_state.answers
            }
            
            # Construct evaluation prompt with robust error handling
            evaluation_prompt = f"""
Carefully evaluate the candidate's technical interview responses.

Resume Analysis:
{json.dumps(evaluation_data['resume_analysis'], indent=2)}

Candidate Answers:
{json.dumps(evaluation_data['answers'], indent=2)}

**Evaluation Instructions:**
1. Assess technical knowledge, problem-solving, and communication skills
2. Compare answers against resume skills and experience
3. Provide constructive feedback
4. Return ONLY a valid JSON response with:
   - overall_score (0-100)
   - category_scores (0-20 for each category)
   - strengths (list of strings)
   - areas_for_improvement (list of strings)
   - detailed_feedback (string)

Return the JSON WITHOUT any additional text or formatting.
"""
            
            try:
                # Generate evaluation with error handling
                response = agents.model.generate_content(evaluation_prompt)
                
                # Clean response text - remove any potential code blocks or extra formatting
                response_text = response.text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text.replace("```json", "").replace("```", "").strip()
                
                # Parse JSON with additional error handling
                try:
                    evaluation_result = json.loads(response_text)
                except json.JSONDecodeError:
                    st.error(f"JSON Parsing Error. Raw response: {response_text}")
                    return None
                
                # Validate required keys
                required_keys = [
                    "overall_score", "category_scores", 
                    "strengths", "areas_for_improvement", 
                    "detailed_feedback"
                ]
                
                if not all(key in evaluation_result for key in required_keys):
                    st.error("Evaluation result missing required fields")
                    return None
                
                # Display results (same as previous implementation)
                st.markdown("## Evaluation Results")
                
                # Display overall score with color coding
                score = evaluation_result["overall_score"]
                score_color = (
                    "red" if score < 60 
                    else "orange" if score < 75 
                    else "green"
                )
                st.markdown(
                    f"### Overall Score: "
                    f"<span style='color:{score_color}'>{score}/100</span>", 
                    unsafe_allow_html=True
                )
                
                # Display category scores
                st.markdown("### Category Scores")
                for category, score in evaluation_result["category_scores"].items():
                    st.write(f"- {category.replace('_', ' ').title()}: {score}/20")
                
                # Display strengths and improvements
                st.markdown("### Key Strengths")
                for strength in evaluation_result["strengths"]:
                    st.write(f"- {strength}")
                    
                st.markdown("### Areas for Improvement")
                for area in evaluation_result["areas_for_improvement"]:
                    st.write(f"- {area}")
                
                st.markdown("### Detailed Feedback")
                st.write(evaluation_result["detailed_feedback"])
                
                return evaluation_result
                
            except Exception as e:
                st.error(f"Evaluation generation failed: {str(e)}")
                return None
                
        except Exception as e:
            st.error(f"Evaluation process failed: {str(e)}")
            return None


# Main App Flow
def main():
    display_header()
    
    # Step 1: Resume Upload
    if not st.session_state.resume_analysis:
        st.subheader("📄 Upload Resume/CV")
        uploaded_file = st.file_uploader("Upload your resume (PDF or DOCX)", type=['pdf', 'docx'])
        
        if uploaded_file:
            resume_text = handle_file_upload(uploaded_file)
            if resume_text:
                with st.spinner("Analyzing resume..."):
                    st.session_state.resume_analysis = analyze_resume(resume_text)
                st.rerun()
    
    # Step 2: Position Selection
    elif not st.session_state.position_selected:
        display_position_selection()
    
    # Step 3: Technical Assessment
    else:
        display_technical_assessment()
    
    if st.button("Reset Application"):
        st.session_state.clear()
        st.rerun()

if __name__ == "__main__":
    main()