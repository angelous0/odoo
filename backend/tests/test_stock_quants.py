"""
Backend API tests for Fase 5: stock.quant sync + validation screens.
Testing: stock-quants, stock-by-product, stock-by-location, health, sync-jobs APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestStockQuantsAPI:
    """Tests for GET /api/stock-quants endpoint"""
    
    def test_stock_quants_pagination(self):
        """Test paginated stock quants return"""
        response = requests.get(f"{BASE_URL}/api/stock-quants", params={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "rows" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "total_pages" in data
        
        # Data validation - should have >1M quants
        assert data["total"] > 1000000, f"Expected >1M quants, got {data['total']}"
        assert len(data["rows"]) <= 10
        
        # Validate row structure
        if data["rows"]:
            row = data["rows"][0]
            assert "odoo_id" in row
            assert "product_id" in row
            assert "location_id" in row
            assert "qty" in row
            assert "reserved_qty" in row
            assert "in_date" in row
            assert "odoo_write_date" in row
    
    def test_stock_quants_filter_by_product_id(self):
        """Test product_id filter"""
        response = requests.get(f"{BASE_URL}/api/stock-quants", params={"page": 1, "page_size": 50, "product_id": 57914})
        assert response.status_code == 200
        data = response.json()
        
        # All rows should have the filtered product_id
        for row in data["rows"]:
            assert row["product_id"] == 57914
    
    def test_stock_quants_filter_by_location_id(self):
        """Test location_id filter"""
        response = requests.get(f"{BASE_URL}/api/stock-quants", params={"page": 1, "page_size": 50, "location_id": 9})
        assert response.status_code == 200
        data = response.json()
        
        # All rows should have the filtered location_id
        for row in data["rows"]:
            assert row["location_id"] == 9


class TestStockByProductAPI:
    """Tests for GET /api/stock-by-product endpoint"""
    
    def test_stock_by_product_all(self):
        """Test aggregated stock by product (all)"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "rows" in data
        assert "total" in data
        assert data["total"] > 8000, f"Expected >8000 products, got {data['total']}"
        
        # Validate row structure
        if data["rows"]:
            row = data["rows"][0]
            assert "product_id" in row
            assert "qty" in row
            assert "reserved_qty" in row
            assert "available_qty" in row
    
    def test_stock_by_product_only_available(self):
        """Test only_available=true filter"""
        response = requests.get(f"{BASE_URL}/api/stock-by-product", params={"page": 1, "page_size": 50, "only_available": True})
        assert response.status_code == 200
        data = response.json()
        
        # All rows should have available_qty > 0
        for row in data["rows"]:
            assert row["available_qty"] > 0, f"Expected available_qty > 0, got {row['available_qty']}"


class TestStockByLocationAPI:
    """Tests for GET /api/stock-by-location endpoint"""
    
    def test_stock_by_location_all(self):
        """Test stock by product+location"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 10})
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "rows" in data
        assert "total" in data
        assert data["total"] > 16000, f"Expected >16000 rows, got {data['total']}"
        
        # Validate row structure with location name
        if data["rows"]:
            row = data["rows"][0]
            assert "product_id" in row
            assert "location_id" in row
            assert "available_qty" in row
            assert "qty" in row
            assert "reserved_qty" in row
            assert "location_name" in row or "location_raw_name" in row, "Missing location name in response"
    
    def test_stock_by_location_only_available(self):
        """Test only_available=true filter"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 50, "only_available": True})
        assert response.status_code == 200
        data = response.json()
        
        # All rows should have available_qty > 0
        for row in data["rows"]:
            assert row["available_qty"] > 0
    
    def test_stock_by_location_filter_location(self):
        """Test location_id filter"""
        response = requests.get(f"{BASE_URL}/api/stock-by-location", params={"page": 1, "page_size": 50, "location_id": 15})
        assert response.status_code == 200
        data = response.json()
        
        # All rows should have the filtered location_id
        for row in data["rows"]:
            assert row["location_id"] == 15


class TestHealthAPI:
    """Tests for GET /api/health endpoint"""
    
    def test_health_includes_stock_quant(self):
        """Test health endpoint includes stock_quant table"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        
        # Validate structure
        assert "tables" in data
        assert "pos_by_company" in data
        assert "orphan_lines" in data
        assert "recent_errors" in data
        
        # Find stock_quant in tables
        table_names = [t["table"] for t in data["tables"]]
        assert "stock_quant" in table_names, f"stock_quant not in health tables: {table_names}"
        
        # Validate stock_quant count
        stock_quant_entry = next(t for t in data["tables"] if t["table"] == "stock_quant")
        assert stock_quant_entry["count"] > 1000000, f"Expected >1M stock quants, got {stock_quant_entry['count']}"


class TestSyncJobsAPI:
    """Tests for GET /api/sync-jobs endpoint"""
    
    def test_stock_quants_job_exists(self):
        """Test STOCK_QUANTS job with correct config"""
        response = requests.get(f"{BASE_URL}/api/sync-jobs")
        assert response.status_code == 200
        data = response.json()
        
        # Find STOCK_QUANTS job
        jobs = data.get("jobs", [])
        job_codes = [j["job_code"] for j in jobs]
        assert "STOCK_QUANTS" in job_codes, f"STOCK_QUANTS not in sync jobs: {job_codes}"
        
        # Validate job config
        stock_job = next(j for j in jobs if j["job_code"] == "STOCK_QUANTS")
        assert stock_job["chunk_size"] == 5000, f"Expected chunk_size=5000, got {stock_job['chunk_size']}"
        assert stock_job["company_scope"] == "GLOBAL", f"Expected company_scope=GLOBAL, got {stock_job['company_scope']}"
        assert stock_job["enabled"] == True


class TestConnectionAPI:
    """Test basic API connectivity"""
    
    def test_connection(self):
        """Test PostgreSQL connection"""
        response = requests.get(f"{BASE_URL}/api/connection/test")
        assert response.status_code == 200
        data = response.json()
        assert data.get("connected") == True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
