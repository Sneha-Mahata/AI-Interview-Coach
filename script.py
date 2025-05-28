import google.generativeai as gen_ai
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables")
else:
    gen_ai.configure(api_key=API_KEY)
    try:
        models = gen_ai.list_models()
        for model in models:
            print(f"Model Name: {model.name}, Supported Methods: {model.supported_generation_methods}")
    except Exception as e:
        print("Error accessing Gemini API:", e)
