"""
Test Suite for 'tipo' field using x_tipo_resumen values.
Verifies that tipo field in product_template uses x_tipo_resumen (like 'Pantalon Denim', 'Polo')
instead of generic names/IDs in all views and endpoints.
"""
import pytest
import requests
import os
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://catalog-archive.preview.emergentagent.com').rstrip('/')

class TestTipoFieldInPosLinesFull:
    """Tests for /api/pos-lines-full endpoint - tipo field with x_tipo_resumen values"""
    
    def test_pos_lines_full_returns_tipo_field(self):
        """GET /api/pos-lines-full should include 'tipo' field in response"""
        response = requests.get(f"{BASE_URL}/api/pos-lines-full", params={"page_size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert len(data["rows"]) > 0
        
        # Verify tipo field exists in rows
        for row in data["rows"][:5]:
            assert "tipo" in row, "tipo field must be present in response"
            # If tipo is not null, verify it's a descriptive name (x_tipo_resumen format)
            if row["tipo"] is not None:
                assert isinstance(row["tipo"], str), "tipo should be a string"
                assert len(row["tipo"]) > 0, "tipo should not be empty string"
                print(f"  tipo value: {row['tipo']}")
    
    def test_pos_lines_tipo_filter_works(self):
        """GET /api/pos-lines-full with tipo filter should return filtered results"""
        # First get some data with tipo
        response = requests.get(f"{BASE_URL}/api/pos-lines-full", params={"page_size": 50})
        data = response.json()
        
        # Find a valid tipo value to filter by
        tipo_value = None
        for row in data["rows"]:
            if row["tipo"] and len(row["tipo"]) > 2:
                tipo_value = row["tipo"]
                break
        
        if tipo_value:
            # Test filter with partial match
            filter_response = requests.get(f"{BASE_URL}/api/pos-lines-full", 
                params={"tipo": tipo_value[:4], "page_size": 50})
            assert filter_response.status_code == 200
            filter_data = filter_response.json()
            print(f"  Filtering by tipo containing '{tipo_value[:4]}': found {filter_data['total']} results")
            
            # All results should contain the filter value (case-insensitive)
            for row in filter_data["rows"][:5]:
                if row["tipo"]:
                    assert tipo_value[:4].lower() in row["tipo"].lower()
    
    def test_pos_lines_tipo_has_correct_values(self):
        """Verify tipo field contains x_tipo_resumen format values (e.g., 'Pantalon Denim', 'Polo')"""
        response = requests.get(f"{BASE_URL}/api/pos-lines-full", params={"page_size": 100})
        data = response.json()
        
        expected_tipos = ["Pantalon", "Polo", "Camisa", "Bermuda", "Polera", "Correa", "Drill"]
        found_tipos = set()
        
        for row in data["rows"]:
            if row["tipo"]:
                found_tipos.add(row["tipo"])
        
        print(f"  Found tipo values: {list(found_tipos)[:10]}")
        
        # Verify we have descriptive names, not IDs
        for tipo in list(found_tipos)[:10]:
            assert not tipo.isdigit(), f"tipo should be descriptive name, not ID: {tipo}"
            # Check it's not a generic M2O reference like "product.tipo,1"
            assert "product.tipo" not in tipo.lower(), f"tipo should be x_tipo_resumen, not ref: {tipo}"


class TestTipoFieldInStockByProduct:
    """Tests for /api/stock-by-product endpoint - tipo field"""
    
    def test_stock_by_product_returns_tipo_field(self):
        """GET /api/stock-by-product should include tipo field in response"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page_size": 50})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        
        # Check schema has tipo field
        if data["rows"]:
            first_row = data["rows"][0]
            assert "tipo" in first_row, "tipo field must be in response schema"
            assert "product_name" in first_row, "product_name field must be in response"
            assert "marca" in first_row, "marca field must be in response"
    
    def test_stock_by_product_tipo_has_values_when_product_exists(self):
        """When product exists in product_template, tipo should have x_tipo_resumen value"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page_size": 200})
        data = response.json()
        
        # Find rows where product_name is not null (meaning product exists)
        rows_with_products = [r for r in data["rows"] if r.get("product_name") is not None]
        
        print(f"  Total rows: {data['total']}, rows with product data: {len(rows_with_products)}")
        
        if rows_with_products:
            for row in rows_with_products[:5]:
                print(f"    product_id={row['product_id']}, name={row['product_name'][:30] if row['product_name'] else 'N/A'}, tipo={row['tipo']}, marca={row['marca']}")
            
            # Verify tipo format when present
            for row in rows_with_products[:10]:
                if row["tipo"]:
                    assert isinstance(row["tipo"], str)
                    assert not row["tipo"].isdigit(), "tipo should not be numeric ID"


class TestTipoFieldInStockByLocation:
    """Tests for /api/stock-by-location endpoint - tipo field"""
    
    def test_stock_by_location_returns_tipo_field(self):
        """GET /api/stock-by-location should include tipo field in response"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page_size": 50})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        
        # Check schema has tipo field
        if data["rows"]:
            first_row = data["rows"][0]
            assert "tipo" in first_row, "tipo field must be in response schema"
            assert "product_name" in first_row, "product_name field must be in response"
            assert "marca" in first_row, "marca field must be in response"
            assert "location_name" in first_row, "location_name field must be in response"
    
    def test_stock_by_location_tipo_has_values_when_product_exists(self):
        """When product exists in product_template, tipo should have x_tipo_resumen value"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page_size": 200})
        data = response.json()
        
        # Find rows where product_name is not null
        rows_with_products = [r for r in data["rows"] if r.get("product_name") is not None]
        
        print(f"  Total rows: {data['total']}, rows with product data: {len(rows_with_products)}")
        
        if rows_with_products:
            for row in rows_with_products[:5]:
                print(f"    product_id={row['product_id']}, loc={row['location_id']}, name={row['product_name'][:25] if row['product_name'] else 'N/A'}, tipo={row['tipo']}, marca={row['marca']}")
            
            # Verify tipo format when present
            for row in rows_with_products[:10]:
                if row["tipo"]:
                    assert isinstance(row["tipo"], str)
                    assert not row["tipo"].isdigit(), "tipo should not be numeric ID"


class TestProductTemplateDirectly:
    """Direct tests on product_template tipo field values via health endpoint"""
    
    def test_health_endpoint_shows_product_template_data(self):
        """GET /api/health should show product_template has data"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        # Find product_template in tables
        pt_data = None
        for table in data.get("tables", []):
            if table["table"] == "product_template":
                pt_data = table
                break
        
        assert pt_data is not None, "product_template should be in health response"
        assert pt_data["count"] > 0, "product_template should have data"
        print(f"  product_template count: {pt_data['count']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
