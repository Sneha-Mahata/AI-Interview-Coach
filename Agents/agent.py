import google.generativeai as gen_ai
import os
from dotenv import load_dotenv
from utils.common import question_generation_prompt, evaluate_candidate
import json

load_dotenv()

class Agents:
    """
    A class to handle interactions with the Google Gemini AI model.
    """
    def __init__(self):
        """Initialize the agent with Google API key and model configuration."""
        self.GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        gen_ai.configure(api_key=self.GOOGLE_API_KEY)

        try:
            available_models = [m.name for m in gen_ai.list_models()]
            # print("🔍 Available Models:", available_models)

            # Force selection of the best Gemini model
            preferred_models = [
                "models/gemini-1.5-pro-latest",  # Best choice
                "models/gemini-1.5-pro",  
                "models/gemini-1.5-flash-latest",  # Fast but less powerful
            ]
            self.model_name = next((m for m in preferred_models if m in available_models), None)

            if not self.model_name:
                raise ValueError("❌ No valid Gemini models found. Check your API key permissions.")

            # print(f"✅ Using Google Gemini Model: {self.model_name}")
            self.model = gen_ai.GenerativeModel(self.model_name)

        except Exception as e:
            print(f"❌ Error loading models: {str(e)}")
            self.model = None

    def generate_questions(self, data):
        """Generate technical interview questions."""
        if not self.model:
            return {"error": "Model is not initialized"}
        
        prompt = question_generation_prompt(data)

        try:
            response = self.model.generate_content(prompt)
            return self._extract_json(response.text)
        except Exception as e:
            print(f"Error generating questions: {str(e)}")
            return {"error": "Failed to generate questions"}

    def evaluate_candidate(self, data):
        """Evaluate the candidate's responses."""
        if not self.model:
            return {"error": "Model is not initialized"}

        prompt = evaluate_candidate(data)

        try:
            response = self.model.generate_content(prompt)
            return self._extract_json(response.text)
        except Exception as e:
            print(f"Error evaluating candidate: {str(e)}")
            return {"error": "Failed to evaluate candidate"}

    def _extract_json(self, response_text):
        """Extract JSON content from the model's response."""
        try:
            if response_text.startswith("```") and "```" in response_text:
                start_idx = response_text.find("{")
                end_idx = response_text.rfind("}") + 1
                response_text = response_text[start_idx:end_idx]

            return json.loads(response_text)
        except json.JSONDecodeError:
            print("Failed to parse JSON from response.")
            return {"error": "Invalid JSON response from API"}
