import requests
import os
import json
from datetime import datetime

# Bundle-Konfiguration basierend auf deiner Tabelle
BUNDLE_CONFIG = {
    'NEUBUN1': [
        {'sku': 'PN003', 'quantity': 1},
        {'sku': 'PN002', 'quantity': 1}
    ],
    'NEUBUN2': [
        {'sku': 'PN003', 'quantity': 1},
        {'sku': 'PN008', 'quantity': 1}
    ],
    'PN009': [
        {'sku': 'PN002', 'quantity': 2}
    ],
    'PN010': [
        {'sku': 'PN002', 'quantity': 3}
    ],
    'PN011': [
        {'sku': 'PN004', 'quantity': 2}
    ],
    'PN012': [
        {'sku': 'PN004', 'quantity': 3}
    ],
    'PN013': [
        {'sku': 'PN006', 'quantity': 2}
    ],
    'PN014': [
        {'sku': 'PN006', 'quantity': 3}
    ],
    'PN015': [
        {'sku': 'PN008', 'quantity': 2}
    ],
    'PN016': [
        {'sku': 'PN008', 'quantity': 3}
    ]
}

def setup_api():
    """API Setup"""
    shop_url = os.environ['SHOPIFY_SHOP_URL']
    api_token = os.environ['SHOPIFY_API_TOKEN']
    
    base_url = f"https://{shop_url}/admin/api/2023-10"
    headers = {
        'X-Shopify-Access-Token': api_token,
        'Content-Type': 'application/json'
    }
    
    return base_url, headers

def get_location_id_by_name(base_url, headers, location_name):
    """Location ID anhand des Namens finden"""
    try:
        response = requests.get(f"{base_url}/locations.json", headers=headers)
        response.raise_for_status()
        
        locations = response.json()['locations']
        for location in locations:
            if location['name'] == location_name:
                return location['id']
        
        print(f"⚠️  Lager '{location_name}' nicht gefunden!")
        print(f"Verfügbare Lager: {[loc['name'] for loc in locations]}")
        return None
        
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Lager: {e}")
        return None

def get_all_products(base_url, headers):
    """Alle Produkte mit Varianten laden"""
    try:
        all_products = []
        url = f"{base_url}/products.json?limit=250"
        
        while url:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            all_products.extend(data['products'])
            
            # Pagination
            link_header = response.headers.get('Link', '')
            if 'rel="next"' in link_header:
                # Extract next URL from Link header
                next_url = None
                for link in link_header.split(','):
                    if 'rel="next"' in link:
                        next_url = link.split('<')[1].split('>')[0]
                        break
                url = next_url
            else:
                url = None
        
        return all_products
        
    except Exception as e:
        print(f"❌ Fehler beim Laden der Produkte: {e}")
        return []

def find_variant_by_sku(products, sku):
    """Variante anhand SKU finden"""
    for product in products:
        for variant in product['variants']:
            if variant['sku'] == sku:
                return variant
    return None

def get_inventory_quantity(base_url, headers, inventory_item_id, location_id):
    """Bestand einer Variante für ein bestimmtes Lager holen"""
    try:
        url = f"{base_url}/inventory_levels.json?inventory_item_ids={inventory_item_id}&location_ids={location_id}"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        levels = response.json()['inventory_levels']
        if levels:
            return levels[0]['available'] or 0
        return 0
        
    except Exception as e:
        print(f"⚠️  Fehler beim Abrufen des Bestands: {e}")
        return 0

def update_inventory_quantity(base_url, headers, inventory_item_id, location_id, new_quantity, sku):
    """Bestand einer Variante für ein bestimmtes Lager aktualisieren"""
    try:
        # Aktuellen Bestand holen
        current_qty = get_inventory_quantity(base_url, headers, inventory_item_id, location_id)
        adjustment = new_quantity - current_qty
        
        if adjustment == 0:
            print(f"✓ {sku}: Bestand unverändert ({new_quantity}) [Versandmanufaktur]")
            return True
        
        # Inventory Level anpassen
        data = {
            "location_id": location_id,
            "inventory_item_id": inventory_item_id,
            "available_adjustment": adjustment
        }
        
        response = requests.post(f"{base_url}/inventory_levels/adjust.json", 
                               headers=headers, json=data)
        response.raise_for_status()
        
        print(f"✓ {sku}: {current_qty} → {new_quantity} (Δ{adjustment:+d}) [Versandmanufaktur]")
        return True
        
    except Exception as e:
        print(f"✗ Fehler beim Update von {sku}: {e}")
        return False

def calculate_bundle_stock(products, base_url, headers, bundle_sku, components, location_id):
    """Berechnet verfügbaren Bundle-Bestand basierend auf Komponenten"""
    min_possible = float('inf')
    
    print(f"\n📦 Berechne {bundle_sku} [Versandmanufaktur]:")
    
    for component in components:
        component_sku = component['sku']
        needed_qty = component['quantity']
        
        # Hole Variante der Komponente
        variant = find_variant_by_sku(products, component_sku)
        if not variant:
            print(f"  ⚠️  Komponente {component_sku} nicht gefunden!")
            return 0
            
        current_stock = get_inventory_quantity(base_url, headers, variant['inventory_item_id'], location_id)
        possible_bundles = current_stock // needed_qty
        
        print(f"  • {component_sku}: {current_stock} verfügbar, {needed_qty} benötigt → {possible_bundles} Bundles möglich")
        
        min_possible = min(min_possible, possible_bundles)
    
    result = int(min_possible) if min_possible != float('inf') else 0
    print(f"  → Bundle {bundle_sku}: {result} Stück verfügbar")
    return result

def main():
    """Hauptfunktion"""
    print(f"🚀 Bundle Inventory Update gestartet - {datetime.now()}")
    
    try:
        base_url, headers = setup_api()
        
        # Test API-Verbindung
        print("🔍 Teste API-Verbindung...")
        test_response = requests.get(f"{base_url}/shop.json", headers=headers)
        test_response.raise_for_status()
        shop_data = test_response.json()['shop']
        print(f"✓ Verbunden mit Shop: {shop_data['name']}")
        
        # Hole Location ID für "Versandmanufaktur"
        location_id = get_location_id_by_name(base_url, headers, "Versandmanufaktur")
        if not location_id:
            print("❌ Lager 'Versandmanufaktur' nicht gefunden! Abbruch.")
            return
        
        print(f"📍 Verwende Lager: Versandmanufaktur (ID: {location_id})")
        
        # Lade alle Produkte
        print("📦 Lade alle Produkte...")
        products = get_all_products(base_url, headers)
        print(f"✓ {len(products)} Produkte geladen")
        
        updated_bundles = 0
        
        for bundle_sku, components in BUNDLE_CONFIG.items():
            # Berechne verfügbaren Bestand für Bundle
            available_qty = calculate_bundle_stock(products, base_url, headers, bundle_sku, components, location_id)
            
            # Hole Bundle-Variante
            bundle_variant = find_variant_by_sku(products, bundle_sku)
            if not bundle_variant:
                print(f"⚠️  Bundle {bundle_sku} nicht in Shopify gefunden!")
                continue
            
            # Aktueller Bundle-Bestand im Versandmanufaktur-Lager
            current_bundle_stock = get_inventory_quantity(base_url, headers, bundle_variant['inventory_item_id'], location_id)
            
            # Update nur wenn sich was geändert hat
            if current_bundle_stock != available_qty:
                if update_inventory_quantity(base_url, headers, bundle_variant['inventory_item_id'], 
                                           location_id, available_qty, bundle_sku):
                    updated_bundles += 1
            else:
                print(f"✓ {bundle_sku}: Bestand unverändert ({available_qty}) [Versandmanufaktur]")
        
        print(f"\n✅ Fertig! {updated_bundles} Bundles aktualisiert")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
