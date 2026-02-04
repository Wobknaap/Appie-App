import requests
import dashboard
import pandas as pd

# 1. Image Check
print("--- 1. IMAGE CHECK ---")
test_id = 4169 # Champignons (from previous debug)
url = f"https://static.ah.nl/static/product/AHI_{test_id}?options=200,q85"
try:
    print(f"Testing: {url}")
    res = requests.head(url, allow_redirects=True)
    print(f"Final Status: {res.status_code}")
    print(f"Final URL: {res.url}")
    print(f"Content-Type: {res.headers.get('Content-Type')}")
except Exception as e:
    print(f"Error: {e}")

# 2. Price Check (Mocking the merge logic)
print("\n--- 2. PRICE CHECK (OVERLAP) ---")
token = dashboard.get_ah_token()
if token:
    bargains = dashboard.fetch_laatste_kans(token, dashboard.STORE_ID)
    bonus = dashboard.get_bonus_promotions(token)
    
    if bargains and bonus:
        df_bargains = pd.json_normalize(bargains)
        df_bargains.columns = [c.replace('product.', '').replace('bargainPrice.', '').replace('markdown.', '') for c in df_bargains.columns]
        if 'title' in df_bargains.columns:
             df_bargains['title_clean'] = df_bargains['title'].str.lower().str.strip()
        
        df_bonus = pd.json_normalize(bonus, record_path=['products'], meta=['title'], meta_prefix='promo_')
        # Map bonus columns
        mapping = {
            'title': 'Product',
            'priceV2.now.amount': 'Prijs_Nu', # Bonus Price
            'priceV2.was.amount': 'Prijs_Was', # Original Price
        }
        rename_map = {k: v for k, v in mapping.items() if k in df_bonus.columns}
        df_bonus = df_bonus.rename(columns=rename_map)
        if 'Product' in df_bonus.columns:
            df_bonus['Product_clean'] = df_bonus['Product'].str.lower().str.strip()

        # Merge
        merged = pd.merge(
            df_bonus,
            df_bargains,
            left_on='Product_clean',
            right_on='title_clean',
            how='inner',
            suffixes=('_bonus', '_bargain')
        )
        
        if not merged.empty:
            print(f"Found {len(merged)} overlaps.")
            row = merged.iloc[0]
            print(f"Sample: {row['Product']}")
            print(f" - Bonus Price (Prijs_Nu): {row.get('Prijs_Nu')}")
            print(f" - Original Price (Prijs_Was): {row.get('Prijs_Was')}")
            print(f" - Bargain Price (priceNow): {row.get('priceNow')}")
            print(f" - Bargain Was (priceWas): {row.get('priceWas')}")
            print(f" - Markdown Pct: {row.get('markdownPercentage')}")
            
            # Check logic
            try:
                p_bonus = float(row.get('Prijs_Nu') or 0)
                p_bargain = float(row.get('priceNow') or 0)
                print(f" -> Which is lower? Bonus={p_bonus} vs Bargain={p_bargain}")
            except:
                pass
    else:
        print("No data fetched.")
