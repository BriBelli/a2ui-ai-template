
import os
import openai

# Load OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")




def get_openai_completion(prompt: str, model: str = "gpt-3.5-turbo", max_tokens: int = 50):
    if not prompt:
        return {"error": "Prompt is required.", "status_code": 400}
    try:
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return {"response": response.choices[0].message.content.strip(), "status_code": 200}
    except Exception as e:
        print(f"OpenAI error: {e}")
        return {"error": "An error occurred processing your request", "status_code": 500}
