import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), 'config/.env'))

print(os.getenv("OPENAI_API_KEY"))
print(os.getenv("TELEGRAM_API_KEY"))