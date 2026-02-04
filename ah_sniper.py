import requests
import pandas as pd
import uuid
import os
from datetime import datetime

# 1. Configuraties
BASE_URL = "https://api.ah.nl"
STORE_ID = "1558"  # Woenselse Markt Eindhoven
CSV_FILE = "laatste_kans_trends.csv"

# Verplichte headers voor de AH API
HEADERS = {
    "User-Agent": "Appie/9.28 (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)",
    "x-application": "AHWEBSHOP",
    "x-clientname": "appie-ios",
    "x-fraud-detection-installation-id": str(uuid.uuid4()),
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def get_ah_token():
    """Haalt een anonieme token op voor de AH API"""
    auth_url = f"{BASE_URL}/mobile-auth/v1/auth/token/anonymous"
    payload = {"clientId": "appie-ios"}
    response = requests.post(auth_url, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()['access_token']

def fetch_laatste_kans(token):
    """Haalt de lokale 'Laatste Kans' koopjes op"""
    url = f"{BASE_URL}/graphql"
    graphql_headers = HEADERS.copy()
    graphql_headers.update({
        "Authorization": f"Bearer {token}",
        "x-apollo-operation-name": "GetBargains",
        "apollographql-client-name": "nl.ah.Appie-apollo-ios",
    })
    
    query = """
    query GetBargains($storeId: String!) {
      bargainItems(storeId: $storeId) {
        categoryTitle
        product { 
            title 
            brand 
            salesUnitSize 
        }
        bargainPrice { 
            priceWas 
            priceNow 
        }
        markdown { 
            markdownPercentage 
        }
        stock
      }
    }
    """
    payload = {
        'query': query, 
        'variables': {'storeId': STORE_ID}, 
        'operationName': 'GetBargains'
    }
    response = requests.post(url, json=payload, headers=graphql_headers)
    response.raise_for_status()
    return response.json().get('data', {}).get('bargainItems', [])

def main():
    print(f"[{datetime.now()}] Data ophalen voor winkel {STORE_ID}...")
    
    try:
        token = get_ah_token()
        items = fetch_laatste_kans(token)
        
        if not items:
            print("Geen items gevonden.")
            return

        # Data platstaan naar DataFrame
        df = pd.json_normalize(items)
        
        # Kolommen opschonen
# Kolommen opschonen
        # Kolommen opschonen
        df.columns = [c.replace('product.', '').replace('bargainPrice.', '').replace('markdown.', '') for c in df.columns]      
        
        # Tijdstempel toevoegen voor trend-analyse
        df['fetch_timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Alleen relevante kolommen behouden
        cols_to_keep = ['fetch_timestamp', 'title', 'brand', 'categoryTitle', 'priceWas', 'priceNow', 'markdownPercentage', 'stock']
        df = df[cols_to_keep]

        # Opslaan naar CSV (append mode)
        file_exists = os.path.isfile(CSV_FILE)
        df.to_csv(CSV_FILE, mode='a', index=False, header=not file_exists)
        
        print(f"✅ Succes! {len(df)} items toegevoegd aan {CSV_FILE}.")

    except Exception as e:
        print(f"❌ Fout opgetreden: {e}")

if __name__ == "__main__":
    main()