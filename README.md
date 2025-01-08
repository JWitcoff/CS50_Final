Hello! 

This is my submission for CS50's Final Project: Coffee S50. 

I'm very proud of the effort and correlative results! 

As I have learned time and time again: building simplicity is anything but simple. 

# Coffee Shop SMS Ordering System

A sophisticated SMS-based ordering system that enables customers to order coffee and food items using natural language through text messages. This project combines modern web technologies with artificial intelligence to create a seamless, conversational ordering experience.

## Project Overview

The Coffee Shop SMS Ordering System transforms the traditional coffee ordering experience by allowing customers to place orders through text messages using natural language. Whether someone orders "an iced latte with almond milk and a muffin" or adds items sequentially, the system handles complex orders with customizations while maintaining a natural conversation flow. The system is particularly innovative in its ability to maintain context throughout the ordering process and handle multiple items with different modifications simultaneously.

## Technology Stack

- **Backend**: Python Flask with Gunicorn
- **SMS Integration**: Twilio API
- **Natural Language Processing**: OpenAI API
- **State Management**: Custom Python implementation
- **Testing**: pytest with scenario-based testing
- **Deployment Platform**: Render
  - Continuous deployment from GitHub
  - Automatic HTTPS/SSL
  - Application logging and monitoring
- **IDE**: Cursor AI
- **Feedbacking**: Claude 3.5 Sonnet

## Design Choices and Implementation Details

### Core Components

The project is structured into modular components, each handling specific aspects of the ordering system:

#### Cart Management (`src/core/cart.py`)
Initially, the cart system struggled with handling multiple items when some required modifications. After careful consideration, we implemented a two-phase item processing approach:
- Immediately adds non-modifiable items to the cart
- Queues items requiring modification for sequential processing
- Maintains cart state throughout the modification flow

This design choice significantly improved the user experience by ensuring no items are lost during the ordering process.

#### Conversation Handling (`src/core/conversation_handler.py` and `dialogue.py`)
We chose to separate conversation handling into two components:
- `conversation_handler.py`: Manages immediate message processing
- `dialogue.py`: Handles higher-level conversation flow

This separation allows for better testing and easier maintenance of the conversational aspects.

#### Menu and State Management (`src/core/menu_handler.py` and `state.py`)
The menu handler was designed to be flexible and extensible:
- Processes natural language menu selections
- Handles modifiers and customizations
- Integrates with the state management system

The state management system tracks:
- Order stages (MENU, AWAITING_MOD_CONFIRM, PAYMENT)
- Session context
- Cart state

#### Payment Processing (`src/core/payment.py`)
Implements a modular payment system supporting:
- Cash payments
- Card payments (expandable for different providers)
- Order confirmation generation

### Testing Strategy

The testing framework (`tests/`) is comprehensive and scenario-based:

- `test_scenarios.py`: Defines real-world ordering scenarios
- `test_suite.py`: Orchestrates test execution
- `conversation_analyzer.py`: Validates conversation flows
- `test_verifier.py`: Verifies test outcomes

This structure was chosen to ensure thorough testing of both individual components and integrated functionality.

## Project Structure

```
├── app.py                  # Main application entry point
├── src/
│   ├── core/              # Core business logic
│   │   ├── cart.py        # Cart management
│   │   ├── config.py      # Configuration
│   │   ├── conversation_handler.py  # Message processing
│   │   ├── dialogue.py    # Conversation management
│   │   ├── menu_handler.py # Menu processing
│   │   ├── payment.py     # Payment handling
│   │   └── state.py       # State management
│   └── utils/
│       └── nlp.py         # NLP utilities
└── tests/                 # Test suite
```

## Deployment and Configuration

The application is deployed on Render, chosen for its:
- Seamless GitHub integration
- Built-in SSL/HTTPS support
- Comprehensive logging system
- Easy environment variable management

Configuration files:
- `Procfile`: Defines process types for deployment
- `gunicorn_config.py`: Production server configuration
- `requirements.txt`: Project dependencies

## Key Features

### Natural Language Processing
The system uses OpenAI's API to understand natural language orders, handling:
- Complex modifiers ("iced latte with almond milk")
- Multiple items in one message
- Conversational context maintenance

### Smart Cart Management
- Real-time cart updates
- Multiple items with different modifiers
- Accurate price calculations
- State persistence throughout conversations

### State Management
- Robust order tracking
- Multi-user session management
- Contextual responses

### Payment Processing
- Multiple payment methods
- Secure handling
- Order confirmation system

## Installation and Setup

1. Clone the repository:
```bash
git clone [repository-url]
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
```bash
cp .env.example .env
# Add your credentials:
# - TWILIO_ACCOUNT_SID
# - TWILIO_AUTH_TOKEN
# - OPENAI_API_KEY
```

4. Run locally:
```bash
python app.py
```

## Future Enhancements

Planned improvements include:
- Order history tracking
- Customer preference learning
- Menu customization interface
- Analytics dashboard
- Extended payment integrations

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
