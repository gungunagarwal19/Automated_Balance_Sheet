import google.generativeai as genai
genai.configure(api_key="YOUR_GEMINI_API_KEY")
print([m for m in genai.list_models()])
