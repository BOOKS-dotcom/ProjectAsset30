from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.5",
    input="こんにちは！簡単に自己紹介してください。"
)

print(response.output_text)