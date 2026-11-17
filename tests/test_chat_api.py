import requests


url = "http://127.0.0.1:8000/api/v1/chat"

payload = {
    "message": "什么是 RAG？",
    "model": "deepseek-chat",
    "temperature": 0.7,
    "stream": False
}

response = requests.post(url, json=payload)

print(response.status_code)
print(response.json())