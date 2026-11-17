import os
from pathlib import Path
from typing import Any
from app.basics.utils import format_user_name

result = format_user_name("Alice")
print(os.getcwd())


current_file = Path(__file__)
print(current_file)
print(current_file.parent)
print(result)