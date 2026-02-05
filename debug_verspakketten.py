
import requests
import json
import uuid

# Configuration from dashboard.py
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

def get_bonus_test(token):
    auth_headers = HEADERS.copy()
    auth_headers["Authorization"] = f"Bearer {token}"
    
    query = """
    query GetNationalBonus {
      bonusPromotions {
        title
        category
        products {
          title
          brand
          category
          description
        }
      }
    }
    """
    try:
        response = requests.post(f"{BASE_URL}/graphql", json={"query": query}, headers=auth_headers)
        data = response.json()
        promotions = data.get('data', {}).get('bonusPromotions', [])
        
        print(f"Found {len(promotions)} promotions.")
        
        verspakketten = []
        for promo in promotions:
            # Check products in promo
            for prod in promo.get('products', []):
                title = prod.get('title', '').lower()
                category = prod.get('category', '').lower()
                
                if 'verspakket' in title or 'maaltijdpakket' in title:
                    verspakketten.append({
                        'promo_title': promo.get('title'),
                        'product_title': prod.get('title'),
                        'category': category
                    })

        print("\n--- Found Verspakketten ---")
        for v in verspakketten:
            print(f"- {v['product_title']} (Cat: {v['category']}) - Promo: {v['promo_title']}")
            
        return verspakketten

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    token = get_ah_token()
    if token:
        get_bonus_test(token)
