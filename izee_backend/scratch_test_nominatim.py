import json
import urllib.request
import urllib.parse
import sys

sys.stdout.reconfigure(encoding='utf-8')

def test_nominatim(query):
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "limit": 5,
        "countrycodes": "EG",
        "viewbox": "30.7,30.3,31.8,29.8",
        "bounded": 1,
    }
    url = base_url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            print(f"Nominatim Results for '{query}': {len(data)}")
            for item in data:
                print(f"  - {item.get('display_name')}")
    except Exception as e:
        print(f"Error fetching '{query}': {e}")

test_nominatim("شبرا الخيمة")
test_nominatim("ميدان التحرير")
