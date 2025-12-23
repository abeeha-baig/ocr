# create a gemini client that uses a default model until specified otherwise
import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def get_gemini_model(model_name="gemini-2.5-flash-lite"):
    return genai.GenerativeModel(model_name)

MODEL_NAME = "gemini-2.5-flash-lite"
def get_default_gemini_model():
    return get_gemini_model(MODEL_NAME)
def get_gemini_model_by_name(model_name):
    return get_gemini_model(model_name)
