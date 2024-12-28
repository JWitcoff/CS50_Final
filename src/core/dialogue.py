from openai import OpenAI
from decouple import config
import logging
import re

logger = logging.getLogger(__name__)

class DialogueManager:
    def __init__(self, menu=None, modifiers=None):
        try:
            self.client = OpenAI(api_key=config('OPENAI_API_KEY'))
            self.menu = menu or {}
            self.modifiers = modifiers or {}
        except Exception as e:
            logger.error(f"Error initializing DialogueManager: {e}")
            raise

    def format_menu_for_ai(self, menu):
        """Format menu in a clear way for the AI"""
        try:
            menu_text = ""
            categories = {"hot": "Hot Drinks:", "cold": "Cold Drinks:", "food": "Food Items:"}
            
            for category in categories:
                menu_text += f"\n{categories[category]}\n"
                for id, item in menu.items():
                    if item['category'] == category:
                        menu_text += f"- {item['item']} (${item['price']:.2f}): {item['description']} (Order with number {id})\n"
            return menu_text
        except Exception as e:
            logger.error(f"Error formatting menu: {e}")
            return ""

    def get_ai_response(self, user_message, menu, context=None):
        """Get AI-generated response based on user message and context"""
        try:
            modifier_text = self._format_modifier_text()
            
            system_message = f"""You are a friendly coffee shop assistant. Here's our menu:
            {self.format_menu_for_ai(menu)}
            {modifier_text}
            
            Guidelines:
            1. Keep responses under 2 sentences unless showing menu
            2. Always show prices with 2 decimal places (e.g., $4.50)
            3. Use 1-2 emojis maximum
            4. For orders, guide users to use item numbers (1-7)
            5. If users ask about modifiers, confirm their costs
            6. Recognize commands: MENU, ADD, REMOVE, DONE, CLEAR, STATUS
            7. Be friendly but concise
            8. Extract specific item and modifier requests from natural language
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
            return "I'm having trouble understanding. Please try again or text MENU to see our options."

    def _format_modifier_text(self):
        """Format modifier information"""
        try:
            modifier_text = "\nModifiers Available:\n"
            for mod_type, mods in self.modifiers.items():
                modifier_text += f"\n{mod_type.title()}:\n"
                for mod, price in mods.items():
                    modifier_text += f"- {mod} (+${price:.2f})\n"
            return modifier_text
        except Exception as e:
            logger.error(f"Error formatting modifiers: {e}")
            return ""

    def extract_order_details(self, message):
        """Extract order details using AI"""
        try:
            prompt = f"""Extract order details from: "{message}"
            Format: {{"item": "item_name", "modifiers": ["modifier1", "modifier2"]}}
            If no clear order, return {{"item": null, "modifiers": []}}"""
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.3,
                max_tokens=100
            )
            try:
                return response.choices[0].message.content
            except (AttributeError, IndexError) as e:
                logger.error(f"Error parsing AI response: {e}")
                return {"item": None, "modifiers": []}
        except Exception as e:
            logger.error(f"Error in extract_order_details: {e}")
            return {"item": None, "modifiers": []}