from openai import OpenAI
from decouple import config
import logging
import re

from src.core.state import OrderContext
from src.core.enums import OrderStage
from src.utils.nlp import extract_drink_order, extract_modifications

logger = logging.getLogger(__name__)

class DialogueManager:
    def __init__(self, menu=None):
        self.client = OpenAI(api_key=config('OPENAI_API_KEY'))
        self.conversation_context = {}  # Store per-user context
        self.menu = menu or {}  # Initialize menu

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
        # Get or create user's context
        context = self.conversation_context.get(
            phone_number, 
            OrderContext()
        )
        
        # Process message based on current stage
        if context.stage == OrderStage.INITIAL:
            drink = extract_drink_order(user_message, menu)
            if drink:
                context.current_drink = drink
                context.update_stage(OrderStage.MODIFICATIONS)
                return self._get_modification_prompt(drink)
                
        elif context.stage == OrderStage.MODIFICATIONS:
            mods = extract_modifications(user_message)
            if mods:
                context.modifications.extend(mods)
                return self._get_confirmation_prompt(context)
                
        # Default to AI response if no specific handling
        return self._get_ai_response(context, user_message, menu)

    def _get_modification_prompt(self, drink):
        return (f"Great choice! Would you like any modifications to your {drink}? "
                "We offer different milk options, extra shots, or you can have it iced. "
                "Or say 'none' to continue.")

    def _get_confirmation_prompt(self, context):
        mods_text = ", ".join(context.modifications) if context.modifications else "no modifications"
        return (f"I have a {context.current_drink} with {mods_text}. "
                "Would you like to add anything else or say 'done' to checkout?")

    def _get_ai_response(self, context, user_message, menu):
        # Update system message with context
        system_message = self._build_system_message(context, menu)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.5,
                max_tokens=150
            )
            
            # Process the response and update context
            ai_response = response.choices[0].message.content
            self._update_context(context, user_message, ai_response)
            
            return ai_response

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return "Sorry, could you try that again?"

    def _build_system_message(self, context, menu):
        return f"""You're a coffee shop assistant. Current order status:
        Stage: {context.stage.value}
        Current Drink: {context.current_drink or 'None'}
        Modifications: {', '.join(context.modifications) or 'None'}
        
        Menu: {self.format_menu_for_ai(menu)}
        
        Rules:
        1. Keep responses under 2 sentences unless showing full menu
        2. Always mention prices
        3. Ask about customization only for drinks
        4. Use 1-2 emojis max"""

    def _update_context(self, context, user_message, ai_response):
        # Extract drink selection
        if context.stage == OrderStage.INITIAL:
            drink = self._extract_drink_order(user_message)
            if drink:
                context.current_drink = drink
                context.update_stage(OrderStage.MODIFICATIONS)
                
        # Extract modifications
        elif context.stage == OrderStage.MODIFICATIONS:
            mods = self._extract_modifications(user_message)
            if mods:
                context.modifications.extend(mods)
            if 'done' in user_message.lower():
                context.update_stage(OrderStage.CONFIRMATION)

    def _extract_drink_order(self, user_message):
        """Extract drink orders from message"""
        # Simple pattern matching for menu items
        for item_id, details in self.menu.items():
            if details['item'].lower() in user_message.lower():
                return details['item']
        return None

    def _extract_modifications(self, user_message):
        """Extract modifications from message"""
        mods = []
        mod_patterns = {
            'milk': r'(oat|soy|almond) milk',
            'temp': r'(hot|iced)',
            'shots': r'(extra|double) shot'
        }
        
        for mod_type, pattern in mod_patterns.items():
            match = re.search(pattern, user_message.lower())
            if match:
                mods.append(match.group(0))
        return mods

# Add this at the bottom of the file
if __name__ == "__main__":
    dm = DialogueManager()
    print("DialogueManager initialized successfully") 