import requests
import pandas as pd
import numpy as np
import uuid
import time
from flask import Flask, render_template, jsonify

app = Flask(__name__)


# --- CONFIGURATION ---
BASE_URL = "https://api.ah.nl"
DEFAULT_STORE_ID = "1558"  # Woenselse Markt Eindhoven
HEADERS = {
    "User-Agent": "Appie/9.28 (iPhone17,3; iPhone; CPU OS 26_1 like Mac OS X)",
    "x-application": "AHWEBSHOP",
    "x-clientname": "appie-ios",
    "x-fraud-detection-installation-id": str(uuid.uuid4()),
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# Simple in-memory cache
cache = {
    "data": None,
    "timestamp": 0
}
CACHE_DURATION = 300  # 5 minutes

def get_ah_token():
    auth_url = f"{BASE_URL}/mobile-auth/v1/auth/token/anonymous"
    payload = {"clientId": "appie-ios"}
    try:
        response = requests.post(auth_url, json=payload, headers=HEADERS)
        response.raise_for_status()
        token_data = response.json()
        return token_data['access_token']
    except Exception as e:
        print(f"Error getting token: {e}")
        return None

def fetch_laatste_kans(token, store_id):
    url = f"{BASE_URL}/graphql"
    
    graphql_headers = HEADERS.copy()
    graphql_headers["Authorization"] = f"Bearer {token}"
    graphql_headers.update({
        "x-apollo-operation-name": "GetBargains",
        "apollographql-client-name": "nl.ah.Appie-apollo-ios",
    })
    
    bargain_query = """
    query GetBargains($storeId: String!) {
      bargainItems(storeId: $storeId) {
        categoryTitle
        product {
          id
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
          markdownExpirationDate
        }
        stock
      }
    }
    """
    
    payload = {
        'query': bargain_query, 
        'variables': {'storeId': store_id},
        'operationName': 'GetBargains'
    }
    
    try:
        response = requests.post(url, json=payload, headers=graphql_headers)
        if response.status_code != 200:
            print(f"GraphQL Error: {response.status_code} - {response.text}")
            return []
            
        data = response.json()
        if 'errors' in data:
            print("GraphQL Errors:", data['errors'])
            return []
            
        return data.get('data', {}).get('bargainItems', [])
    except Exception as e:
        print(f"Error fetching bargains: {e}")
        return []

def get_bonus_promotions(token):
    auth_headers = HEADERS.copy()
    auth_headers["Authorization"] = f"Bearer {token}"
    
    query = """
    query GetNationalBonus {
      bonusPromotions {
        title
        category
        products {
          id
          title
          brand
          category
          priceV2 {
            now { amount }
            was { amount }
            discount { description }
          }
        }
      }
    }
    """
    
    try:
        response = requests.post(f"{BASE_URL}/graphql", json={"query": query}, headers=auth_headers)
        response.raise_for_status()
        
        data = response.json()
        if 'errors' in data:
            print("GraphQL Errors (Bonus):", data['errors'])
            return []
            
        return data.get('data', {}).get('bonusPromotions', [])
    except Exception as e:
        print(f"Error fetching bonus: {e}")
        return []

def fetch_product_images(token, product_ids):
    """Batch fetch product details to get image URLs"""
    if not product_ids:
        return {}
    
    # API limit is typically 100 per request
    image_map = {}
    batch_size = 100
    
    for i in range(0, len(product_ids), batch_size):
        batch = product_ids[i:i+batch_size]
        params = '&'.join([f'ids={pid}' for pid in batch])
        url = f"{BASE_URL}/mobile-services/product/search/v2/products?{params}&sortOn=INPUT_PRODUCT_IDS"
        
        headers = HEADERS.copy()
        headers["Authorization"] = f"Bearer {token}"
        
        try:
            response = requests.get(url, headers=headers)
            print(f"Image fetch status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"Response type: {type(data)}, keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
                
                # Handle both dict and direct list responses
                if isinstance(data, dict):
                    products = data.get('products', [])
                elif isinstance(data, list):
                    products = data
                else:
                    print(f"Unexpected response type: {type(data)}")
                    continue
                    
                print(f"Found {len(products)} products with images")
                for product in products:
                    pid = product.get('webshopId')
                    images = product.get('images', [])
                    if images and pid:
                        # Get 200x200 image
                        img_url = None
                        for img in images:
                            if img.get('width') == 200 or img.get('width') == 400:
                                img_url = img.get('url')
                                break
                        if not img_url and images:
                            img_url = images[0].get('url')
                        image_map[pid] = img_url
        except Exception as e:
            print(f"Error fetching images batch: {e}")
            import traceback
            traceback.print_exc()
    
    return image_map

def get_merged_data(store_id=None):
    if store_id is None:
        store_id = DEFAULT_STORE_ID
        
    # Check cache (include store_id in cache key)
    cache_key = f"{store_id}"
    if cache_key in cache and time.time() - cache[cache_key]["timestamp"] < CACHE_DURATION:
        print(f"Using cached data for store {store_id}")
        return cache[cache_key]["data"]

    print(f"Fetching fresh data for store {store_id}...")
    token = get_ah_token()
    if not token:
        return {"error": "Could not authenticate"}

    # 1. Fetch Data
    bargains_raw = fetch_laatste_kans(token, store_id)
    print(f"DEBUG: Raw Bargains count: {len(bargains_raw) if bargains_raw else 0}")
    
    bonus_raw = get_bonus_promotions(token)
    print(f"DEBUG: Raw Bonus count: {len(bonus_raw) if bonus_raw else 0}")

    # 2. Process Bargains (Laatste Kans)
    bargains_list = []
    if bargains_raw:
        df_bargains = pd.json_normalize(bargains_raw)
        # Clean column names
        df_bargains.columns = [c.replace('product.', '').replace('bargainPrice.', '').replace('markdown.', '') for c in df_bargains.columns]
        
        # Ensure columns exist before processing
        required_cols = ['title', 'priceWas', 'priceNow', 'markdownPercentage']
        missing_cols = [col for col in required_cols if col not in df_bargains.columns]
        if not missing_cols:
            # Normalize title for matching
            if 'title' in df_bargains.columns:
                df_bargains['title_clean'] = df_bargains['title'].str.lower().str.strip()
            
            # Add Image URL
            if 'id' in df_bargains.columns:
                df_bargains['image_url'] = df_bargains['id'].apply(lambda x: f"https://static.ah.nl/static/product/AHI_{x}?options=200,q85" if pd.notnull(x) else None)
            
            # Ensure numeric prices first
            cols_to_numeric = ['priceWas', 'priceNow', 'markdownPercentage']
            for col in cols_to_numeric:
                if col in df_bargains.columns:
                    df_bargains[col] = pd.to_numeric(df_bargains[col], errors='coerce')
            
            # Fetch images for all bargain items
            if 'id' in df_bargains.columns:
                product_ids = df_bargains['id'].dropna().unique().tolist()
                image_map = fetch_product_images(token, product_ids)
                df_bargains['image_url'] = df_bargains['id'].apply(lambda x: image_map.get(x) if pd.notnull(x) else None)
            
            # Sanitize NaNs for JSON
            df_bargains = df_bargains.replace({np.nan: None})

            # Convert to list of dicts for frontend
            bargains_list = df_bargains.to_dict(orient='records')
            print(f"DEBUG: Processed Bargains count: {len(bargains_list)}")
        else:
            print(f"DEBUG: Missing columns in bargains data: {missing_cols}")
            print(f"DEBUG: Available columns: {df_bargains.columns.tolist()}")

    # 3. Process Bonus
    bonus_list = []
    df_bonus = pd.DataFrame()
    if bonus_raw:
        # Flatten bonus data
        df_bonus = pd.json_normalize(
            bonus_raw, 
            record_path=['products'], 
            meta=['title'], # Promo title
            meta_prefix='promo_'
        )
        print(f"DEBUG: Flattened Bonus rows: {len(df_bonus)}")
        
        mapping = {
            'id': 'id',
            'title': 'Product',
            'brand': 'Merk',
            'priceV2.now.amount': 'Prijs_Nu',
            'priceV2.was.amount': 'Prijs_Was',
            'priceV2.discount.description': 'Bonus_Tekst',
            'promo_title': 'Bonus_Groep'
        }
        
        # Rename available columns
        rename_map = {k: v for k, v in mapping.items() if k in df_bonus.columns}
        df_bonus = df_bonus.rename(columns=rename_map)
        
        if 'Product' in df_bonus.columns:
            df_bonus['Product_clean'] = df_bonus['Product'].str.lower().str.strip()
            
            # Ensure numeric prices first
            cols_to_numeric = ['Prijs_Nu', 'Prijs_Was']
            for col in cols_to_numeric:
                if col in df_bonus.columns:
                    df_bonus[col] = pd.to_numeric(df_bonus[col], errors='coerce')
            
            # Fetch images for bonus items
            if 'id' in df_bonus.columns:
                product_ids = df_bonus['id'].dropna().unique().tolist()
                image_map = fetch_product_images(token, product_ids)
                df_bonus['image_url'] = df_bonus['id'].apply(lambda x: image_map.get(x) if pd.notnull(x) else None)

            # Sanitize NaNs for JSON
            df_bonus = df_bonus.replace({np.nan: None})

            bonus_list = df_bonus.to_dict(orient='records')
        else:
             print("DEBUG: 'Product' column missing in bonus data")
             print(f"DEBUG: Bonus columns: {df_bonus.columns.tolist()}")

    # 4. Find Overlap (Double Deals)
    overlap_list = []
    if not df_bonus.empty and bargains_list:
        try:
            # We need a DataFrame for bargains to merge easily
            df_bargains_for_merge = pd.DataFrame(bargains_list)
            
            # DEBUG: Check for matching titles
            bonus_titles = set(df_bonus['Product_clean'].unique())
            bargain_titles = set(df_bargains_for_merge['title_clean'].unique())
            common = bonus_titles.intersection(bargain_titles)
            print(f"DEBUG: Found {len(common)} potential matches on title")
            
            merged = pd.merge(
                df_bonus,
                df_bargains_for_merge,
                left_on='Product_clean',
                right_on='title_clean',
                how='inner',
                suffixes=('_bonus', '_bargain') # Avoid collision on 'image_url' and 'id'
            )
            
            # Prioritize bargain image if consistent, or bonus
            if 'image_url_bonus' in merged.columns:
                merged['image_url'] = merged['image_url_bonus']
            elif 'image_url_bargain' in merged.columns:
                merged['image_url'] = merged['image_url_bargain']

            if not merged.empty:
                # Calculate correct prices for overlap items
                merged['Prijs_Nu'] = pd.to_numeric(merged['Prijs_Nu'], errors='coerce')
                merged['priceNow'] = pd.to_numeric(merged['priceNow'], errors='coerce')
                merged['Prijs_Was'] = pd.to_numeric(merged['Prijs_Was'], errors='coerce')
                merged['priceWas'] = pd.to_numeric(merged['priceWas'], errors='coerce')
                merged['markdownPercentage'] = pd.to_numeric(merged['markdownPercentage'], errors='coerce')
                
                # Use the LOWEST price (bargain is usually better)
                merged['final_price'] = merged[['Prijs_Nu', 'priceNow']].min(axis=1)
                # Use the HIGHEST original price
                merged['final_was_price'] = merged[['Prijs_Was', 'priceWas']].max(axis=1)
                # Calculate total discount percentage
                merged['total_discount_pct'] = ((merged['final_was_price'] - merged['final_price']) / merged['final_was_price'] * 100).round(0)
                
                # Calculate absolute savings in euros
                merged['savings_euro'] = merged['final_was_price'] - merged['final_price']
                
                # Create smart discount label
                def get_discount_label(row):
                    bonus_txt = row.get('Bonus_Tekst')
                    markdown_pct = row.get('markdownPercentage')
                    total_pct = row.get('total_discount_pct')
                    
                    # Check if there's a special bonus mechanism (like "1+1 gratis")
                    if pd.notna(bonus_txt) and bonus_txt and bonus_txt != 'nan':
                        # Use bonus text for special deals
                        return str(bonus_txt)
                    elif pd.notna(total_pct) and total_pct > 0:
                        # Regular percentage discount
                        return f"-{int(total_pct)}%"
                    elif pd.notna(markdown_pct) and markdown_pct > 0:
                        return f"-{int(markdown_pct)}%"
                    return ""
                
                merged['discount_label'] = merged.apply(get_discount_label, axis=1)
                
                # DEDUPLICATION: Keep only unique bargain items (fixes Arla milk duplicate issue)
                # When multiple bonus items match same bargain, keep the one with best bonus
                if 'id_bargain' in merged.columns:
                    # Sort by savings (highest first) then drop duplicates by bargain ID
                    merged = merged.sort_values('savings_euro', ascending=False)
                    merged = merged.drop_duplicates(subset=['id_bargain'], keep='first')
                    print(f"After deduplication: {len(merged)} unique overlap items")
                
                # Sanitize NaNs for JSON
                merged = merged.replace({np.nan: None})
                
                # Sort by category for frontend
                if 'categoryTitle' in merged.columns:
                    merged = merged.sort_values('categoryTitle')

                # Convert to list for frontend
                overlap_list = merged.to_dict(orient='records')
        except Exception as e:
            print(f"Error merging data: {e}")
            import traceback
            traceback.print_exc()

    # Calculate Top 3 Best Deals (highest savings in euros)
    top3 = []
    if overlap_list:
        # Sort by savings
        sorted_deals = sorted(overlap_list, key=lambda x: x.get('savings_euro', 0) or 0, reverse=True)
        top3 = sorted_deals[:3]
        top3_names = [f"{d.get('Product', d.get('title'))} (€{d.get('savings_euro', 0):.2f})" for d in top3]
        print(f"Top 3 deals: {top3_names}")

    result = {
        "bargains": bargains_list,
        "bonus": bonus_list[:100],
        "overlap": overlap_list,
        "top3": top3
    }
    
    # Update cache with store_id key
    cache[cache_key] = {
        "data": result,
        "timestamp": time.time()
    }
    
    return result

@app.route('/')
def home():
    return render_template('dashboard.html')

@app.route('/api/data')
def data():
    from flask import request
    store_id = request.args.get('store_id', DEFAULT_STORE_ID)
    return jsonify(get_merged_data(store_id))

if __name__ == '__main__':
    print("Starting Appie Dashboard on http://localhost:5000")
    app.run(debug=True, port=5000)
