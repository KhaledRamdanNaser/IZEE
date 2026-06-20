import json
import urllib.request
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_nominatim(query):
    url = "http://localhost:8000/places/search?query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"Results for '{query}': {len(data['results'])}")
            for item in data['results']:
                print(f"  - {item.get('name')}")
    except Exception as e:
        print(f"Error fetching '{query}': {e}")

test_nominatim("شبرا الخيمة")
test_nominatim("ميدان التحرير")
