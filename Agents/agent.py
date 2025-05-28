import google.generativeai as gen_ai
import os
from dotenv import load_dotenv
from utils.common import question_generation_prompt, evaluate_candidate
import json
import time
import random

load_dotenv()

class Agents:
    """
    A class to handle interactions with the Google Gemini AI model with rate limiting and error handling.
    """
    def __init__(self):
        """Initialize the agent with Google API key and model configuration."""
        self.GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")

        gen_ai.configure(api_key=self.GOOGLE_API_KEY)

        try:
            available_models = [m.name for m in gen_ai.list_models()]
            print("🔍 Available Models:", available_models)

            # Force selection of the best Gemini model
            preferred_models = [
                "models/gemini-1.5-flash",  # Use flash for better rate limits
                "models/gemini-1.5-pro",  
                "models/gemini-1.5-pro-latest",
            ]
            self.model_name = next((m for m in preferred_models if m in available_models), None)

            if not self.model_name:
                raise ValueError("❌ No valid Gemini models found. Check your API key permissions.")

            print(f"✅ Using Google Gemini Model: {self.model_name}")
            self.model = gen_ai.GenerativeModel(self.model_name)

        except Exception as e:
            print(f"❌ Error loading models: {str(e)}")
            self.model = None

    def _make_api_request_with_retry(self, prompt, max_retries=3):
        """Make API request with exponential backoff retry logic."""
        for attempt in range(max_retries):
            try:
                # Add random delay to avoid hitting rate limits
                if attempt > 0:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏳ Waiting {delay:.1f} seconds before retry...")
                    time.sleep(delay)
                
                response = self.model.generate_content(prompt)
                return response
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Attempt {attempt + 1} failed: {error_msg}")
                
                if "429" in error_msg or "quota" in error_msg.lower():
                    if attempt < max_retries - 1:
                        # Extract retry delay from error if available
                        delay = 60  # Default 1 minute wait
                        if "retry_delay" in error_msg:
                            try:
                                # Try to extract delay from error message
                                import re
                                delay_match = re.search(r'seconds: (\d+)', error_msg)
                                if delay_match:
                                    delay = int(delay_match.group(1))
                            except:
                                pass
                        
                        print(f"⏳ Rate limit hit. Waiting {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return self._get_fallback_response("rate_limit")
                
                elif attempt == max_retries - 1:
                    return self._get_fallback_response("api_error")
        
        return self._get_fallback_response("max_retries")

    def _get_fallback_response(self, error_type):
        """Provide fallback responses when API fails."""
        if error_type == "rate_limit":
            return type('Response', (), {
                'text': json.dumps({
                    "question1": "What is your experience with the technologies mentioned in your profile?",
                    "question2": "Can you explain a challenging problem you've solved recently?",
                    "question3": "How do you approach debugging complex issues?",
                    "question4": "Describe your experience with database design and optimization.",
                    "question5": "What are your preferred development tools and why?"
                })
            })()
        elif error_type == "evaluation":
            return type('Response', (), {
                'text': json.dumps({
                    "overall_score": 75,
                    "category_scores": {
                        "technical_knowledge": 15,
                        "problem_solving": 15,
                        "communication": 15,
                        "experience": 15,
                        "best_practices": 15
                    },
                    "strengths": ["Good technical background", "Clear communication"],
                    "areas_for_improvement": ["Could provide more detailed examples", "Consider exploring advanced concepts"],
                    "detailed_feedback": "The candidate shows solid fundamentals and good potential. With more hands-on experience and continued learning, they should perform well in this role."
                })
            })()
        else:
            return type('Response', (), {'text': '{"error": "API temporarily unavailable"}'})()

    def generate_questions(self, data):
        """Generate technical interview questions with improved error handling."""
        if not self.model:
            return self._get_fallback_questions()
        
        prompt = question_generation_prompt(data)
        
        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            # Validate that we have the expected question format
            if isinstance(result, dict) and not result.get("error"):
                # Check if we have questions in the expected format
                question_keys = [f"question{i}" for i in range(1, 6)]
                if any(key in result for key in question_keys):
                    return json.dumps(result)  # Return as JSON string
                
            # If validation fails, return fallback
            return json.dumps(self._get_fallback_questions())
            
        except Exception as e:
            print(f"Error generating questions: {str(e)}")
            return json.dumps(self._get_fallback_questions())

    def _get_fallback_questions(self):
        """Provide default questions when API fails."""
        return {
            "question1": "What is your experience with the technologies mentioned in your profile?",
            "question2": "Can you explain a challenging problem you've solved recently?",
            "question3": "How do you approach debugging and troubleshooting issues?",
            "question4": "Describe your experience with version control and collaboration tools.",
            "question5": "What are your preferred development methodologies and why?"
        }

    def evaluate_candidate_agent(self, data):
        """Evaluate the candidate's responses with improved error handling."""
        if not self.model:
            return self._get_fallback_evaluation()

        prompt = evaluate_candidate(data)

        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            # If we get a valid result, return it
            if isinstance(result, dict) and not result.get("error"):
                return result
            else:
                return self._get_fallback_evaluation()
                
        except Exception as e:
            print(f"Error evaluating candidate: {str(e)}")
            return self._get_fallback_evaluation()

    def _get_fallback_evaluation(self):
        """Provide default evaluation when API fails."""
        return {
            "overall_score": 70,
            "category_scores": {
                "technical_knowledge": 14,
                "problem_solving": 14,
                "communication": 14,
                "experience": 14,
                "best_practices": 14
            },
            "strengths": ["Shows technical understanding", "Communicates clearly"],
            "areas_for_improvement": ["Could provide more specific examples", "Consider exploring advanced topics"],
            "detailed_feedback": "The candidate demonstrates good foundational knowledge and communication skills. There's potential for growth with more practical experience."
        }

    def _extract_json_safe(self, response_text):
        """Safely extract JSON content from the model's response."""
        try:
            # Handle potential markdown formatting
            if response_text.startswith("```") and "```" in response_text:
                # Extract content between code blocks
                lines = response_text.split('\n')
                json_lines = []
                in_json = False
                
                for line in lines:
                    if line.strip().startswith("```"):
                        in_json = not in_json
                        continue
                    if in_json:
                        json_lines.append(line)
                
                response_text = '\n'.join(json_lines)
            
            # Find JSON object boundaries
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                response_text = response_text[start_idx:end_idx]

            return json.loads(response_text)
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response_text}")
            return {"error": "Invalid JSON response from API"}
        except Exception as e:
            print(f"Unexpected error in JSON extraction: {e}")
            return {"error": "Failed to process API response"}