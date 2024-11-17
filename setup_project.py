import os
import shutil
from pathlib import Path

def setup_project_structure():
    # Define the root directory
    root = Path("coffee-shop-sms")
    
    # Create directory structure
    directories = [
        "src/api",
        "src/core",
        "src/utils",
        "tests/scenarios",
        "tests/utils",
        "templates"
    ]
    
    for dir_path in directories:
        os.makedirs(root / dir_path, exist_ok=True)
    
    # Create empty __init__.py files
    init_locations = [
        "src",
        "src/api",
        "src/core",
        "src/utils",
        "tests",
        "tests/scenarios",
        "tests/utils"
    ]
    
    for location in init_locations:
        with open(root / location / "__init__.py", "w") as f:
            pass
    
    # Define file moves (source -> destination)
    file_moves = {
        "dialogue.py": "src/core/dialogue.py",
        "order_processor.py": "src/core/order.py",
        "order_state.py": "src/core/state.py",
        "payment_handler.py": "src/core/payment.py",
        "session_manager.py": "src/core/session.py",
        "message_formatter.py": "src/utils/formatter.py",
        "nlp_utils.py": "src/utils/nlp.py",
        "app.py": "src/api/routes.py",
        "templates/index.html": "templates/index.html"
    }
    
    # Move files
    for source, dest in file_moves.items():
        try:
            source_path = Path(source)
            dest_path = root / dest
            
            # Create parent directories if they don't exist
            os.makedirs(dest_path.parent, exist_ok=True)
               
            # Copy the file
            if source_path.exists():
                shutil.copy2(source_path, dest_path)
                print(f"Moved {source} to {dest}")
            else:
                print(f"Warning: Source file {source} not found")
        except Exception as e:
            print(f"Error moving {source}: {str(e)}")
    
    # Keep these files at root level
    root_files = ["Procfile", "requirements.txt", "runtime.txt"]
    for file in root_files:
        if Path(file).exists():
            shutil.copy2(file, root / file)
            print(f"Copied {file} to project root")

if __name__ == "__main__":
    setup_project_structure()