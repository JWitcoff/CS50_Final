from flask import Flask, request, render_template
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from decouple import config
from datetime import datetime, timedelta
import logging
import uuid
import os
import openai
from openai import OpenAI
from src.core.dialogue import DialogueManager
from src.core.order import OrderProcessor
from src.core.payment import PaymentHandler
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('coffee_shop.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# Initialize Twilio client
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Menu configuration
MENU = {
    # Hot Drinks
    '1': {'item': 'Espresso', 'price': 3.50, 'category': 'hot', 'description': 'Strong, pure coffee shot'},
    '2': {'item': 'Latte', 'price': 4.50, 'category': 'hot', 'description': 'Espresso with steamed milk'},
    '3': {'item': 'Cappuccino', 'price': 4.50, 'category': 'hot', 'description': 'Equal parts espresso, steamed milk, and foam'},
    
    # Cold Drinks
    '4': {'item': 'Cold Brew', 'price': 4.50, 'category': 'cold', 'description': '12-hour steeped coffee'},
    '5': {'item': 'Iced Latte', 'price': 5.00, 'category': 'cold', 'description': 'Espresso over ice with cold milk'},
    
    # Food Items
    '6': {'item': 'Croissant', 'price': 3.50, 'category': 'food', 'description': 'Butter croissant'},
    '7': {'item': 'Muffin', 'price': 3.00, 'category': 'food', 'description': 'Blueberry muffin'}
}

# Initialize services with menu
dialogue_manager = DialogueManager(menu=MENU)

# In-memory storage
active_orders = {}  # Stores current shopping sessions
completed_orders = {}  # Stores completed orders for tracking

class ShoppingCart:
    def __init__(self):
        self.items = []
        self.total = 0.00
        
    def add_item(self, item, quantity=1):
        """Add an item to cart"""
        for _ in range(quantity):
            self.items.append(item)
            self.total += item['price']
            
    def remove_item(self, item_id):
        """Remove an item from cart"""
        for item in self.items:
            if str(item_id) in MENU and MENU[str(item_id)]['item'] == item['item']:
                self.items.remove(item)
                self.total -= item['price']
                return True
        return False
    
    def clear(self):
        """Clear the cart"""
        self.items = []
        self.total = 0.00
    
    def get_summary(self):
        """Get cart summary"""
        if not self.items:
            return "Your cart is empty. Text 'MENU' to see options."
        
        # Count quantities of each item
        items_count = {}
        for item in self.items:
            items_count[item['item']] = items_count.get(item['item'], 0) + 1
        
        # Format summary message
        summary = "Your Cart:\n\n"
        for item_name, quantity in items_count.items():
            price = next(item['price'] for item in self.items if item['item'] == item_name)
            summary += f"{quantity}x {item_name} (${price:.2f} each)\n"
        
        summary += f"\nTotal: ${self.total:.2f}\n"
        summary += "\nReply with:\n"
        summary += "- ADD <number> to add more items\n"
        summary += "- REMOVE <number> to remove items\n"
        summary += "- DONE to checkout\n"
        summary += "- CLEAR to empty cart"
        
        return summary

class Order:
    def __init__(self, phone_number, cart):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.phone_number = phone_number
        self.items = cart.items.copy()
        self.total = cart.total
        self.status = 'pending'
        self.created_at = datetime.now()
        self.estimated_ready = self.created_at + timedelta(minutes=15)
        
    def update_status(self, status):
        """Update order status"""
        self.status = status
        
    def get_status_message(self):
        """Get formatted status message"""
        status_emoji = {
            'pending': '⏳',
            'preparing': '👨‍🍳',
            'ready': '✅',
            'completed': '🎉',
            'cancelled': '❌'
        }
        
        message = f"Order #{self.id} Status: {status_emoji.get(self.status, '')} {self.status.upper()}\n\n"
        message += "Items:\n"
        
        items_count = {}
        for item in self.items:
            items_count[item['item']] = items_count.get(item['item'], 0) + 1
            
        for item_name, quantity in items_count.items():
            message += f"- {quantity}x {item_name}\n"
            
        message += f"\nTotal: ${self.total:.2f}\n"
        
        if self.status in ['pending', 'preparing']:
            message += f"\nEstimated ready: {self.estimated_ready.strftime('%I:%M %p')}"
            
        return message

# Menu helper functions
def search_menu(query):
    """Search menu items by name or description"""
    query = query.lower()
    results = {}
    
    for key, item in MENU.items():
        if (query in item['item'].lower() or 
            query in item['description'].lower() or 
            query in item['category'].lower()):
            results[key] = item
    
    return results

def get_category_menu(category):
    """Get menu items by category"""
    return {k: v for k, v in MENU.items() if v['category'] == category}

def format_menu_message(menu_items):
    """Format menu items into a readable message"""
    if not menu_items:
        return "No items found. Text 'MENU' to see all options."
    
    message = "Available Items:\n\n"
    for key, item in menu_items.items():
        message += f"{key}. {item['item']} (${item['price']:.2f})\n"
        message += f"   {item['description']}\n"
    return message

def get_menu_message():
    """Generate the menu message"""
    message = "Welcome to Coffee S50! Order by number or name:\n\n"
    for key, item in MENU.items():
        message += f"{key}. {item['item']} (${item['price']:.2f})\n"
        message += f"   {item['description']}\n"
    return message

def get_help_message():
    """Generate help message with available commands"""
    return( 
        "CS50 Coffee Shop Commands:\n\n"
        "🛒 Ordering:\n"
        "- Order by number (e.g., '1' for Espresso)\n"
        "- Order by name (e.g., 'Espresso')\n"
        "- Or use 'ADD 1' format\n\n"
        "📋 Menu:\n"
        "- START: Begin ordering\n"
        "- MENU: See full menu\n"
        "- HOT: View hot drinks\n"
        "- COLD: View cold drinks\n"
        "- FOOD: View food items\n"
        "- FIND [term]: Search menu\n\n"
        "🛍️ Cart:\n"
        "- CART: View your cart\n"
        "- CLEAR: Empty cart\n"
        "- DONE: Proceed to checkout\n\n"
        "📦 Order:\n"
        "- STATUS: Check your order status\n\n"
        "Need help? Visit our website or call us at (555) 123-4567"
    )
# Order processing functions
def complete_order(phone_number, cart):
    """Complete an order and set up tracking"""
    logger.info(f"Creating new order for {phone_number} with {len(cart.items)} items")
    
    # Create new order
    order = Order(phone_number, cart)
    
    # Store order
    if phone_number not in completed_orders:
        completed_orders[phone_number] = []
    completed_orders[phone_number].append(order)
    
    logger.info(f"Created order {order.id} for {phone_number}")
    
    # Send confirmation
    confirmation_message = (
        f"🎉 Order #{order.id} confirmed!\n\n"
        f"{order.get_status_message()}\n\n"
        "Text 'STATUS' anytime to check your order.\n"
        "Text 'START' to place another order."
    )
    
    return confirmation_message

def get_ai_response(user_message, phone_number):
    """Get AI-generated response based on user message and context"""
    # Get user's cart if they have one
    user_cart = active_orders.get(phone_number, {}).get('cart')
    cart_status = user_cart.get_summary() if user_cart else "No items in cart"
    
    # Create a system message that constrains the AI to our menu
    system_message = f"""You are a friendly coffee shop assistant. You can engage in natural conversation 
    about our menu items: {', '.join(f"{item['item']} (${item['price']})" for item in MENU.values())}.

    Current cart: {cart_status}

    Remember:
    1. Only suggest items from our menu
    2. Guide users to order using numbers (1-7) or exact item names
    3. Keep responses friendly but concise
    4. If users ask about unavailable items, suggest similar ones from our menu
    5. Recognize order-related commands: ADD, REMOVE, DONE, CLEAR, STATUS"""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}")
        return None

def process_message(phone_number, message):
    """Process incoming messages based on current order state"""
    message = message.lower().strip()
    
    # Initialize order if this is a new conversation
    if phone_number not in active_orders and message not in ['status', 'help']:
        active_orders[phone_number] = {
            'state': 'MENU',
            'cart': ShoppingCart(),
            'last_action': None
        }

    # Handle direct commands first
    if message == 'status':
        if phone_number in completed_orders and completed_orders[phone_number]:
            latest_order = completed_orders[phone_number][-1]
            return latest_order.get_status_message()
        return "No active orders found. Text 'START' to place an order."

    if message == 'help':
        return get_help_message()

    if message == 'clear':
        if phone_number in active_orders:
            active_orders[phone_number]['cart'].clear()
            return "Cart cleared. Text 'MENU' to see options."
        return "No active cart. Text 'START' to begin ordering."

    if message == 'cart':
        if phone_number in active_orders:
            return active_orders[phone_number]['cart'].get_summary()
        return "No active cart. Text 'START' to begin ordering."

    # Get AI response for general queries
    ai_response = get_ai_response(message, phone_number)
    if ai_response:
        # Process any order-related commands that might be in the message
        order = active_orders.get(phone_number, {})
        cart = order.get('cart') if order else None

        # Check for item numbers or names in the message
        for menu_id, item in MENU.items():
            if menu_id in message or item['item'].lower() in message.lower():
                if cart:
                    cart.add_item(MENU[menu_id])
                    return f"{ai_response}\n\n{cart.get_summary()}"

        # Handle payment confirmation
        if order and order.get('state') == 'PAYMENT' and '4242' in message:
            confirmation = complete_order(phone_number, cart)
            del active_orders[phone_number]
            return confirmation

        return ai_response

    # Fallback to original menu if AI fails
    return get_menu_message()

# Flask routes
@app.route('/')
def home():
    """Render the home page"""
    return render_template('index.html', menu=MENU, twilio_number=TWILIO_PHONE_NUMBER)

@app.route('/test', methods=['GET'])
def test():
    return "Test route working!"

@app.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages"""
    phone_number = request.values.get('From', '')
    message_body = request.values.get('Body', '').strip()
    
    logger.info(f"Incoming message from {phone_number}: {message_body}")
    
    resp = MessagingResponse()
    
    try:
        response_message = process_message(phone_number, message_body.lower())
        logger.info(f"Sending response to {phone_number}: {response_message}")
        resp.message(response_message)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        resp.message("Sorry, something went wrong. Please text 'START' to try again.")
    
    return str(resp)

@app.route('/test-openai', methods=['GET'])
def test_openai():
    """Test OpenAI connection and check credits"""
    try:
        # Try to make a minimal API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1
        )
        return "OpenAI API is working!"
    except Exception as e:
        logger.error(f"OpenAI API error: {str(e)}", exc_info=True)
        return f"OpenAI API error: {str(e)}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
