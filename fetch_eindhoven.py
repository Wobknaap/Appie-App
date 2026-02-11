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
        new_stores = fetch_eindhoven_stores(token)
        if new_stores:
            output_path = os.path.join("static", "stores.json")
            
            # Load existing stores
            try:
                with open(output_path, "r") as f:
                    existing_stores = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                existing_stores = []
                
            # Create a lookup for existing stores (by ID as string)
            store_map = {str(s.get("id")): s for s in existing_stores}
            
            # Process new stores
            for s in new_stores:
                sid = str(s["id"])
                street = s["address"]["street"]
                city = s["address"]["city"]
                
                # Format nice name: "AH [Street]"
                # If the explicit name from API is wildly different (e.g. AH XL), we might want that
                # But "AH [Street]" is a safe baseline matching user's "AH Woenselse Markt" style
                # Simple heuristic: if name contains "XL", keep that, else construct
                raw_name = s.get("name", "")
                if "XL" in raw_name:
                    nice_name = f"AH XL {street}"
                else:
                    nice_name = f"AH {street}"

                # Construct enhanced store object
                # Keep existing fields if we want, but prioritize new details
                filtered_store = {
                    "id": sid,
                    "name": nice_name,
                    "city": city,
                    "address": s["address"],
                    "geoLocation": s["geoLocation"]
                }
                
                # Update or Add
                store_map[sid] = filtered_store
                
            # Convert back to list and sort?
            # Prefer keeping original order roughly, but map destroys order.
            # Let's just create a new list: values of map
            combined_stores = list(store_map.values())
            
            # Sort by City, then Name for neatness
            combined_stores.sort(key=lambda x: (x.get("city", ""), x.get("name", "")))

            with open(output_path, "w") as f:
                json.dump(combined_stores, f, indent=4)
            print(f"Updated {output_path} with {len(new_stores)} Eindhoven stores. Total: {len(combined_stores)}")
