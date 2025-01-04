from openai import OpenAI
from decouple import config
import logging
import re
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class DialogueManager:
    def __init__(self, menu=None, modifiers=None):
        try:
            self.client = OpenAI(api_key=config('OPENAI_API_KEY'))
            self.menu = menu or {}
            self.modifiers = modifiers or {}
            self.conversation_context = {}
        except Exception as e:
            logger.error(f"Error initializing DialogueManager: {e}")
            raise

    def process_message(self, message: str, phone_number: str, context: Dict) -> Tuple[str, Dict]:
        """Process message and maintain conversation context"""
        try:
            # First check for casual conversation
            casual_response = self._handle_casual_chat(message)
            if casual_response:
                return casual_response, context

            # Then check for order-related content
            order_details = self.extract_order_details(message)
            if order_details.get('item'):
                context['last_item'] = order_details['item']
                context['last_mods'] = order_details.get('modifiers', [])
                
            response = self.get_ai_response(message, self.menu, context)
            return response, context
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "I'm having trouble understanding. Could you rephrase that? 😊", context

    def _handle_casual_chat(self, message: str) -> Optional[str]:
        """Handle casual conversation"""
        casual_patterns = {
            'greeting': r'\b(hi|hello|hey|morning)\b',
            'thanks': r'\b(thanks|thank you|ty)\b',
            'goodbye': r'\b(bye|goodbye|see you|cya)\b',
            'how_are_you': r'how (are|r) (you|u)',
        }

        for intent, pattern in casual_patterns.items():
            if re.search(pattern, message.lower()):
                return self._get_casual_response(intent)
        return None

    def get_ai_response(self, user_message: str, menu: Dict, context: Dict) -> str:
        """Get AI-generated response based on message and context"""
        try:
            modifier_text = self._format_modifier_text()
            current_time = datetime.now().strftime("%H:%M")
            
            system_message = f"""You are a friendly, helpful barista at a coffee shop. Current time: {current_time}

            Menu:
            {self.format_menu_for_ai(menu)}
            
            Modifiers Available:
            {modifier_text}
            
            Customer Context:
            {context}
            
            Guidelines:
            1. Be warm and friendly but concise (2-3 sentences max)
            2. Use 1-2 emojis maximum
            3. Always confirm prices and modifications clearly
            4. If customer orders a drink, subtly suggest complementary items
            5. Reference past orders if available
            6. Keep important information clear while being conversational

            Example good responses:
            "One almond milk latte coming up! That'll be $5.25 with the almond milk (+$0.75). Would you like anything else? Our blueberry muffins are fresh out of the oven! 🥮"
            "Welcome back! Another iced cappuccino with oat milk? That's $5.25 total ☕"
            """

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.7,
                max_tokens=150
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "I'm having trouble understanding. Could you rephrase that? 😊"

    def extract_order_details(self, message: str) -> Dict:
        """Extract order details using AI"""
        try:
            prompt = f"""Extract order details from this message. Include drink type, size, temperature, and any modifications.
            
            Available items: {[item['item'] for item in self.menu.values()]}
            Available modifiers: {self._format_modifier_text()}
            
            Message: "{message}"
            
            Format response as JSON:
            {{
                "item": "item_name",
                "modifiers": ["mod1", "mod2"],
                "temperature": "hot/iced",
                "special_instructions": "any special notes"
            }}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            # Parse response and validate against menu
            try:
                content = response.choices[0].message.content
                # Add validation logic here
                return content
            except Exception as e:
                logger.error(f"Error parsing order details: {e}")
                return {"item": None, "modifiers": []}
                
        except Exception as e:
            logger.error(f"Error extracting order details: {e}")
            return {"item": None, "modifiers": []}

    def format_menu_for_ai(self, menu: Dict) -> str:
        """Format menu for AI prompt"""
        try:
            menu_text = ""
            categories = {"hot": "Hot Drinks:", "cold": "Cold Drinks:", "food": "Food Items:"}
            
            for category in categories:
                menu_text += f"\n{categories[category]}\n"
                for id, item in menu.items():
                    if item['category'] == category:
                        menu_text += f"- {item['item']} (${item['price']:.2f}): {item['description']}\n"
            return menu_text
        except Exception as e:
            logger.error(f"Error formatting menu: {e}")
            return ""

    def _format_modifier_text(self) -> str:
        """Format modifier information"""
        try:
            modifier_text = ""
            for mod_type, mods in self.modifiers.items():
                modifier_text += f"\n{mod_type.title()}:\n"
                for mod, price in mods.items():
                    modifier_text += f"- {mod} (+${price:.2f})\n"
            return modifier_text
        except Exception as e:
            logger.error(f"Error formatting modifiers: {e}")
            return ""

    def _get_casual_response(self, intent: str) -> str:
        """Get appropriate casual response"""
        responses = {
            'greeting': [
                "Hi there! ☺️ What can I get started for you?",
                "Welcome! What are you in the mood for today? ✨"
            ],
            'thanks': [
                "You're welcome! Enjoy! ☺️",
                "My pleasure! Hope to see you again soon! ✨"
            ],
            'goodbye': [
                "Thanks for stopping by! Have a great day! 👋",
                "See you next time! Enjoy your drinks! ✨"
            ],
            'how_are_you': [
                "I'm doing great, thanks for asking! What can I get you? ☺️",
                "All good here! Ready to make your perfect drink! ✨"
            ]
        }
        return responses[intent][0]