import shopify
import json
import os
from datetime import datetime

# Bundle-Konfiguration basierend auf deiner Tabelle
BUNDLE_CONFIG = {
    'NEUBUN1': [
        {'sku': 'PN003', 'quantity': 1}
    ],
    'NEUBUN1': [  # NEUBUN1 hat zwei Komponenten
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

def setup_shopify():
    """Shopify API Setup"""
    shop_url = os.environ['SHOPIFY_SHOP_URL']  # z.B. "dein-shop.myshopify.com"
    api_token = os.environ['SHOPIFY_API_TOKEN']
    api_version = "2023-10"
    
    shopify.ShopifyResource.set_site(f"https://{api_token}@{shop_url}/admin/api/{api_version}")

def get_product_by_sku(sku):
    """Produkt anhand der SKU finden"""
    products = shopify.Product.find(limit=250)
    
    for product in products:
        for variant in product.variants:
            if variant.sku == sku:
                return product, variant
    return None, None

def get_location_id_by_name(location_name):
    """Location ID anhand des Namens finden"""
    try:
        locations = shopify.Location.find()
        for location in locations:
            if location.name == location_name:
                return location.id
        print(f"⚠️  Lager '{location_name}' nicht gefunden!")
        return None
    except Exception as e:
        print(f"❌ Fehler beim Abrufen der Lager: {e}")
        return None

def get_inventory_quantity(variant_id, location_id):
    """Bestand einer Variante für ein bestimmtes Lager holen"""
    try:
        inventory_levels = shopify.InventoryLevel.find(
            inventory_item_ids=variant_id,
            location_ids=location_id
        )
        if inventory_levels:
            return inventory_levels[0].available or 0
        return 0
    except Exception as e:
        print(f"⚠️  Fehler beim Abrufen des Bestands: {e}")
        return 0

def update_inventory_quantity(variant, new_quantity, location_id):
    """Bestand einer Variante für ein bestimmtes Lager aktualisieren"""
    try:
        # Hole aktuellen Bestand für das spezifische Lager
        inventory_levels = shopify.InventoryLevel.find(
            inventory_item_ids=variant.inventory_item_id,
            location_ids=location_id
        )
        
        if not inventory_levels:
            print(f"⚠️  Kein Inventory Level für {variant.sku} in Versandmanufaktur gefunden")
            return False
            
        level = inventory_levels[0]
        current_qty = level.available or 0
        adjustment = new_quantity - current_qty
        
        if adjustment != 0:
            # Erstelle Inventory Adjustment für das spezifische Lager
            adjustment_data = {
                "inventory_item_id": variant.inventory_item_id,
                "location_id": location_id,
                "available_adjustment": adjustment
            }
            
            shopify.InventoryLevel.adjust(adjustment_data)
            print(f"✓ {variant.sku}: {current_qty} → {new_quantity} (Δ{adjustment:+d}) [Versandmanufaktur]")
        else:
            print(f"✓ {variant.sku}: Bestand unverändert ({new_quantity}) [Versandmanufaktur]")
            
        return True
    except Exception as e:
        print(f"✗ Fehler beim Update von {variant.sku}: {e}")
        return False

def calculate_bundle_stock(bundle_sku, components, location_id):
    """Berechnet verfügbaren Bundle-Bestand basierend auf Komponenten"""
    min_possible = float('inf')
    
    print(f"\n📦 Berechne {bundle_sku} [Versandmanufaktur]:")
    
    for component in components:
        component_sku = component['sku']
        needed_qty = component['quantity']
        
        # Hole Bestand der Komponente
        product, variant = get_product_by_sku(component_sku)
        if not variant:
            print(f"  ⚠️  Komponente {component_sku} nicht gefunden!")
            return 0
            
        current_stock = get_inventory_quantity(variant.inventory_item_id, location_id)
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
        setup_shopify()
        
        # Hole Location ID für "Versandmanufaktur"
        location_id = get_location_id_by_name("Versandmanufaktur")
        if not location_id:
            print("❌ Lager 'Versandmanufaktur' nicht gefunden! Abbruch.")
            return
        
        print(f"📍 Verwende Lager: Versandmanufaktur (ID: {location_id})")
        
        updated_bundles = 0
        
        for bundle_sku, components in BUNDLE_CONFIG.items():
            # Berechne verfügbaren Bestand für Bundle
            available_qty = calculate_bundle_stock(bundle_sku, components, location_id)
            
            # Hole Bundle-Produkt
            bundle_product, bundle_variant = get_product_by_sku(bundle_sku)
            if not bundle_variant:
                print(f"⚠️  Bundle {bundle_sku} nicht in Shopify gefunden!")
                continue
            
            # Aktueller Bundle-Bestand im Versandmanufaktur-Lager
            current_bundle_stock = get_inventory_quantity(bundle_variant.inventory_item_id, location_id)
            
            # Update nur wenn sich was geändert hat
            if current_bundle_stock != available_qty:
                if update_inventory_quantity(bundle_variant, available_qty, location_id):
                    updated_bundles += 1
            else:
                print(f"✓ {bundle_sku}: Bestand unverändert ({available_qty}) [Versandmanufaktur]")
        
        print(f"\n✅ Fertig! {updated_bundles} Bundles aktualisiert")
        
    except Exception as e:
        print(f"❌ Fehler: {e}")
        raise

if __name__ == "__main__":
    main()
