import requests
import json
import uuid

BASE_URL = "https://api.ah.nl"
HEADERS = {
    "User-Agent": "Appie/9.28 (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)",
    "x-application": "AHWEBSHOP",
    "x-clientname": "appie-ios",
    "x-fraud-detection-installation-id": str(uuid.uuid4()),
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_ah_token():
    auth_url = f"{BASE_URL}/mobile-auth/v1/auth/token/anonymous"
    payload = {"clientId": "appie-ios"}
    try:
        response = requests.post(auth_url, json=payload, headers=HEADERS)
        response.raise_for_status()
        return response.json()['access_token']
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def search_stores(token):
    # 1. Single ID Test (1558)
    # 2. Geo Search (Eindhoven)
    
    endpoints = [
        # Check specific ID
        ("ID_CHECK", "https://api.ah.nl/mobile-services/section/v1/stores/1558"),
        ("ID_CHECK", "https://api.ah.nl/mobile-services/v1/stores/1558"),
        
        # Geo Search
        ("GEO", "https://api.ah.nl/mobile-services/v1/stores?lat=51.4416&lon=5.4697"),
        ("GEO", "https://api.ah.nl/mobile-services/v2/stores?lat=51.4416&lon=5.4697"),
    ]

    for label, url in endpoints:
        print(f"[{label}] Trying: {url}")
        try:
            curr_headers = HEADERS.copy()
            curr_headers["Authorization"] = f"Bearer {token}"
            response = requests.get(url, headers=curr_headers)
            
            if response.status_code == 200:
                print(f"SUCCESS {label}!")
                return response.json()
            else:
                print(f"Failed ({response.status_code})")
        except Exception as e:
            print(e)

    return []

if __name__ == "__main__":
    token = get_ah_token()
    if token:
        result = search_stores(token)
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("No stores found")
