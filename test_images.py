import requests

ids = ["4169", "565684"]

patterns = [
    "https://static.ah.nl/static/product/AHI_{id}",
    "https://static.ah.nl/static/product/AHI_{id}?options=200,q85",
    "https://static.ah.nl/dam/product/AHI_{id}",
    "https://static.ah.nl/dam/product/AHI_{id}?revLabel=1&rendition=200x200_JPG_Q85&fileType=binary",
    # Zero padding?
    "https://static.ah.nl/static/product/AHI_{id:0>6}",
    "https://static.ah.nl/dam/product/AHI_{id:0>6}?revLabel=1&rendition=200x200_JPG_Q85&fileType=binary"
]

print("Testing Image URLs...")

for pid in ids:
    print(f"\n--- Testing ID {pid} ---")
    for pattern in patterns:
        try:
            # handle padding manually in f-string if needed
            if ":0>6" in pattern:
                url = pattern.replace("{id:0>6}", pid.zfill(6))
            else:
                url = pattern.replace("{id}", pid)
                
            res = requests.head(url)
            print(f"[{res.status_code}] {url}")
        except Exception as e:
            print(f"[ERR] {url} - {e}")
