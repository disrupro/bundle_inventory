import shopify
import os

def test_shopify_connection():
    """Minimaler Test der Shopify-Verbindung"""
    try:
        shop_url = os.environ['SHOPIFY_SHOP_URL']
        api_token = os.environ['SHOPIFY_API_TOKEN']
        
        print(f"Shop URL: {shop_url}")
        print(f"API Token: {api_token[:10]}...")
        
        # Verschiedene API-Versionen testen
        for version in ["2024-01", "2023-10", "2023-07"]:
            print(f"\n--- Testing API Version {version} ---")
            
            try:
                shopify.ShopifyResource.set_site(f"https://{api_token}@{shop_url}/admin/api/{version}")
                
                # Einfacher Shop-Test
                shop = shopify.Shop.current()
                print(f"✓ Shop gefunden: {shop.name}")
                
                # Locations-Test
                locations = shopify.Location.find()
                print(f"✓ {len(locations)} Locations gefunden:")
                for loc in locations:
                    print(f"  - {loc.name} (ID: {loc.id})")
                
                # Erfolgreich - aufhören
                return version
                
            except Exception as e:
                print(f"✗ Fehler mit {version}: {e}")
        
        print("\n❌ Keine API-Version funktioniert!")
        return None
        
    except Exception as e:
        print(f"❌ Grundlegender Fehler: {e}")
        return None

if __name__ == "__main__":
    test_shopify_connection()
