import requests
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

try:
    print("Fetching data...")
    res = requests.get('http://localhost:5000/api/data')
    print(f"Status: {res.status_code}")
    
    data = res.json()
    print("JSON parse OK")
    
    # Check types
    if data['bargains']:
        item = data['bargains'][0]
        p_now = item.get('priceNow')
        p_was = item.get('priceWas')
        print(f"Sample Bargain: {item.get('title')}")
        print(f" - priceNow type: {type(p_now)} Value: {p_now}")
        print(f" - priceWas type: {type(p_was)} Value: {p_was}")
        
        if not isinstance(p_now, (int, float, type(None))):
             print("❌ WARNING: priceNow is not a number!")
        else:
             print("✅ priceNow is numeric")
             
    if data['overlap']:
        print(f"✅ Overlap count: {len(data['overlap'])}")
    else:
        print("⚠️ No overlap found (might be correct, but worth noting)")

except Exception as e:
    print(f"❌ Error: {e}")
