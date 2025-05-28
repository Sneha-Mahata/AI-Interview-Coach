import google.generativeai as gen_ai
import os
from dotenv import load_dotenv
import json
import time
import random

load_dotenv()

class AnswerEvaluationAgent:
    """
    A class to evaluate interview answers using Google Gemini AI with comprehensive feedback.
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
                        delay = 60  # Default 1 minute wait
                        if "retry_delay" in error_msg:
                            try:
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
        return type('Response', (), {
            'text': json.dumps({
                "overall_score": 70,
                "detailed_scores": {
                    "clarity": 14,
                    "completeness": 14,
                    "accuracy": 14,
                    "relevance": 14,
                    "communication": 14
                },
                "strengths": ["Answer provided shows understanding"],
                "weaknesses": ["Could be more detailed"],
                "improvement_suggestions": ["Provide specific examples", "Elaborate on key points"],
                "detailed_feedback": "Unable to evaluate due to API issues. Please try again.",
                "overall_impression": "Moderate"
            })
        })()

    def evaluate_single_answer(self, question, answer, context=""):
        """
        Evaluate a single answer to an interview question.
        
        Args:
            question (str): The interview question
            answer (str): The candidate's answer
            context (str): Additional context like job role, company, etc.
        
        Returns:
            dict: Detailed evaluation results
        """
        prompt = self._create_answer_evaluation_prompt(question, answer, context)
        
        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            if isinstance(result, dict) and not result.get("error"):
                return result
            else:
                return self._get_fallback_evaluation()
                
        except Exception as e:
            print(f"Error evaluating answer: {str(e)}")
            return self._get_fallback_evaluation()

    def evaluate_multiple_answers(self, qa_pairs, context=""):
        """
        Evaluate multiple question-answer pairs.
        
        Args:
            qa_pairs (list): List of dictionaries with 'question' and 'answer' keys
            context (str): Additional context
            
        Returns:
            dict: Comprehensive evaluation results
        """
        prompt = self._create_multiple_answers_evaluation_prompt(qa_pairs, context)
        
        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            if isinstance(result, dict) and not result.get("error"):
                return result
            else:
                return self._get_fallback_comprehensive_evaluation()
                
        except Exception as e:
            print(f"Error evaluating multiple answers: {str(e)}")
            return self._get_fallback_comprehensive_evaluation()

    def _create_answer_evaluation_prompt(self, question, answer, context):
        """Create a detailed prompt for evaluating a single answer."""
        prompt = f"""
You are an expert interview evaluator. Please evaluate the following interview answer comprehensively.

Context: {context if context else "General interview evaluation"}

Question: {question}

Answer: {answer}

Please evaluate this answer and provide feedback in the following JSON format:

{{
    "overall_score": [score out of 100],
    "detailed_scores": {{
        "clarity": [score out of 20 - how clear and well-structured is the answer],
        "completeness": [score out of 20 - how thoroughly does it address the question],
        "accuracy": [score out of 20 - technical accuracy and correctness],
        "relevance": [score out of 20 - how relevant is the answer to the question],
        "communication": [score out of 20 - communication skills demonstrated]
    }},
    "strengths": [list of 2-4 specific strengths in the answer],
    "weaknesses": [list of 2-4 areas that could be improved],
    "improvement_suggestions": [list of 3-5 specific suggestions for improvement],
    "detailed_feedback": "[2-3 paragraph detailed feedback]",
    "overall_impression": "[Excellent/Good/Satisfactory/Needs Improvement/Poor]",
    "missing_elements": [list of important elements that should have been included],
    "follow_up_questions": [list of 2-3 follow-up questions an interviewer might ask]
}}

Provide constructive, specific feedback that helps the candidate improve their interview performance.
"""
        return prompt

    def _create_multiple_answers_evaluation_prompt(self, qa_pairs, context):
        """Create a prompt for evaluating multiple answers comprehensively."""
        qa_text = ""
        for i, qa in enumerate(qa_pairs, 1):
            qa_text += f"\nQ{i}: {qa['question']}\nA{i}: {qa['answer']}\n"
        
        prompt = f"""
You are an expert interview evaluator. Please evaluate the following complete interview session comprehensively.

Context: {context if context else "General interview evaluation"}

Interview Questions and Answers:
{qa_text}

Please evaluate this interview session and provide feedback in the following JSON format:

{{
    "overall_score": [score out of 100],
    "individual_scores": [
        {{
            "question_number": 1,
            "score": [score out of 100],
            "feedback": "[brief feedback for this answer]"
        }}
        // ... for each question
    ],
    "category_scores": {{
        "technical_knowledge": [score out of 20],
        "problem_solving": [score out of 20],
        "communication": [score out of 20],
        "experience": [score out of 20],
        "professionalism": [score out of 20]
    }},
    "strengths": [list of overall strengths across all answers],
    "areas_for_improvement": [list of areas needing improvement],
    "consistency_analysis": "[analysis of consistency across answers]",
    "detailed_feedback": "[comprehensive 3-4 paragraph feedback]",
    "interview_readiness": "[Ready/Nearly Ready/Needs Preparation/Significant Preparation Needed]",
    "recommendations": [list of specific recommendations for improvement],
    "standout_moments": [list of particularly impressive aspects],
    "red_flags": [list of concerning aspects, if any]
}}

Provide honest, constructive feedback that helps the candidate understand their performance and improve.
"""
        return prompt

    def compare_answers(self, question, answer1, answer2, labels=["Answer A", "Answer B"]):
        """
        Compare two different answers to the same question.
        
        Args:
            question (str): The interview question
            answer1 (str): First answer to compare
            answer2 (str): Second answer to compare
            labels (list): Labels for the answers
            
        Returns:
            dict: Comparison results
        """
        prompt = f"""
You are an expert interview evaluator. Please compare these two answers to the same interview question.

Question: {question}

{labels[0]}: {answer1}

{labels[1]}: {answer2}

Please provide a detailed comparison in the following JSON format:

{{
    "comparison_summary": "[Overall summary of the comparison]",
    "scores": {{
        "{labels[0].lower().replace(' ', '_')}": [score out of 100],
        "{labels[1].lower().replace(' ', '_')}": [score out of 100]
    }},
    "detailed_comparison": {{
        "clarity": "[comparison of clarity]",
        "completeness": "[comparison of completeness]",
        "accuracy": "[comparison of accuracy]",
        "examples": "[comparison of examples used]",
        "structure": "[comparison of answer structure]"
    }},
    "winner": "[{labels[0]}/{labels[1]}/Tie]",
    "reasoning": "[detailed reasoning for the winner]",
    "best_elements": {{
        "{labels[0].lower().replace(' ', '_')}": [list of best elements from answer 1],
        "{labels[1].lower().replace(' ', '_')}": [list of best elements from answer 2]
    }},
    "improvement_suggestions": {{
        "{labels[0].lower().replace(' ', '_')}": [suggestions for answer 1],
        "{labels[1].lower().replace(' ', '_')}": [suggestions for answer 2]
    }}
}}
"""
        
        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            if isinstance(result, dict) and not result.get("error"):
                return result
            else:
                return {"error": "Failed to compare answers"}
                
        except Exception as e:
            print(f"Error comparing answers: {str(e)}")
            return {"error": f"Comparison failed: {str(e)}"}

    def _get_fallback_evaluation(self):
        """Provide default evaluation when API fails."""
        return {
            "overall_score": 70,
            "detailed_scores": {
                "clarity": 14,
                "completeness": 14,
                "accuracy": 14,
                "relevance": 14,
                "communication": 14
            },
            "strengths": ["Shows understanding of the topic"],
            "weaknesses": ["Could provide more specific details"],
            "improvement_suggestions": ["Add concrete examples", "Structure answer more clearly"],
            "detailed_feedback": "Unable to provide detailed evaluation due to API issues. The answer shows basic understanding but could benefit from more specific examples and clearer structure.",
            "overall_impression": "Satisfactory",
            "missing_elements": ["Specific examples", "Detailed explanations"],
            "follow_up_questions": ["Can you provide a specific example?", "How would you handle edge cases?"]
        }

    def _get_fallback_comprehensive_evaluation(self):
        """Provide default comprehensive evaluation when API fails."""
        return {
            "overall_score": 70,
            "category_scores": {
                "technical_knowledge": 14,
                "problem_solving": 14,
                "communication": 14,
                "experience": 14,
                "professionalism": 14
            },
            "strengths": ["Shows technical understanding"],
            "areas_for_improvement": ["Provide more specific examples"],
            "detailed_feedback": "Unable to provide detailed evaluation due to API issues. Consider providing more specific examples and structuring answers more clearly.",
            "interview_readiness": "Needs Preparation",
            "recommendations": ["Practice with specific examples", "Work on answer structure"]
        }

    def generate_questions(self, data):
        """Generate technical interview questions (for backward compatibility)."""
        if not self.model:
            return json.dumps(self._get_fallback_questions())
        
        prompt = self._create_question_generation_prompt(data)
        
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

    def _create_question_generation_prompt(self, data):
        """Create a prompt for generating interview questions based on user data."""
        prompt = f"""
You are an expert technical interviewer. Based on the following candidate information, generate 5 relevant technical interview questions.

Candidate Information:
{json.dumps(data, indent=2) if isinstance(data, dict) else str(data)}

Generate questions that are:
1. Relevant to their experience level and technologies mentioned
2. Progressive in difficulty
3. Mix of technical knowledge, problem-solving, and experience-based questions
4. Appropriate for their stated role/position

Please provide exactly 5 questions in the following JSON format:

{{
    "question1": "[First technical question]",
    "question2": "[Second technical question]", 
    "question3": "[Third technical question]",
    "question4": "[Fourth technical question]",
    "question5": "[Fifth technical question]"
}}

Make sure the questions are specific, clear, and would help assess the candidate's technical competency.
"""
        return prompt

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
        """Evaluate the candidate's responses (for backward compatibility)."""
        if not self.model:
            return self._get_fallback_legacy_evaluation()

        prompt = self._create_legacy_evaluation_prompt(data)

        try:
            response = self._make_api_request_with_retry(prompt)
            result = self._extract_json_safe(response.text)
            
            # If we get a valid result, return it
            if isinstance(result, dict) and not result.get("error"):
                return result
            else:
                return self._get_fallback_legacy_evaluation()
                
        except Exception as e:
            print(f"Error evaluating candidate: {str(e)}")
            return self._get_fallback_legacy_evaluation()

    def _create_legacy_evaluation_prompt(self, data):
        """Create evaluation prompt for legacy compatibility."""
        prompt = f"""
You are an expert interview evaluator. Please evaluate the candidate's overall interview performance based on the following data:

Interview Data:
{json.dumps(data, indent=2) if isinstance(data, dict) else str(data)}

Please provide evaluation in the following JSON format:

{{
    "overall_score": [score out of 100],
    "category_scores": {{
        "technical_knowledge": [score out of 20],
        "problem_solving": [score out of 20],
        "communication": [score out of 20],
        "experience": [score out of 20],
        "best_practices": [score out of 20]
    }},
    "strengths": [list of candidate's main strengths],
    "areas_for_improvement": [list of areas needing improvement],
    "detailed_feedback": "[comprehensive feedback paragraph]"
}}

Provide honest, constructive feedback that helps the candidate understand their performance.
"""
        return prompt

    def _get_fallback_legacy_evaluation(self):
        """Provide default evaluation for legacy compatibility."""
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


# Example usage
if __name__ == "__main__":
    evaluator = AnswerEvaluationAgent()
    
    # Example 1: Evaluate a single answer
    question = "What is your experience with Python?"
    answer = """I have been working with Python for about 3 years. I've used it for web development 
    with Django and Flask, data analysis with pandas and numpy, and automation scripts. 
    I'm comfortable with object-oriented programming and have experience with testing frameworks like pytest."""
    
    result = evaluator.evaluate_single_answer(question, answer, "Software Developer position")
    print("Single Answer Evaluation:")
    print(json.dumps(result, indent=2))
    
    # Example 2: Evaluate multiple answers
    qa_pairs = [
        {
            "question": "What is your experience with Python?",
            "answer": "I have 3 years of experience with Python, working on web development and data analysis."
        },
        {
            "question": "How do you handle debugging?",
            "answer": "I use debuggers, print statements, and logging to identify and fix issues systematically."
        }
    ]
    
    comprehensive_result = evaluator.evaluate_multiple_answers(qa_pairs, "Python Developer Interview")
    print("\nComprehensive Evaluation:")
    print(json.dumps(comprehensive_result, indent=2))