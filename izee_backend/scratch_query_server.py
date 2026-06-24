import urllib.request
import json

url = "http://127.0.0.1:8000/control-center/bus-routes"
try:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        print("Status Code:", res.status)
        print("Response:", json.loads(res.read().decode('utf-8'))[:5])
except urllib.error.HTTPError as e:
    print("HTTP Error Code:", e.code)
    print("Response detail:", e.read().decode('utf-8'))
except Exception as e:
    print("Error:", e)
