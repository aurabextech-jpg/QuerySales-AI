import asyncio
import json
import httpx

TOKEN = "eyJhbGciOiJFZERTQSIsImtpZCI6IjYwYThkNWZiLTcxZDktNDM3Ny04OGMwLTExMTJjYWI1MmI2MSJ9.eyJpYXQiOjE3Nzg5NTEzMTgsIm5hbWUiOiJBbWFkIEFzaWYiLCJlbWFpbCI6ImFtYWRAZ21haWwuY29tIiwiZW1haWxWZXJpZmllZCI6ZmFsc2UsImNyZWF0ZWRBdCI6IjIwMjYtMDUtMTZUMTU6MTM6MjQuNjQ4WiIsInVwZGF0ZWRBdCI6IjIwMjYtMDUtMTZUMTU6MTM6MjQuNjQ4WiIsInJvbGUiOiJhdXRoZW50aWNhdGVkIiwiYmFubmVkIjpmYWxzZSwiYmFuUmVhc29uIjpudWxsLCJiYW5FeHBpcmVzIjpudWxsLCJpZCI6Ijc0YTU5YjNlLThhM2MtNDA0MC1hYmI0LTljNjMzMmYwYjM4MyIsInN1YiI6Ijc0YTU5YjNlLThhM2MtNDA0MC1hYmI0LTljNjMzMmYwYjM4MyIsImV4cCI6MTc3ODk1MjIxOCwiaXNzIjoiaHR0cHM6Ly9lcC1zdGVlcC1iYXNlLWFwMzkzNHJhLm5lb25hdXRoLmMtNy51cy1lYXN0LTEuYXdzLm5lb24udGVjaCIsImF1ZCI6Imh0dHBzOi8vZXAtc3RlZXAtYmFzZS1hcDM5MzRyYS5uZW9uYXV0aC5jLTcudXMtZWFzdC0xLmF3cy5uZW9uLnRlY2gifQ.ASmEEZsXJKzydFtxujja6qOavPwPmEoYwa8cILXBQpuLt1Sc5b381X7QqhRT_FfprYb78SILknGwQufGfhItCQ"
RUN_ID = "37841d04-6abd-4f32-9557-9bb704de81ef"
URL = "http://127.0.0.1:8000/api/chat/stream" # Assuming /api/chat/stream is the mapped route in main.py

async def main():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }
    
    payload = {
        "run_id": RUN_ID,
        "messages": [
            {"role": "user", "content": "Find restaurants in Lahore and suggest one."}
        ]
    }
    
    print(f"Connecting to {URL}...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", URL, headers=headers, json=payload) as response:
                print(f"Status: {response.status_code}")
                if response.status_code != 200:
                    text = await response.aread()
                    print(f"Error body: {text.decode('utf-8')}")
                    return

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data.get("type") == "token":
                            print(data.get("content", ""), end="", flush=True)
                        elif data.get("type") == "tool":
                            print(f"\n[TOOL CALLED: {data.get('tool')}]")
                        elif data.get("type") == "agent":
                            print(f"\n[AGENT SWITCH: {data.get('agent')}]")
                        elif data.get("type") == "tool_output":
                            print(f"\n[TOOL OUTPUT: {data.get('content')[:100]}...]")
                        elif data.get("type") == "error":
                            print(f"\n[ERROR: {data.get('content')}]")
                        elif data.get("type") == "done":
                            print(f"\n\n[DONE]\nFinal Output: {data.get('content')[:50]}...")
                        else:
                            print(f"\n[EVENT: {data.get('type')}] -> {data}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
