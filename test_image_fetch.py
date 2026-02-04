import requests
import dashboard

print("Testing batch image fetch...")
token = dashboard.get_ah_token()

if token:
    # Test with a few known IDs
    test_ids = [4169, 565684, 415761]
    
    print(f"Fetching images for IDs: {test_ids}")
    image_map = dashboard.fetch_product_images(token, test_ids)
    
    print(f"\nResults ({len(image_map)} images found):")
    for pid, url in image_map.items():
        print(f"  {pid}: {url[:80]}..." if url else f"  {pid}: None")
else:
    print("Failed to get token")
