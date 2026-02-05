import requests
import json
import uuid
import os

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

def fetch_eindhoven_stores(token):
    url = f"{BASE_URL}/graphql"
    headers = HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    headers.update({
        "x-apollo-operation-name": "FindStores",
        "apollographql-client-name": "nl.ah.Appie-apollo-ios",
    })

    # Query using verified filter 'cityStartsWith'
    query = """
    query FindStores {
      storesSearch(filter: {cityStartsWith: "Eindhoven"}, limit: 50) {
        result {
          id
          name
          address {
             street
             houseNumber
             postalCode
             city
          }
          geoLocation {
             latitude
             longitude
          }
        }
      }
    }
    """
    
    print("Fetching stores for Eindhoven...")
    response = requests.post(url, json={'query': query}, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        if "errors" in data:
            print("GraphQL Errors:", json.dumps(data["errors"], indent=2))
            return []
            
        stores = data.get("data", {}).get("storesSearch", {}).get("result", [])
        print(f"Found {len(stores)} stores.")
        return stores
    else:
        print(f"Request failed: {response.text}")
        return []

if __name__ == "__main__":
    token = get_ah_token()
    if token:
        stores = fetch_eindhoven_stores(token)
        if stores:
            # Transform to match expected format if needed, or just dump
            # Existing keys in stores.json might be different?
            # Let's save as stores.json directly for now or merge
            
            output_path = os.path.join("static", "stores.json")
            
            # Simple format: list of dicts
            with open(output_path, "w") as f:
                json.dump(stores, f, indent=2)
            print(f"Saved to {output_path}")
