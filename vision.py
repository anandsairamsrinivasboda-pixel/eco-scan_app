
import os
from google import genai
from google.genai import types
import json

def parse_receipt(image_path):
    # Initialize the client (it automatically looks for your GEMINI_API_KEY environment variable)
    client = genai.Client()

    # Ask Gemini to extract items from the receipt image
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(
                data=open(image_path, "rb").read(),
                mime_type="image/jpeg",
            ),
            "Extract all grocery items, their quantities, and units from this receipt. "
            "Return ONLY a JSON list of dictionaries with keys: 'item', 'quantity', and 'unit'."
        ],
    )
    
    # Return the text response (which contains our clean list for your calc.py file)
    return response.text
