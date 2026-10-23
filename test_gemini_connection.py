import os
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found. Check your .env file.")

client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=60000))
start = time.time()
MAX_ATTEMPTS = 3
start = time.time()
for attempt in range(1, MAX_ATTEMPTS + 1):
    try:
        interaction = client.interactions.create(
            model="gemini-3.8-flash",
            input="Describe the functional specification for an 8-bit synchronous counter with asynchronous reset, in 3 sentences."
        )
        break
    except Exception as e:
        print(f"Attempt {attempt}/{MAX_ATTEMPTS} failed: {type(e).__name__}")
        if attempt == MAX_ATTEMPTS:
            raise
        time.sleep(10 * attempt)   # wait 10 s, then 20 s (a "backoff": waiting longer after each failure)

print(f"Latency: {time.time() - start:.1f} s")
print("Gemini connection successful!")
print("Response:")
print(interaction.output_text)