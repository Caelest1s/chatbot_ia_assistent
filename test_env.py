import os
from src.config import settings_loader 

print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("TELEGRAM_API_KEY"))