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

def extract_menu_items_and_modifiers(message):
    """Extract menu items and their modifiers from a message"""
    found_items = []
    message = message.lower()
    
    # First look for iced/cold drinks
    is_iced = 'iced' in message or 'cold' in message
    
    # Define modifier variations
    milk_modifiers = {
        'almond milk': ['almond milk', 'almond'],
        'oat milk': ['oat milk', 'oat'],
        'soy milk': ['soy milk', 'soy']
    }
    
    for menu_id, item in MENU.items():
        item_name = item['item'].lower()
        
        # Handle iced drinks specially
        if is_iced and 'latte' in item_name:
            for menu_item in MENU.values():
                if menu_item['item'].lower() == 'iced latte':
                    item = menu_item
                    item_name = 'iced latte'
                    break
        
        if item_name in message:
            # Create a copy of the item
            item_copy = item.copy()
            item_copy['modifiers'] = []
            
            # Check for modifiers
            for mod_name, variations in milk_modifiers.items():
                if any(var in message for var in variations):
                    item_copy['modifiers'].append(mod_name)
            
            found_items.append(item_copy)
            
    return found_items

def confirm_modifications(message):
    """Check if message confirms modifications"""
    confirmations = ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'y', 'alright', 'confirm']
    denials = ['no', 'nope', 'n', 'regular', 'normal', 'none']
    
    message = message.lower().strip()
    return (message in confirmations, message in denials)

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
        # Define modifier mappings
        milk_modifiers = {
            'almond': 'almond milk',
            'almond milk': 'almond milk',
            'oat': 'oat milk',
            'oat milk': 'oat milk',
            'soy': 'soy milk',
            'soy milk': 'soy milk'
        }
        
        # Check for direct modifier selection
        selected_modifier = None
        for key, value in milk_modifiers.items():
            if key in message:
                selected_modifier = value
                order['pending_modifier'] = value
                break
        
        if selected_modifier:
            return f"{selected_modifier} costs $0.75 extra. Reply YES to confirm or NO for regular milk."
        
        # Check for confirmation/denial
        is_confirmed, is_denied = confirm_modifications(message)
        
        if is_confirmed:
            modifier = order.get('pending_modifier', 'almond milk')
            order['cart'].add_item(order['pending_item'], modifiers=[modifier])
            order['state'] = OrderStage.MENU
            session_manager.update_session_state(phone_number, OrderStage.MENU)
            return order['cart'].get_summary()
        
        if is_denied:
            order['cart'].add_item(order['pending_item'])  # Add without modifications
            order['state'] = OrderStage.MENU
            session_manager.update_session_state(phone_number, OrderStage.MENU)
            return order['cart'].get_summary()
        
        return ("I didn't understand that. Please choose from:\n"
                "- Almond milk (+$0.75)\n"
                "- Oat milk (+$0.75)\n"
                "- Soy milk (+$0.75)\n"
                "Or reply 'no' for regular milk")
    
    # Handle menu state
    if current_state == OrderStage.MENU:
        # Check for special commands
        if message in ['done', 'checkout', 'pay']:
            return handle_checkout(phone_number)
        
        # Extract menu items and modifiers
        found_items = extract_menu_items_and_modifiers(message)
        if found_items:
            total_response = []
            for item in found_items:
                if item['modifiers']:
                    # If modifiers were specified, ask for confirmation
                    order['pending_item'] = item
                    order['pending_modifier'] = item['modifiers'][0]
                    order['state'] = 'AWAITING_MOD_CONFIRM'
                    total_response.append(
                        f"{item['modifiers'][0]} costs $0.75 extra. Reply YES to confirm or NO for regular milk."
                    )
                elif item['category'] in ['hot', 'cold']:
                    # For drinks without specified modifiers
                    order['pending_item'] = item
                    order['state'] = 'AWAITING_MOD_CONFIRM'
                    total_response.append(
                        "Would you like any milk modifications?\n"
                        "- Almond milk (+$0.75)\n"
                        "- Oat milk (+$0.75)\n"
                        "- Soy milk (+$0.75)\n"
                        "Reply 'no' for regular milk"
                    )
                else:
                    # Add non-drink items directly
                    order['cart'].add_item(item)
                    if not total_response:  # Only add summary if no other messages
                        total_response.append(order['cart'].get_summary())
            
            return "\n\n".join(total_response)
            
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