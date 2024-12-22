from openai import OpenAI
from decouple import config
import logging
import re

logger = logging.getLogger(__name__)

class DialogueManager:
    def __init__(self, menu=None, modifiers=None):
        self.client = OpenAI(api_key=config('OPENAI_API_KEY'))
        self.menu = menu or {}
        self.modifiers = modifiers or {}

    def format_menu_for_ai(self, menu):
        """Format menu in a clear way for the AI"""
        menu_text = ""
        categories = {"hot": "Hot Drinks:", "cold": "Cold Drinks:", "food": "Food Items:"}
        
        for category in categories:
            menu_text += f"\n{categories[category]}\n"
            for id, item in menu.items():
                if item['category'] == category:
                    menu_text += f"- {item['item']} (${item['price']:.2f}): {item['description']} (Order with number {id})\n"
        
        return menu_text

    def get_ai_response(self, user_message, menu, phone_number):
        """Get AI-generated response based on user message and context"""
        system_message = f"""You are a friendly coffee shop assistant. Here's our menu:
        {self.format_menu_for_ai(menu)}

        Guidelines:
        1. Keep responses under 2 sentences unless showing menu
        2. Always show prices with 2 decimal places (e.g., $4.50)
        3. Use 1-2 emojis maximum
        4. For orders, guide users to use item numbers (1-7)
        5. If users ask about unavailable items, suggest similar ones from our menu
        6. Recognize commands: MENU, ADD, REMOVE, DONE, CLEAR, STATUS
        7. Be friendly but concise
        
        Common commands:
        - MENU: Show full menu
        - ADD <number>: Add item to cart
        - REMOVE <number>: Remove item from cart
        - DONE: Proceed to checkout
        - CLEAR: Empty cart
        - STATUS: Check order status"""

        try:
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

    def _build_system_message(self, context, menu):
        # Add modifier information to system message
        modifier_text = "\nModifiers Available:\n"
        for mod_type, mods in self.modifiers.items():
            modifier_text += f"\n{mod_type.title()}:\n"
            for mod, price in mods.items():
                modifier_text += f"- {mod} (+${price:.2f})\n"

        return f"""You're a coffee shop assistant. Current order status:
            Stage: {context.stage.value}
            Current Drink: {context.current_drink or 'None'}
            Modifications: {', '.join(context.modifications) or 'None'}
            
            Menu: {self.format_menu_for_ai(menu)}
            {modifier_text}
            
            Rules:
            1. Keep responses under 2 sentences unless showing menu
            2. Always mention modifier costs when suggesting them
            3. Use 1-2 emojis max
            4. Ask for confirmation before adding paid modifiers"""