from datetime import datetime, timedelta
from src.core.state import OrderContext
from src.core.enums import OrderStage

class SessionManager:
    def __init__(self, timeout=timedelta(minutes=30)):
        self.sessions = {}
        self.timeout = timeout

    def get_session_state(self, phone_number):
        if phone_number in self.sessions:
            return self.sessions[phone_number].get('state', OrderStage.MENU)
        return OrderStage.MENU

    def update_session_state(self, phone_number, new_state):
        if not isinstance(new_state, OrderStage):
            raise ValueError("State must be an OrderStage enum value")
        if phone_number in self.sessions:
            self.sessions[phone_number]['state'] = new_state
            self.sessions[phone_number]['last_activity'] = datetime.now()
 