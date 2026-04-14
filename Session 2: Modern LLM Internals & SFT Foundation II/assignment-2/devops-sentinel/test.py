from dotenv import load_dotenv
import os
from google import genai

# Load variables from .env
load_dotenv()

# Fetch the key
api_key = os.getenv("GEMINI_API_KEY")

# Use it
client = genai.Client(api_key=api_key)

# response = client.models.generate_content(
#     model="gemini-3-flash-preview",
#     contents="Explain AI in one line"
# )

response = client.models.generate_content(
    model="gemini-3-flash-preview",
    contents="Hello AI!!!"
)


print(response.text)