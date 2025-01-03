from datetime import datetime, timedelta
from src.core.state import OrderContext
from src.core.enums import OrderStage

class SessionManager:
    def __init__(self, timeout=timedelta(minutes=30)):
        self.sessions = {}
        self.timeout = timeout

    def create_session(self, phone_number):
        """Create a new session"""
        self.sessions[phone_number] = {
            'state': OrderStage.MENU,
            'last_activity': datetime.now(),
            'context': OrderContext()
        }
        return self.sessions[phone_number]

    def get_session_state(self, phone_number) -> OrderStage:
        """Get current state for a phone number"""
        if phone_number not in self.sessions:
            return OrderStage.MENU
        
        session = self.sessions[phone_number]
        if (datetime.now() - session['last_activity']) > self.timeout:
            del self.sessions[phone_number]
            return OrderStage.MENU
            
        return session['state']

    def update_session_state(self, phone_number, new_state: OrderStage):
        """Update session state"""
        if not isinstance(new_state, OrderStage):
            if isinstance(new_state, str):
                try:
                    new_state = OrderStage(new_state)
                except ValueError:
                    raise ValueError(f"Invalid state string: {new_state}")
            else:
                raise ValueError("State must be an OrderStage enum value or valid state string")

        if phone_number not in self.sessions:
            self.create_session(phone_number)
            
        self.sessions[phone_number]['state'] = new_state
        self.sessions[phone_number]['last_activity'] = datetime.now()

    def get_session(self, phone_number):
        """Get or create session"""
        if phone_number not in self.sessions:
            return self.create_session(phone_number)
        return self.sessions[phone_number]
    