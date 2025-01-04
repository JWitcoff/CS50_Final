# Standard library imports
from datetime import datetime, timedelta
import logging
import os
import uuid
import sys
from decimal import Decimal

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
from src.core.state import CustomerContext, OrderContext
from src.core.conversation_handler import ConversationHandler

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
conversation_handler = ConversationHandler(openai_client)

# In-memory storage
active_orders = {}
completed_orders = {}
customer_contexts = {}

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

    # Get or create customer context
    if phone_number not in customer_contexts:
        customer_contexts[phone_number] = CustomerContext()
    customer_context = customer_contexts[phone_number]

    # Try handling casual conversation first
    casual_response = conversation_handler.handle_chat(message)
    if casual_response and message not in ['menu', 'start']:
        return casual_response
    
    # Handle MENU command in any state
    if message == 'menu':
        return get_menu_message()
        
    # Handle START command
    if message == 'start':
        active_orders[phone_number] = {
            'state': OrderStage.MENU,
            'cart': ShoppingCart(),
            'order_queue': OrderQueue()
        }
        # Add personalized welcome for returning customers
        if customer_context.visit_count > 0:
            return conversation_handler.get_friendly_response(
                get_menu_message(),
                customer_context,
                is_returning=True
            )
        return get_menu_message()
        
    # Check if user has an active order
    if phone_number not in active_orders:
        return conversation_handler.get_friendly_response(
            "Please text 'START' to begin ordering.",
            customer_context
        )
        
    order = active_orders[phone_number]
    current_state = order['state']
    logger.info(f"Current state for {phone_number}: {current_state}")
    
    # Handle AWAITING_MOD_CONFIRM state
    if current_state == OrderStage.AWAITING_MOD_CONFIRM:
        has_modifier, modifier = menu_handler.check_for_modification(message)
        if has_modifier:
            order['pending_modifier'] = modifier
            return conversation_handler.get_friendly_response(
                f"{modifier} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                customer_context
            )
            
        if menu_handler.is_confirmation(message):
            if 'pending_modifier' in order:
                order['cart'].add_item(order['pending_item'], modifiers=[order['pending_modifier']])
                customer_context.usual_modifications.append(order['pending_modifier'])
            else:
                order['cart'].add_item(order['pending_item'])
            order['state'] = OrderStage.MENU
            return conversation_handler.get_friendly_response(
                order['cart'].get_summary(),
                customer_context,
                item_added=True
            )
            
        if menu_handler.is_denial(message):
            order['cart'].add_item(order['pending_item'])
            order['state'] = OrderStage.MENU
            return order['cart'].get_summary()
            
        return conversation_handler.get_friendly_response(
            "Please choose a milk type or reply NO for regular milk:\n"
            "- Almond milk (+$0.75)\n"
            "- Oat milk (+$0.75)\n"
            "- Soy milk (+$0.75)",
            customer_context
        )
    
    # Handle menu state
    if current_state == OrderStage.MENU:
        # Check for checkout commands
        if message in ['done', 'checkout', 'pay']:
            return handle_checkout(phone_number)
            
        # Extract menu items and modifiers
        found_items = menu_handler.extract_menu_items_and_modifiers(message)
        if found_items:
            for item in found_items:
                if item.get('modifiers'):
                    # If modifiers were specified in the order
                    mod = item['modifiers'][0]
                    order['pending_item'] = item
                    order['pending_modifier'] = mod
                    order['state'] = OrderStage.AWAITING_MOD_CONFIRM
                    return conversation_handler.get_friendly_response(
                        f"{mod} costs $0.75 extra. Reply YES to confirm or NO for regular milk.",
                        customer_context
                    )
                elif item['category'] in ['hot', 'cold']:
                    # If it's a drink that could have modifiers
                    order['pending_item'] = item
                    order['state'] = OrderStage.AWAITING_MOD_CONFIRM
                    # Check if customer has usual modification
                    if customer_context.usual_modifications:
                        usual_mod = customer_context.usual_modifications[-1]
                        return conversation_handler.get_friendly_response(
                            f"Would you like your usual {usual_mod}? Reply YES or choose another:\n"
                            "- Almond milk (+$0.75)\n"
                            "- Oat milk (+$0.75)\n"
                            "- Soy milk (+$0.75)\n"
                            "Or reply 'no' for regular milk",
                            customer_context
                        )
                    return conversation_handler.get_friendly_response(
                        "Would you like any milk modifications?\n"
                        "- Almond milk (+$0.75)\n"
                        "- Oat milk (+$0.75)\n"
                        "- Soy milk (+$0.75)\n"
                        "Reply 'no' for regular milk",
                        customer_context
                    )
                else:
                    # Non-drink items go straight to cart
                    order['cart'].add_item(item)
            
            return conversation_handler.get_friendly_response(
                order['cart'].get_summary(),
                customer_context,
                items_added=True
            )
        
        return conversation_handler.get_friendly_response(
            "I didn't recognize those items. Would you like to see our menu?",
            customer_context,
            menu_prompt=True
        )
    
    # Handle payment state
    if current_state == OrderStage.PAYMENT:
        if message.lower() in ['cash', 'card']:
            response = payment_handler.handle_payment(phone_number, message, active_orders, completed_orders)
            return conversation_handler.get_friendly_response(response, customer_context, payment=True)
        return conversation_handler.get_friendly_response(
            "Please choose your payment method:\n"
            "- Reply CASH for cash payment\n"
            "- Reply CARD for credit card",
            customer_context
        )
    
    # Handle card payment state
    if current_state == OrderStage.AWAITING_CARD:
        response = payment_handler.handle_card_payment(phone_number, message, active_orders, completed_orders)
        return conversation_handler.get_friendly_response(response, customer_context, payment=True)
    
    return conversation_handler.get_friendly_response(
        "I'm not sure what to do. Would you like to start a new order?",
        customer_context,
        confused=True
    )

def handle_checkout(phone_number):
    """Handle checkout process"""
    cart = active_orders[phone_number]['cart']
    if cart.is_empty():
        return conversation_handler.get_friendly_response(
            "Your cart is empty! Would you like to see our menu?",
            customer_contexts.get(phone_number, CustomerContext()),
            empty_cart=True
        )
    
    active_orders[phone_number]['state'] = OrderStage.PAYMENT
    
    return conversation_handler.get_friendly_response(
        f"Total: ${cart.get_total():.2f}\n"
        "How would you like to pay?\n"
        "Reply with:\n"
        "- CASH for cash payment\n"
        "- CARD to pay by credit card",
        customer_contexts.get(phone_number, CustomerContext()),
        checkout=True
    )

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