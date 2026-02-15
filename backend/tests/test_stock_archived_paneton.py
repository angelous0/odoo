"""
Test cases for stock API enhancements:
1. Paneton exclusion filter - products with 'paneton' in name should NOT be returned
2. include_archived parameter - filters by active=true by default, includes all when true
3. active field presence - response should include 'active' boolean field
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestStockByProductAPI:
    """Tests for /api/stock-by-product endpoint"""
    
    def test_stock_by_product_returns_active_field(self):
        """Response should include 'active' field in each row"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert len(data["rows"]) > 0
        for row in data["rows"]:
            assert "active" in row, f"Row missing 'active' field: {row}"
            assert isinstance(row["active"], bool), f"'active' should be boolean, got {type(row['active'])}"
    
    def test_stock_by_product_no_paneton(self):
        """No products with 'paneton' (case insensitive) in name should be returned"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 500})
        assert response.status_code == 200
        data = response.json()
        for row in data["rows"]:
            product_name = (row.get("product_name") or "").lower()
            assert "paneton" not in product_name, f"Product with paneton found: {row['product_name']}"
    
    def test_stock_by_product_include_archived_default_false(self):
        """By default (include_archived=false), should filter by active=true"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 100})
        assert response.status_code == 200
        data = response.json()
        # All returned rows should have active=true when include_archived is not set
        for row in data["rows"]:
            assert row.get("active") == True, f"Found inactive product when include_archived=false: {row}"
    
    def test_stock_by_product_include_archived_true_param(self):
        """include_archived=true should be accepted as parameter"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", 
                               params={"page": 1, "page_size": 10, "include_archived": "true"})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "total" in data
    
    def test_stock_by_product_returns_expected_fields(self):
        """Response should include product_id, product_name, marca, tipo, active, qty, reserved_qty, available_qty"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["rows"]) > 0
        required_fields = ["product_id", "product_name", "marca", "tipo", "active", "qty", "reserved_qty", "available_qty"]
        for row in data["rows"]:
            for field in required_fields:
                assert field in row, f"Missing field '{field}' in response row"


class TestStockByLocationAPI:
    """Tests for /api/stock-by-location endpoint"""
    
    def test_stock_by_location_returns_active_field(self):
        """Response should include 'active' field in each row"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert len(data["rows"]) > 0
        for row in data["rows"]:
            assert "active" in row, f"Row missing 'active' field: {row}"
            assert isinstance(row["active"], bool), f"'active' should be boolean, got {type(row['active'])}"
    
    def test_stock_by_location_no_paneton(self):
        """No products with 'paneton' (case insensitive) in name should be returned"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 500})
        assert response.status_code == 200
        data = response.json()
        for row in data["rows"]:
            product_name = (row.get("product_name") or "").lower()
            assert "paneton" not in product_name, f"Product with paneton found: {row['product_name']}"
    
    def test_stock_by_location_include_archived_default_false(self):
        """By default (include_archived=false), should filter by active=true"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 100})
        assert response.status_code == 200
        data = response.json()
        # All returned rows should have active=true when include_archived is not set
        for row in data["rows"]:
            assert row.get("active") == True, f"Found inactive product when include_archived=false: {row}"
    
    def test_stock_by_location_include_archived_true_param(self):
        """include_archived=true should be accepted as parameter"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", 
                               params={"page": 1, "page_size": 10, "include_archived": "true"})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "total" in data
    
    def test_stock_by_location_returns_expected_fields(self):
        """Response should include product_id, location_id, product_name, marca, tipo, active, qty, reserved_qty, available_qty, location_name"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["rows"]) > 0
        required_fields = ["product_id", "location_id", "product_name", "marca", "tipo", "active", 
                          "qty", "reserved_qty", "available_qty", "location_name"]
        for row in data["rows"]:
            for field in required_fields:
                assert field in row, f"Missing field '{field}' in response row"


class TestPanetonExclusionFilter:
    """Specific tests for paneton product exclusion"""
    
    def test_large_sample_no_paneton_by_product(self):
        """Check multiple pages - no paneton products should appear"""
        for page in [1, 5, 10]:
            response = requests.get(f"{BASE_URL}/api/stock-by-product", 
                                   params={"page": page, "page_size": 100, "include_archived": "true"})
            if response.status_code == 200:
                data = response.json()
                for row in data["rows"]:
                    product_name = (row.get("product_name") or "").lower()
                    assert "paneton" not in product_name, f"Paneton found on page {page}: {row['product_name']}"
    
    def test_large_sample_no_paneton_by_location(self):
        """Check multiple pages - no paneton products should appear"""
        for page in [1, 5, 10]:
            response = requests.get(f"{BASE_URL}/api/stock-by-location", 
                                   params={"page": page, "page_size": 100, "include_archived": "true"})
            if response.status_code == 200:
                data = response.json()
                for row in data["rows"]:
                    product_name = (row.get("product_name") or "").lower()
                    assert "paneton" not in product_name, f"Paneton found on page {page}: {row['product_name']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
