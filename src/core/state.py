from datetime import datetime
from src.core.enums import OrderStage

class OrderContext:
    def __init__(self):
        self.current_drink = None
        self.modifications = []
        self.stage = OrderStage.INITIAL
        self.last_interaction = datetime.now()
    # Your OrderContext implementation
    pass 
print("Importing OrderStage...")
from src.core.enums import OrderStage
print("Successfully imported OrderStage") 