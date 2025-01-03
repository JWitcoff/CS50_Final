# Standard library imports
from datetime import datetime, timedelta
import logging
import os
import uuid
import sys

# Third-party imports
from decouple import config
from dotenv import load_dotenv
from flask import Flask, request, render_template, jsonify
from openai import OpenAI
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import httpx

# Local/application imports
from src.core.dialogue import DialogueManager
from src.core.order import OrderProcessor, OrderQueue
from src.core.payment import PaymentHandler
from src.core.enums import OrderStage
from src.core.session import SessionManager
from src.core.config import MENU, MODIFIERS
from src.core.cart import ShoppingCart, CartItem
from src.core.menu_handler import MenuHandler

# Configuration Constants
PORT = int(os.getenv('PORT', 10000))
HOST = '0.0.0.0'

# Configure logging
os.makedirs('logs', exist_ok=True)
log_filename = f"logs/coffee_shop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)
logger.info("=== Coffee Shop Application Starting ===")

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# Initialize services
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
dialogue_manager = DialogueManager(menu=MENU, modifiers=MODIFIERS)
payment_handler = PaymentHandler()
order_processor = OrderProcessor()
session_manager = SessionManager()
menu_handler = MenuHandler(menu=MENU, modifiers=MODIFIERS)

# In-memory storage
active_orders = {}
completed_orders = {}

def get_menu_message():
    """Generate the menu message"""
    message = "Welcome to Coffee S50! Order by number or name:\n\n"
    for key, item in MENU.items():
        message += f"{key}. {item['item']} (${item['price']:.2f})\n"
        message += f"   {item['description']}\n"
    return message

def process_message(phone_number, message):
    """Process incoming messages based on current order state"""
    message = message.lower().strip()
    logger.info(f"Processing message: {message} from {phone_number}")
    
    # Handle START command
    if message == 'start':
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue()
        }
        session_manager.update_session_state(phone_number, OrderStage.MENU)
        return get_menu_message()
    
    # Check if user has an active order
    if phone_number not in active_orders:
        return "Please text 'START' to begin ordering."
    
    current_state = session_manager.get_session_state(phone_number)
    order = active_orders[phone_number]
    
    # Handle AWAITING_MOD_CONFIRM state
    if current_state == 'AWAITING_MOD_CONFIRM':
        pending_item = order['pending_item']
        message = message.lower().strip()
        
        # Handle direct modifier responses
        if any(mod in message for mod in ['almond', 'almond milk']):
            order['pending_modifier'] = 'almond milk'
            return ("Almond milk costs $0.75 extra. Reply:\n"
                   "YES to confirm\n"
                   "NO for regular milk")
        elif any(mod in message for mod in ['oat', 'oat milk']):
            order['pending_modifier'] = 'oat milk'
            return ("Oat milk costs $0.75 extra. Reply:\n"
                   "YES to confirm\n"
                   "NO for regular milk")
        elif any(mod in message for mod in ['soy', 'soy milk']):
            order['pending_modifier'] = 'soy milk'
            return ("Soy milk costs $0.75 extra. Reply:\n"
                   "YES to confirm\n"
                   "NO for regular milk")
        elif message in ['yes', 'y', 'yeah', 'sure', 'ok', 'yep']:
            if 'pending_modifier' in order:
                order['cart'].add_item(pending_item, modifiers=[order['pending_modifier']])
            order['state'] = OrderStage.MENU
            session_manager.update_session_state(phone_number, OrderStage.MENU)
            return order['cart'].get_summary()
        elif message in ['no', 'n', 'nope', 'regular', 'regular milk', 'normal']:
            order['cart'].add_item(pending_item)  # Add without modifications
            order['state'] = OrderStage.MENU
            session_manager.update_session_state(phone_number, OrderStage.MENU)
            return order['cart'].get_summary()
        
        return ("Please choose a milk type or reply NO for regular milk:\n"
                "- Almond milk (+$0.75)\n"
                "- Oat milk (+$0.75)\n"
                "- Soy milk (+$0.75)")
    
    # Handle menu state
    if current_state == OrderStage.MENU:
        # Check for special commands
        if message in ['done', 'checkout', 'pay']:
            return handle_checkout(phone_number)
            
        # Extract menu items and potential modifiers
        found_items = menu_handler.extract_menu_items_and_modifiers(message)
        if found_items:
            for item in found_items:
                if item.get('modifiers'):
                    # If modifiers were specified in the order
                    mod = item['modifiers'][0]
                    order['pending_item'] = item
                    order['pending_modifier'] = mod
                    order['state'] = 'AWAITING_MOD_CONFIRM'
                    return f"{mod} costs $0.75 extra. Reply YES to confirm or NO for regular milk."
                elif item['category'] in ['hot', 'cold']:
                    # If it's a drink that could have modifiers
                    order['pending_item'] = item
                    order['state'] = 'AWAITING_MOD_CONFIRM'
                    return ("Would you like any milk modifications?\n"
                           "- Almond milk (+$0.75)\n"
                           "- Oat milk (+$0.75)\n"
                           "- Soy milk (+$0.75)\n"
                           "Reply 'no' for regular milk")
                else:
                    # Non-drink items go straight to cart
                    order['cart'].add_item(item)
            
            return order['cart'].get_summary()
            
        return "I didn't recognize those items. Please order by item name or number, or text 'MENU' to see options."
    
    # Handle other states (payment, etc.)
    return handle_other_states(phone_number, message, current_state)

def handle_checkout(phone_number):
    """Handle checkout process"""
    cart = active_orders[phone_number]['cart']
    if not cart.items:
        return "Your cart is empty! Please add items before checking out."
    
    session_manager.update_session_state(phone_number, OrderStage.PAYMENT)
    active_orders[phone_number]['state'] = OrderStage.PAYMENT
    
    return (
        f"Total: ${cart.get_total():.2f}\n"
        "How would you like to pay?\n"
        "Reply with:\n"
        "- CASH for cash payment\n"
        "- CARD to pay by credit card"
    )

def handle_other_states(phone_number, message, current_state):
    """Handle payment and other states"""
    if current_state == OrderStage.PAYMENT:
        return handle_payment(phone_number, message)
    elif current_state == OrderStage.AWAITING_CARD:
        return handle_card_payment(phone_number, message)
    
    return "I'm not sure what to do. Please text 'START' to begin a new order."

def handle_payment(phone_number, message):
    """Handle payment processing"""
    return payment_handler.handle_payment(phone_number, message, active_orders, completed_orders)

def handle_card_payment(phone_number, message):
    """Handle credit card payment processing"""
    return payment_handler.handle_card_payment(phone_number, message, active_orders, completed_orders)

@app.route('/sms', methods=['POST'])
def handle_sms():
    """Handle incoming SMS messages"""
    phone_number = request.values.get('From', '')
    message_body = request.values.get('Body', '').strip()
    
    logger.info(f"\n=== New Message ===")
    logger.info(f"From: {phone_number}")
    logger.info(f"Message: {message_body}")
    
    resp = MessagingResponse()
    
    try:
        response_message = process_message(phone_number, message_body)
        logger.info(f"Generated Response: {response_message}")
        resp.message(response_message)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        resp.message("Sorry, something went wrong. Please text 'START' to try again.")
    
    logger.info(f"Final Response: {str(resp)}")
    logger.info("=== End Message ===")
    return str(resp)

@app.route('/')
def home():
    return render_template('index.html', 
                         twilio_number=TWILIO_PHONE_NUMBER,
                         menu=MENU)

@app.route('/health')
def health_check():
    return 'OK', 200

if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=True)