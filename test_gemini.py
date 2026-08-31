import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
resp = client.models.generate_content(
        model="gemini-3.5-flash",
    contents='Reply with exactly this JSON and nothing else: {"parry": "ready"}',
)
print(resp.text)