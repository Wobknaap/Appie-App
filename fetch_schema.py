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

def fetch_schema(token):
    url = f"{BASE_URL}/graphql"
    headers = HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    headers.update({
        "x-apollo-operation-name": "IntrospectFilter",
        "apollographql-client-name": "nl.ah.Appie-apollo-ios",
    })

    # Introspect StoresFilterInput
    query = """
    query IntrospectFilter {
      __type(name: "StoresFilterInput") {
        inputFields {
          name
          type { name kind }
        }
      }
    }
    """
    
    response = requests.post(url, json={'query': query}, headers=headers)
    if response.status_code == 200:
        print(json.dumps(response.json(), indent=2))
        return response.json()
    else:
        print(f"Schema fetch failed: {response.text}")
        return None

if __name__ == "__main__":
    token = get_ah_token()
    if token:
        fetch_schema(token)
