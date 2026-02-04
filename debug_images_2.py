import requests
import dashboard
import json

print("--- DEBUG 2 ---")
token = dashboard.get_ah_token()
if not token:
    print("No token")
    exit()
    
headers = dashboard.HEADERS.copy()
headers["Authorization"] = f"Bearer {token}"

# 1. Get Product Detail to see Image URL
pid = 4169 # Champignons
url = f"{dashboard.BASE_URL}/mobile-services/product/detail/v4/fir/{pid}"
print(f"\n1. Fetching Product {pid} details...")
try:
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        data = res.json()
        print("Product Data:")
        # Print images part
        card = data.get('productCard', {})
        images = card.get('images', [])
        if images:
            print("Found Images:")
            for img in images:
                print(f" - {img.get('url')}")
        else:
            print("No images found in detail response.")
    else:
        print(f"Failed: {res.status_code}")
except Exception as e:
    print(f"Error: {e}")

# 2. Test Store Search Guesses
print("\n2. Store Search Guesses...")
guesses = [
    "/mobile-services/v1/store/search?query=eindhoven",
    "/mobile-services/store/search/v1?query=eindhoven",
    "/mobile-services/stores/search?q=eindhoven",
    "/mobile-services/pos/v1/shops?q=eindhoven" 
]

for path in guesses:
    url = f"{dashboard.BASE_URL}{path}"
    print(f"Testing {url}...")
    try:
        res = requests.get(url, headers=headers)
        print(f"[{res.status_code}]")
        if res.status_code == 200:
            print("SUCCESS!")
            print(str(res.json())[:200])
    except Exception as e:
        print(f"Error: {e}")
