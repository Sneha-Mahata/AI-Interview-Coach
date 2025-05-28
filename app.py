import os
import streamlit as st
import json
from dotenv import load_dotenv
import google.generativeai as gen_ai
from Agents.agent import Agents

# Initialize Agents with error handling
try:
    agents = Agents()
except Exception as e:
    st.error(f"Failed to initialize AI agents: {str(e)}")
    st.stop()

# Streamlit Page Configuration
st.set_page_config(
    page_title="Talent Scout",
    page_icon="🧊",
    layout="centered",
)

# Initialize Session State
def initialize_session_state():
    state_defaults = {
        "chat_session": None,
        "chat_stage": 0,
        "user_data": {},
        "questions": {},
        "evaluation_data": {},
        "user_response": {},
        "evaluation_prompt": "",
        "api_error": False,
        "error_message": ""
    }
    for key, value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    
    # Initialize chat session safely
    if st.session_state.chat_session is None and agents.model:
        try:
            st.session_state.chat_session = agents.model.start_chat(history=[])
        except Exception as e:
            st.session_state.api_error = True
            st.session_state.error_message = f"Chat initialization failed: {str(e)}"

initialize_session_state()

# Helper Functions
def translate_role_for_streamlit(user_role):
    return "assistant" if user_role == "model" else user_role

def reset_and_rerun():
    st.session_state.clear()
    st.rerun()

# UI Setup
st.title("🎯 Talent Scout")
st.write("Welcome to Talent Scout! Let's gather your information step-by-step.")

# Display API status
if st.session_state.api_error:
    st.warning(f"⚠️ API Issue: {st.session_state.error_message}")
    st.info("💡 The application will use fallback questions to continue the interview process.")

col1, col2 = st.columns([1, 1])
with col1:
    if st.button(label="🔄 Restart Process"):
        reset_and_rerun()

with col2:
    if st.button(label="🧪 Test API Connection"):
        with st.spinner("Testing API connection..."):
            try:
                test_response = agents.model.generate_content("Say 'API is working'")
                st.success("✅ API connection successful!")
                st.session_state.api_error = False
            except Exception as e:
                st.error(f"❌ API connection failed: {str(e)}")
                st.session_state.api_error = True

# Display Chat History (only if chat session exists)
if st.session_state.chat_session and hasattr(st.session_state.chat_session, 'history'):
    for message in st.session_state.chat_session.history:
        with st.chat_message(translate_role_for_streamlit(message.get("role", "user"))):
            parts = message.get("parts", [])
            if parts and len(parts) > 0:
                st.markdown(parts[0].get("text", ""))

# Define Static Questions
questions = [
    ("Full Name", "What is your full name?"),
    ("Email", "What is your email address?"),
    ("Phone Number", "What is your phone number?"),
    ("Years of Experience", "How many years of experience do you have?"),
    ("Desired Position", "What is your desired position?"),
    ("Current Location", "Where are you currently located?"),
    ("Tech Stack", "What is your tech stack (e.g., Python, Django, SQL)?"),
]

# Question-Answer Flow
def ask_questions():
    if st.session_state.chat_stage < len(questions):
        key, question = questions[st.session_state.chat_stage]

        # Display Assistant's Question
        with st.chat_message("assistant"):
            st.markdown(f"**Question {st.session_state.chat_stage + 1}/7:** {question}")

        # Get User Input
        user_input = st.chat_input("Your response")
        if user_input:
            # Save response and update chat history safely
            st.session_state.user_data[key] = user_input
            
            # Update chat history if session exists
            if st.session_state.chat_session:
                try:
                    st.session_state.chat_session.history.extend([
                        {"role": "model", "parts": [{"text": question}]},
                        {"role": "user", "parts": [{"text": user_input}]},
                    ])
                except Exception as e:
                    print(f"Chat history update failed: {e}")
            
            st.session_state.chat_stage += 1
            st.rerun()
    else:
        handle_dynamic_questions()

def handle_dynamic_questions():
    # Generate questions if not already done
    if not st.session_state.questions:
        with st.spinner("🤖 Generating personalized questions..."):
            try:
                generated_questions_json = agents.generate_questions(st.session_state.user_data)
                
                # Handle both string and dict responses
                if isinstance(generated_questions_json, str):
                    st.session_state.questions = json.loads(generated_questions_json)
                elif isinstance(generated_questions_json, dict):
                    st.session_state.questions = generated_questions_json
                else:
                    raise ValueError("Unexpected response format")
                    
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                st.error("⚠️ Failed to generate personalized questions. Using default questions.")
                print(f"Question generation error: {e}")
                
                # Fallback questions based on user data
                tech_stack = st.session_state.user_data.get("Tech Stack", "general technologies")
                position = st.session_state.user_data.get("Desired Position", "the position")
                
                st.session_state.questions = {
                    "question1": f"What is your experience with {tech_stack}?",
                    "question2": f"Can you describe a challenging project you've worked on using {tech_stack}?",
                    "question3": f"How do you stay updated with the latest trends in {tech_stack}?",
                    "question4": f"What makes you a good fit for the {position} role?",
                    "question5": "What are your career goals for the next 2-3 years?"
                }

    # Ask Additional Questions
    question_keys = list(st.session_state.questions.keys())
    question_index = st.session_state.get("question_index", 0)

    if question_index < len(question_keys):
        key = question_keys[question_index]
        question = st.session_state.questions[key]

        with st.chat_message("assistant"):
            st.markdown(f"**Technical Question {question_index + 1}/5:** {question}")

        user_input = st.chat_input("Your detailed response")
        if user_input:
            # Save response and update chat history
            st.session_state.user_response[question] = user_input
            st.session_state.evaluation_data[question] = user_input
            
            if st.session_state.chat_session:
                try:
                    st.session_state.chat_session.history.extend([
                        {"role": "model", "parts": [{"text": question}]},
                        {"role": "user", "parts": [{"text": user_input}]},
                    ])
                except Exception as e:
                    print(f"Chat history update failed: {e}")
            
            st.session_state.question_index = question_index + 1
            st.rerun()
    else:
        finalize_evaluation()

def finalize_evaluation():
    with st.spinner("🔍 Evaluating your responses..."):
        try:
            # Combine all data for evaluation
            evaluation_input = {
                "user_data": st.session_state.user_data,
                "technical_responses": st.session_state.evaluation_data
            }
            
            score = agents.evaluate_candidate_agent(evaluation_input)
            
            st.success("✅ Interview completed successfully!")
            
            # Display results
            st.markdown("## 📊 Your Interview Results")
            
            if isinstance(score, dict):
                if "overall_score" in score:
                    st.metric("Overall Score", f"{score['overall_score']}/100")
                
                if "category_scores" in score:
                    st.markdown("### Category Breakdown")
                    for category, cat_score in score["category_scores"].items():
                        st.write(f"- **{category.replace('_', ' ').title()}**: {cat_score}/20")
                
                if "strengths" in score:
                    st.markdown("### 💪 Strengths")
                    for strength in score["strengths"]:
                        st.write(f"✅ {strength}")
                
                if "areas_for_improvement" in score:
                    st.markdown("### 📈 Areas for Improvement")
                    for area in score["areas_for_improvement"]:
                        st.write(f"🎯 {area}")
                
                if "detailed_feedback" in score:
                    st.markdown("### 📝 Detailed Feedback")
                    st.write(score["detailed_feedback"])
            else:
                st.write(f"Evaluation Score: {score}")
            
            st.markdown("---")
            st.markdown("**Thank you for your time! Our recruiter will contact you soon.** 📞")
            
            print("Candidate Evaluation Score:", score)
            
        except Exception as e:
            st.error("⚠️ An error occurred during evaluation. Your responses have been recorded.")
            st.markdown("**Thank you for your time! Our recruiter will contact you soon.** 📞")
            print("Evaluation Error:", e)

# Progress indicator
if st.session_state.chat_stage > 0:
    total_questions = len(questions) + 5  # 7 basic + 5 technical
    current_progress = st.session_state.chat_stage + st.session_state.get("question_index", 0)
    progress = min(current_progress / total_questions, 1.0)
    
    st.progress(progress)
    st.write(f"Progress: {current_progress}/{total_questions} questions completed")

# Start the Question Flow
ask_questions()