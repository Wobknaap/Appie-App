import dashboard
import requests
import sys

# Windows encoding fix
sys.stdout.reconfigure(encoding='utf-8')

def fetch_laatste_kans(token, store_id):
    url = f"{dashboard.BASE_URL}/graphql"
    headers = dashboard.HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    headers.update({
        "x-apollo-operation-name": "GetBargains",
        "apollographql-client-name": "nl.ah.Appie-apollo-ios",
    })
    
    query = """
    query GetBargains($storeId: String!) {
      bargainItems(storeId: $storeId) {
        product {
          id
          title
        }
      }
    }
    """
    
    response = requests.post(url, json={'query': query, 'variables': {'storeId': store_id}}, headers=headers)
    return response.json()

def get_bonus(token):
    headers = dashboard.HEADERS.copy()
    headers["Authorization"] = f"Bearer {token}"
    query = """
    query GetNationalBonus {
      bonusPromotions {
        products {
          id
          title
        }
      }
    }
    """
    response = requests.post(f"{dashboard.BASE_URL}/graphql", json={"query": query}, headers=headers)
    return response.json()

print("--- TESTING id ---")
token = dashboard.get_ah_token()
if token:
    print("Token OK")
    
    print("1. Bargains id...")
    res = fetch_laatste_kans(token, dashboard.STORE_ID)
    if 'errors' in res:
        print("X Error:", res['errors'][0]['message'])
    else:
        items = res.get('data', {}).get('bargainItems', [])
        print(f"V Success! Got {len(items)} items.")
        if items: print("Sample:", items[0])

    print("\n2. Bonus id...")
    res = get_bonus(token)
    if 'errors' in res:
        print("X Error:", res['errors'][0]['message'])
    else:
        promos = res.get('data', {}).get('bonusPromotions', [])
        print(f"V Success! Got {len(promos)} promos.")
        if promos: 
             products = promos[0].get('products', [])
             if products: print("Sample:", products[0])
