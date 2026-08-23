from groq import Groq
from dotenv import load_dotenv  # ← Load from .env file
import os

load_dotenv()  # ← This reads .env into os.environ

api_key = os.getenv('GROQ_API_KEY')
print(f"API Key loaded: {bool(api_key)}")
print(f"API Key length: {len(api_key) if api_key else 0}")

if not api_key:
    print("ERROR: GROQ_API_KEY is empty or not set!")
else:
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model='openai/gpt-oss-120b',
            messages=[{'role': 'user', 'content': 'test'}],
            max_tokens=10
        )
        print('✅ Model works!')
    except Exception as e:
        print(f'❌ Error: {type(e).__name__}: {str(e)}')