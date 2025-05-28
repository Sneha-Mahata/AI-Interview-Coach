import os
import streamlit as st
import json
from dotenv import load_dotenv
import google.generativeai as gen_ai
from Agents.agent import Agents

# Initialize Agents
agents = Agents()

# Streamlit Page Configuration
st.set_page_config(
    page_title="Talent Scout",
    page_icon="🧊",
    layout="centered",
)

# Initialize Session State
def initialize_session_state():
    state_defaults = {
        "chat_session": agents.model.start_chat(history=[]),
        "chat_stage": 0,
        "user_data": {},
        "questions": [],
        "evaluation_data": {},
        "user_response": {},
        "evaluation_prompt": "",
    }
    for key, value in state_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

initialize_session_state()

# Helper Functions
def translate_role_for_streamlit(user_role):
    return "assistant" if user_role == "model" else user_role

def reset_and_rerun():
    st.session_state.clear()
    st.rerun()

# UI Setup
st.title("Talent Scout")
st.write("Welcome to Talent Scout! Let’s gather your information step-by-step.")
if st.button(label="Restart Process"):
    reset_and_rerun()

# Display Chat History
for message in st.session_state.chat_session.history:
    with st.chat_message(translate_role_for_streamlit(message["role"])):
        st.markdown(message["parts"][0]["text"])

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
            st.markdown(question)

        # Get User Input
        user_input = st.chat_input("Your response")
        if user_input:
            # Save response and update chat history
            st.session_state.user_data[key] = user_input
            st.session_state.chat_session.history.extend([
                {"role": "model", "parts": [{"text": question}]},
                {"role": "user", "parts": [{"text": user_input}]},
            ])
            st.session_state.chat_stage += 1
            st.rerun()
    else:
        handle_dynamic_questions()

def handle_dynamic_questions():

    if not st.session_state.questions:
        try:
            generated_questions = agents.generate_questions(st.session_state.user_data)
            st.session_state.questions = json.loads(generated_questions)
        except (json.JSONDecodeError, KeyError):
            st.error("Failed to generate additional questions. Please check the model output.")
            return

    # Ask Additional Questions
    question_keys = list(st.session_state.questions.keys())
    question_index = st.session_state.get("question_index", 0)

    if question_index < len(question_keys):
        key = question_keys[question_index]
        question = st.session_state.questions[key]

        with st.chat_message("assistant"):
            st.markdown(question)

        user_input = st.chat_input("Your response")
        if user_input:
            # Save response and update chat history
            st.session_state.user_response[question] = user_input
            st.session_state.chat_session.history.extend([
                {"role": "model", "parts": [{"text": question}]},
                {"role": "user", "parts": [{"text": user_input}]},
            ])
            st.session_state.evaluation_data[question] = user_input
            st.session_state.question_index = question_index + 1
            st.rerun()
    else:
        finalize_evaluation()

def finalize_evaluation():
    
    try:
        score = agents.evaluate_candidate_agent(st.session_state.evaluation_data)
        print("Eval data", st.session_state.evaluation_data)
        st.markdown("Thank you for your time! Our recruiter will contact you soon.")
        print("Candidate Evaluation Score:", score)
    except Exception as e:
        st.error("An error occurred during evaluation. Please try again.")
        print("Evaluation Error:", e)

# Start the Question Flow
ask_questions()
