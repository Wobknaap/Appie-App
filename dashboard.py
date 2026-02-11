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

# --- KONIJNENVOER & VLEES CONFIG ---
MEAL_KIT_KEYWORDS = ['verspakket', 'maaltijdpakket', 'curry pakket', 'lasagne pakket', 'soeppo', 'soep pakket']
NEGATIVE_KEYWORDS = [
    'salade', 'maaltijdsalade', 'broodje', 'hapje', 'snack', 'soep', 'pizza', 'loempia', 'bapao',
    'roti', 'nasi', 'bami', 'mihoen', 'quiche', 'oven', 'magnetron', 'kant-en-klaar', 'stoom', 
    'maaltijd', 'menu', 'schotel', 'wrap', 'sandwich', 'burger', 'kipschnitzel', 'cordon'
]

# Logic: If Meal Kit title contains KEY, look for matches in CATEGORY or KEYWORD
MATCHING_RULES = {
    'lasagne': {'keywords': ['gehakt', 'vega gehakt'], 'category': 'Vlees, kip, vis, vega'},
    'curry': {'keywords': ['kipfilet', 'kipdij', 'kipstukjes', 'tofu', 'vega stukjes'], 'category': 'Vlees, kip, vis, vega'},
    'madras': {'keywords': ['kipfilet', 'kipdij', 'kipstukjes', 'tofu'], 'category': 'Vlees, kip, vis, vega'},
    'tandoori': {'keywords': ['kipfilet', 'kipdij', 'kipstukjes'], 'category': 'Vlees, kip, vis, vega'},
    'soep': {'keywords': ['soepgroente', 'gehaktballetjes', 'stokbrood'], 'category': 'Groente'},
    'pasta': {'keywords': ['gehakt', 'spekjes', 'kaas'], 'category': 'Vlees, kip, vis, vega'},
    'risotto': {'keywords': ['paddenstoelen', 'kipfilet', 'kipdij', 'zalm'], 'category': 'Vlees, kip, vis, vega'},
    'stamppot': {'keywords': ['rookworst', 'spekjes', 'gehaktbal'], 'category': 'Vlees, kip, vis, vega'},
    'chili': {'keywords': ['gehakt', 'vega gehakt'], 'category': 'Vlees, kip, vis, vega'},
    'wraps': {'keywords': ['kipfilet', 'kipdij', 'gehakt', 'vega reepjes'], 'category': 'Vlees, kip, vis, vega'},
    'burrito': {'keywords': ['gehakt', 'kipfilet', 'kipdij', 'kipstukjes', 'bonen'], 'category': 'Vlees, kip, vis, vega'}
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

    # 4. Find Overlap (Double Deals) & Ultimate Stacking
    overlap_list = []
    ultimate_stacks = []
    
    if not df_bonus.empty and bargains_list:
        try:
            # We need a DataFrame for bargains to merge easily
            df_bargains_for_merge = pd.DataFrame(bargains_list)
            
            merged = pd.merge(
                df_bonus,
                df_bargains_for_merge,
                left_on='Product_clean',
                right_on='title_clean',
                how='inner',
                suffixes=('_bonus', '_bargain')
            )
            
            # Prioritize bargain image
            if 'image_url_bonus' in merged.columns:
                merged['image_url'] = merged['image_url_bonus']
            elif 'image_url_bargain' in merged.columns:
                merged['image_url'] = merged['image_url_bargain']

            if not merged.empty:
                # Numeric conversions
                for col in ['Prijs_Nu', 'priceNow', 'Prijs_Was', 'priceWas', 'markdownPercentage']:
                    if col in merged.columns:
                        merged[col] = pd.to_numeric(merged[col], errors='coerce')
                
                # Calculations
                merged['final_price'] = merged[['Prijs_Nu', 'priceNow']].min(axis=1)
                merged['final_was_price'] = merged[['Prijs_Was', 'priceWas']].max(axis=1)
                merged['total_discount_pct'] = ((merged['final_was_price'] - merged['final_price']) / merged['final_was_price'] * 100).round(0)
                merged['savings_euro'] = merged['final_was_price'] - merged['final_price']
                
                # --- ULTIMATE STACKING LOGIC ---
                def get_stack_info(row):
                    stock = row.get('stock')
                    bonus = str(row.get('Bonus_Tekst', '')).lower()
                    
                    if not stock or not isinstance(stock, (int, float)) or stock <= 0:
                        return None
                        
                    required = 0
                    stack_type = ""
                    
                    if '1+1' in bonus:
                        required = 2
                        stack_type = "1 + 1 Gratis"
                    elif '2+1' in bonus:
                        required = 3
                        stack_type = "2 + 1 Gratis"
                    elif '2+2' in bonus:
                        required = 4
                        stack_type = "2 + 2 Gratis"
                    elif '2e gratis' in bonus:
                        required = 2
                        stack_type = "2e Gratis"
                    elif '2e halve' in bonus:
                        required = 2
                        stack_type = "2e Halve Prijs"
                    elif '2 voor' in bonus:
                        required = 2
                        stack_type = "2 voor..."
                    
                    if required > 0 and stock >= required:
                        sets = int(stock // required)
                        total_items = sets * required
                        
                        # Calculate Bundle Price Logic
                        # User Logic: Apply Markdown % ON TOP of the Bonus Bundle Price.
                        
                        # We calculate for ONE set (the minimum required), not total stock.
                        effective_quantity = required 
                        
                        # Base Bundle Price (if it were just the bonus)
                        base_bundle_price = 0
                        
                        # Regex to parse "2 voor 2.49" or "2 voor € 2.49"
                        import re
                        # Pattern matches: "2 voor" followed by price. Price might use comma or dot.
                        # We expect stack_type to match "2 voor..." derived from bonus parsing earlier if implicit, 
                        # but scanning the original 'bonus' text is safer.
                        match_voor = re.search(r'(\d+)\s+voor\s+(?:€|&euro;)?\s*(\d+[,.]\d{2})', bonus)
                        
                        if match_voor:
                             # We found an explicit "X voor Y" price in text! Use it!
                             # e.g. "2 voor 2.49" -> qty=2, price=2.49
                             try:
                                 qty_in_deal = int(match_voor.group(1))
                                 price_in_deal = float(match_voor.group(2).replace(',', '.'))
                                 
                                 # If our effective_quantity (required) matches the deal quantity, use the price directly.
                                 if qty_in_deal == effective_quantity:
                                     base_bundle_price = price_in_deal
                                 else:
                                     # Scale it? e.g. deal is 2 for 4, we generally shouldn't be here if required!=2
                                     base_bundle_price = price_in_deal * (effective_quantity / qty_in_deal)
                             except:
                                 base_bundle_price = 0 # Fallback
                        
                        if base_bundle_price == 0:
                            # Fallback logic if regex missed or text is different (e.g. 1+1 gratis)
                            if '1+1' in stack_type:
                                base_bundle_price = (row['final_was_price'] * effective_quantity) * 0.5
                            elif '2+1' in stack_type:
                                base_bundle_price = (row['final_was_price'] * effective_quantity) * (2/3)
                            elif '2+2' in stack_type:
                                base_bundle_price = (row['final_was_price'] * effective_quantity) * 0.5
                            elif '2e gratis' in stack_type: 
                                 base_bundle_price = (row['final_was_price'] * effective_quantity) * 0.5
                            elif '2e halve' in stack_type:
                                 base_bundle_price = (row['final_was_price'] * effective_quantity) * 0.75
                            else:
                                 # Try to use 'Prijs_Nu' if available as the bonus unit price
                                 if pd.notna(row.get('Prijs_Nu')):
                                    base_bundle_price = row['Prijs_Nu'] * effective_quantity
                                 else:
                                    base_bundle_price = row['final_was_price'] * effective_quantity

                        # Apply Markdown Percentage if available
                        markdown_pct = row.get('markdownPercentage', 0)
                        
                        # If markdown exists, User says: Bonus Price * (1 - Markdown)
                        final_bundle_price = base_bundle_price
                        if markdown_pct and markdown_pct > 0:
                             final_bundle_price = base_bundle_price * (1 - (markdown_pct / 100))
                        
                        original_price = row['final_was_price'] * effective_quantity
                        bundle_savings = original_price - final_bundle_price
                        
                        # Total available sets
                        sets_available = int(stock // required)

                        return {
                            'is_stack': True,
                            'required': required,
                            'sets_available': sets_available,
                            'total_items': effective_quantity,
                            'stack_type': stack_type,
                            'bundle_price': round(final_bundle_price, 2),
                            'bundle_savings': round(bundle_savings, 2),
                            'message': f"Stack {effective_quantity} stuks voor €{final_bundle_price:.2f}! (Normaal €{original_price:.2f})"
                        }
                    return None

                # Discount labels logic
                def get_discount_labels(row):
                    labels = []
                    bonus_txt = row.get('Bonus_Tekst')
                    markdown_pct = row.get('markdownPercentage')
                    total_pct = row.get('total_discount_pct')
                    
                    if pd.notna(bonus_txt) and bonus_txt and str(bonus_txt).lower() != 'nan':
                        labels.append({'text': str(bonus_txt), 'type': 'bonus'})
                    
                    if pd.notna(markdown_pct) and markdown_pct > 0:
                        labels.append({'text': f"-{int(markdown_pct)}%", 'type': 'markdown'})
                    
                    if not labels and pd.notna(total_pct) and total_pct > 0:
                        labels.append({'text': f"-{int(total_pct)}%", 'type': 'markdown'})
                        
                    return labels
                
                merged['discount_labels'] = merged.apply(get_discount_labels, axis=1)
                merged['stack_info'] = merged.apply(get_stack_info, axis=1)
                
                # Deduplication
                if 'id_bargain' in merged.columns:
                    merged = merged.sort_values('savings_euro', ascending=False)
                    merged = merged.drop_duplicates(subset=['id_bargain'], keep='first')
                
                # Sanitize
                merged = merged.replace({np.nan: None})
                
                # Sort by category
                if 'categoryTitle' in merged.columns:
                    merged = merged.sort_values('categoryTitle')

                overlap_list = merged.to_dict(orient='records')
                
                # Filter for Ultimate Stacks
                ultimate_stacks = [item for item in overlap_list if item.get('stack_info')]
                
                # Create Ranked List (All overlap items sorted by discount %)
                ranked_list = sorted(overlap_list, key=lambda x: x.get('total_discount_pct', 0) or 0, reverse=True)


        except Exception as e:
            print(f"Error merging data: {e}")
            import traceback
            traceback.print_exc()

    # 5. Process Verspakketten & Smart Matching
    meal_kits = []
    
    # helper to find items in list matching keywords
    def find_matches_in_list(source_list, keywords, category_filter=None):
        matches = []
        for item in source_list:
            title = str(item.get('Product') or item.get('title') or '').lower()
            cat = str(item.get('Categorie') or item.get('categoryTitle') or '').lower()
            
            # 1. Negative Keyword Check
            if any(bad in title for bad in NEGATIVE_KEYWORDS):
                continue

            # 2. Category Check (if provided)
            # This is loose matching: input 'Vlees' matches 'Vlees, kip, vis...'
            if category_filter:
                # We split valid categories by comma if multiple are allowed or just check containment
                # Simple containment check:
                if category_filter.lower() not in cat and cat not in category_filter.lower():
                     # Fallback: sometimes categories are vague. If keyword is strongly matched, maybe allow?
                     # For now: strict.
                     continue

            # 3. Positive Keyword Check
            # We want WHOLE WORD match for short words like 'kip' to avoid 'kipkerrie' or 'kippie'
            # But simple substring is easier. Let's try to be smart.
            for k in keywords:
                 if k in title:
                     matches.append(item)
                     break # Found one keyword match, good enough
                
        return matches

    all_deals = overlap_list + bargains_list + bonus_list
    
    # Identify meal kits from all deals
    for item in all_deals:
        title = str(item.get('Product') or item.get('title') or '').lower()
        if any(mk in title for mk in MEAL_KIT_KEYWORDS):
            # Avoid duplicates if item is in multiple lists (overlap vs bargains)
            # Use 'id' or 'webshopId' if available, otherwise title
            item_id = item.get('id') or item.get('Product')
            if not any((m.get('id') or m.get('Product')) == item_id for m in meal_kits):
                
                # Copy item to avoid mutating original list references
                kit_item = item.copy()
                
                # --- SMART MATCHING LOGIC ---
                kit_item['smart_match'] = None
                
                # Clean title for rule lookup
                clean_title = title.lower()
                
                required_ingredients = []
                target_category = None
                
                for rule_key, rules in MATCHING_RULES.items():
                    if rule_key in clean_title:
                        required_ingredients.extend(rules['keywords'])
                        target_category = rules.get('category')
                        break # Stop after first rule match to avoid mixing logic
                
                if required_ingredients:
                    # Look for discounted matches in all deals
                    possible_matches = find_matches_in_list(all_deals, required_ingredients, category_filter=target_category)
                    
                    # Sort matches by savings or relevance
                    if possible_matches:
                        # Pick the best match (e.g. highest discount or overlap item)
                        # Prefer overlap items first
                        best_match = next((m for m in possible_matches if m in overlap_list), None)
                        if not best_match:
                             best_match = possible_matches[0]
                        
                        # --- PRICE FIX LOGIC ---
                        # Ensure 'final_price' is set properly for the Frontend
                        # Bonus items might have Prijs_Nu, Bargains priceNow.
                        match_price = best_match.get('final_price') or best_match.get('priceNow') or best_match.get('Prijs_Nu')
                        # If price is still 0/None, try Prijs_Was or priceWas (better than 0)
                        if match_price is None or match_price == 0:
                             match_price = best_match.get('final_was_price') or best_match.get('priceWas') or best_match.get('Prijs_Was')
                        
                        # Store sanitized price back on the match object
                        best_match['final_price'] = match_price
                             
                        kit_item['smart_match'] = best_match
                        kit_item['match_message'] = f"Lekker met: {best_match.get('Product') or best_match.get('title')}"

                meal_kits.append(kit_item)

    # Calculate Top 3 Best Deals
    top3 = []
    if overlap_list:
        sorted_deals = sorted(overlap_list, key=lambda x: x.get('savings_euro', 0) or 0, reverse=True)
        top3 = sorted_deals[:3]

    result = {
        "bargains": bargains_list,
        "bonus": bonus_list,
        "overlap": overlap_list,
        "ultimate_stacks": ultimate_stacks,
        "meal_kits": meal_kits,
        "ranked_list": ranked_list if 'ranked_list' in locals() else [],
        "top3": top3,
        "store_id": store_id
    }
    
    # Update cache with store_id key BEFORE returning
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
