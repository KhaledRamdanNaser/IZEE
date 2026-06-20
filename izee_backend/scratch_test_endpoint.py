import requests

try:
    print("Testing /places/search...")
    res = requests.get("http://localhost:8000/places/search?query=station")
    print(res.status_code)
    print(res.json())
except Exception as e:
    print(e)
