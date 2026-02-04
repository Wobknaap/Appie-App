import dashboard
import pandas as pd

print("=== ARLA MELK DEBUG ===\n")

token = dashboard.get_ah_token()
if not token:
    print("No token!")
    exit()

# Fetch data
bargains = dashboard.fetch_laatste_kans(token, "1558")
bonus = dashboard.get_bonus_promotions(token)

# Process bargains
df_bargains = pd.json_normalize(bargains)
df_bargains.columns = [c.replace('product.', '').replace('bargainPrice.', '').replace('markdown.', '') for c in df_bargains.columns]
if 'title' in df_bargains.columns:
    df_bargains['title_clean'] = df_bargains['title'].str.lower().str.strip()

# Process bonus
df_bonus = pd.json_normalize(bonus, record_path=['products'], meta=['title'], meta_prefix='promo_')
mapping = {
    'id': 'id',
    'title': 'Product',
    'brand': 'Merk',
    'priceV2.now.amount': 'Prijs_Nu',
    'priceV2.was.amount': 'Prijs_Was',
    'salesUnitSize': 'Unit',
    'priceV2.discount.description': 'Bonus_Tekst',
}
rename_map = {k: v for k, v in mapping.items() if k in df_bonus.columns}
df_bonus = df_bonus.rename(columns=rename_map)
if 'Product' in df_bonus.columns:
    df_bonus['Product_clean'] = df_bonus['Product'].str.lower().str.strip()

# Merge to find overlaps
merged = pd.merge(
    df_bonus,
    df_bargains,
    left_on='Product_clean',
    right_on='title_clean',
    how='inner',
    suffixes=('_bonus', '_bargain')
)

# Filter for Arla
arla_items = merged[merged['Product'].str.contains('Arla', case=False, na=False)]

if len(arla_items) > 0:
    print(f"Found {len(arla_items)} Arla items in overlap:\n")
    
    for idx, row in arla_items.iterrows():
        print(f"--- Item {idx+1} ---")
        print(f"Title: {row['Product']}")
        print(f"ID (bonus): {row.get('id_bonus', 'N/A')}")
        print(f"ID (bargain): {row.get('id_bargain', 'N/A')}")  
        print(f"Unit (bonus): {row.get('Unit', 'N/A')}")
        print(f"Unit (bargain): {row.get('salesUnitSize', 'N/A')}")
        print(f"Bonus Prijs Nu: €{row.get('Prijs_Nu', 0)}")
        print(f"Bonus Prijs Was: €{row.get('Prijs_Was', 0)}")
        print(f"Bargain Prijs Nu: €{row.get('priceNow', 0)}")
        print(f"Bargain Prijs Was: €{row.get('priceWas', 0)}")
        print(f"Bonus Tekst: {row.get('Bonus_Tekst', 'N/A')}")
        print(f"Markdown %: {row.get('markdownPercentage', 'N/A')}%")
        print()
else:
    print("No Arla items found in overlap.")
    print("\nChecking bonus only...")
    arla_bonus = df_bonus[df_bonus['Product'].str.contains('Arla', case=False, na=False)]
    print(f"Arla in bonus: {len(arla_bonus)}")
    if len(arla_bonus) > 0:
        print(arla_bonus[['Product', 'Prijs_Nu', 'Prijs_Was', 'Unit', 'Bonus_Tekst']].to_string())
