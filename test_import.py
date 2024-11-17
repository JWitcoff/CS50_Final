import os
import sys

# Add immediate feedback
print("Script starting...")

# Add the project root to the Python path explicitly
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    print(f"Added {current_dir} to Python path")

print(f"Current working directory: {os.getcwd()}")
print(f"Python path: {sys.path}")
print("\nTrying import...")

try:
    print("About to import OrderStage...")
    from src.core.enums import OrderStage
    print("Successfully imported OrderStage")
    print(OrderStage)
    print(list(OrderStage))
except ImportError as e:
    print(f"Import failed with error: {e}")
    print(f"Error type: {type(e)}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"Unexpected error: {e}")
    print(f"Error type: {type(e)}")
    import traceback
    traceback.print_exc()

print("Script finished.") 