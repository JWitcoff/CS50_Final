"""Conversation handler for friendly chat interactions"""
from datetime import datetime
import logging
from typing import Dict, List, Optional
import random
from openai import OpenAI

logger = logging.getLogger(__name__)

class ConversationHandler:
    def __init__(self, openai_client: OpenAI):
        self.client = openai_client
        self.customer_context = {}
        self.greeting_used = set()
    
    def get_friendly_response(self, base_message: str, customer_context: Dict, **kwargs) -> str:
        """Make responses more conversational while maintaining necessary info"""
        try:
            time_of_day = self._get_time_greeting()
            
            prompt = f"""You are a friendly, helpful barista. 
            Make this response conversational while keeping all important information.
            Use max 1-2 emojis. Be concise but warm.

            Time of day: {time_of_day}
            Customer context: {customer_context}
            Message to convey: {base_message}
            Additional context: {kwargs}

            Keep prices and important information clear while being friendly.
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": base_message}
                ],
                temperature=0.7,
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating friendly response: {e}")
            return base_message
            
    def handle_chat(self, message: str, context: Optional[Dict] = None) -> Optional[str]:
        """Handle casual conversation and questions"""
        casual_patterns = {
            'greeting': ['hi', 'hello', 'hey', 'good morning', 'morning', 'afternoon', 'evening'],
            'how_are_you': ['how are you', 'how you doing', "how's it going"],
            'thanks': ['thank you', 'thanks', 'appreciate it'],
            'busy': ['busy', 'quiet', 'long wait'],
            'weather': ['weather', 'hot', 'cold', 'rain', 'sunny'],
        }
        
        message = message.lower()
        
        # Check if message is just casual conversation
        for category, patterns in casual_patterns.items():
            if any(pattern in message for pattern in patterns):
                return self._get_casual_response(category, context or {})
                
        return None

    def _get_time_greeting(self) -> str:
        """Get appropriate time-based greeting"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        else:
            return "evening"
            
    def _get_casual_response(self, category: str, context: Dict) -> str:
        """Get contextually appropriate casual response"""
        responses = {
            'greeting': [
                "Hey there! ☺️ What can I get started for you?",
                "Welcome to Coffee S50! ✨ What are you in the mood for?"
            ],
            'how_are_you': [
                "Doing great, thanks for asking! How can I help you today? ☺️",
                "All good here! Ready to make your perfect drink! ✨"
            ],
            'thanks': [
                "You're welcome! Enjoy! ☺️",
                "My pleasure! Hope to see you again soon! ✨"
            ],
            'busy': [
                "Just the usual rush, but we'll have your order ready in no time! ⚡",
                "Not too bad! We'll get your order ready quick! ✨"
            ],
            'weather': [
                "Perfect day for a coffee! What can I get you? ☀️",
                "Great coffee weather! What are you in the mood for? ✨"
            ]
        }
        
        return random.choice(responses[category])