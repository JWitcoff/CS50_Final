from datetime import datetime, timedelta
from src.core.state import OrderContext
from src.core.enums import OrderStage

class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.timeout = timedelta(minutes=10)
        
    def start_session(self, phone_number):
        """Initialize or reset a session"""
        self.sessions[phone_number] = {
            'started_at': datetime.now(),
            'last_activity': datetime.now(),
            'interaction_count': 0
        }
        
    def update_session(self, phone_number):
        """Update session activity"""
        if phone_number in self.sessions:
            self.sessions[phone_number]['last_activity'] = datetime.now()
            self.sessions[phone_number]['interaction_count'] += 1
            
    def is_session_active(self, phone_number):
        """Check if session is still valid"""
        if phone_number not in self.sessions:
            return False
        
        last_activity = self.sessions[phone_number]['last_activity']
        return datetime.now() - last_activity < self.timeout
 