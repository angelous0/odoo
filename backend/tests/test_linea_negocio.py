"""
Test suite for X_LINEA_NEGOCIO feature and purchase_ok filter removal.
Tests:
1. x_linea_negocio table exists with correct columns
2. product_template has linea_negocio_id (INT) and linea_negocio (TEXT) columns
3. X_LINEA_NEGOCIO job is registered in sync_job table
4. GET /api/schema/tables includes x_linea_negocio
5. GET /api/odoo-sync/job-status lists 10 jobs including X_LINEA_NEGOCIO
6. POST /api/odoo-sync/run with job_code=X_LINEA_NEGOCIO returns success
7. purchase_ok filter was removed from sync_engine.py
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
SYNC_TOKEN = os.environ.get('ODOO_SYNC_TOKEN', 'sync-secret-2026')


class TestSchemaTablesAPI:
    """Test /api/schema/tables endpoint for x_linea_negocio"""
    
    def test_x_linea_negocio_table_exists(self):
        """x_linea_negocio table should exist with 8 columns"""
        response = requests.get(f"{BASE_URL}/api/schema/tables")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        tables = data.get('tables', [])
        
        # Find x_linea_negocio table
        xlb_table = next((t for t in tables if t['name'] == 'x_linea_negocio'), None)
        assert xlb_table is not None, "x_linea_negocio table not found in schema"
        assert xlb_table['exists'] is True, "x_linea_negocio table should exist"
        assert xlb_table['col_count'] == 8, f"Expected 8 columns, got {xlb_table['col_count']}"
        assert xlb_table['type'] == 'TABLE', f"Expected TABLE, got {xlb_table['type']}"

    def test_product_template_has_20_columns(self):
        """product_template should have 20 columns (including linea_negocio_id and linea_negocio)"""
        response = requests.get(f"{BASE_URL}/api/schema/tables")
        assert response.status_code == 200
        
        data = response.json()
        tables = data.get('tables', [])
        
        # Find product_template table
        pt_table = next((t for t in tables if t['name'] == 'product_template'), None)
        assert pt_table is not None, "product_template table not found"
        assert pt_table['col_count'] == 20, f"Expected 20 columns, got {pt_table['col_count']}"


class TestJobStatusAPI:
    """Test /api/odoo-sync/job-status for X_LINEA_NEGOCIO job"""
    
    def test_job_status_returns_10_jobs(self):
        """GET /api/odoo-sync/job-status should return 10 jobs"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        jobs = data.get('jobs', [])
        assert len(jobs) == 10, f"Expected 10 jobs, got {len(jobs)}"

    def test_x_linea_negocio_job_exists(self):
        """X_LINEA_NEGOCIO job should be in the jobs list"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        assert response.status_code == 200
        
        data = response.json()
        jobs = data.get('jobs', [])
        job_codes = [j['job_code'] for j in jobs]
        
        assert 'X_LINEA_NEGOCIO' in job_codes, f"X_LINEA_NEGOCIO not found in jobs: {job_codes}"

    def test_x_linea_negocio_job_config(self):
        """X_LINEA_NEGOCIO job should have correct config"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        assert response.status_code == 200
        
        data = response.json()
        jobs = data.get('jobs', [])
        xlb_job = next((j for j in jobs if j['job_code'] == 'X_LINEA_NEGOCIO'), None)
        
        assert xlb_job is not None, "X_LINEA_NEGOCIO job not found"
        assert xlb_job['enabled'] is True, "X_LINEA_NEGOCIO should be enabled"
        assert xlb_job['schedule_type'] == 'DAILY', f"Expected DAILY, got {xlb_job['schedule_type']}"
        assert xlb_job['chunk_size'] == 500, f"Expected 500, got {xlb_job['chunk_size']}"
        assert xlb_job['company_scope'] == 'GLOBAL', f"Expected GLOBAL, got {xlb_job['company_scope']}"

    def test_all_10_expected_jobs_present(self):
        """All 10 expected jobs should be present"""
        expected_jobs = [
            'RES_COMPANY', 'STOCK_LOCATIONS', 'STOCK_QUANTS', 'RES_USERS', 
            'RES_PARTNER', 'X_LINEA_NEGOCIO', 'PRODUCTS', 'ATTRIBUTES', 
            'POS_ORDERS', 'AR_CREDIT_INVOICES'
        ]
        
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        assert response.status_code == 200
        
        data = response.json()
        jobs = data.get('jobs', [])
        job_codes = [j['job_code'] for j in jobs]
        
        for expected in expected_jobs:
            assert expected in job_codes, f"{expected} not found in jobs: {job_codes}"


class TestSyncRunAPI:
    """Test POST /api/odoo-sync/run for X_LINEA_NEGOCIO"""
    
    def test_run_x_linea_negocio_returns_success(self):
        """POST /api/odoo-sync/run with job_code=X_LINEA_NEGOCIO should return success=true"""
        headers = {"Content-Type": "application/json"}
        payload = {"job_code": "X_LINEA_NEGOCIO"}
        
        response = requests.post(f"{BASE_URL}/api/odoo-sync/run", json=payload, headers=headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # The endpoint returns success even if sync runs in background
        assert data.get('success') is True, f"Expected success=true, got {data}"


class TestCodeReview:
    """Code verification tests"""
    
    def test_purchase_ok_filter_removed(self):
        """Verify purchase_ok filter was removed from sync_engine.py _sync_products"""
        # Read the sync_engine.py file and verify the base domain
        sync_engine_path = '/app/backend/sync_engine.py'
        
        with open(sync_engine_path, 'r') as f:
            content = f.read()
        
        # Find the _sync_products method and check base domain
        # The base should only have sale_ok filter, NOT purchase_ok=False
        import re
        
        # Look for the base domain assignment in _sync_products
        base_match = re.search(r'def _sync_products.*?base\s*=\s*\[([^\]]+)\]', content, re.DOTALL)
        assert base_match is not None, "Could not find base domain in _sync_products"
        
        base_domain = base_match.group(1)
        
        # Verify sale_ok is present
        assert 'sale_ok' in base_domain, f"sale_ok not in base domain: {base_domain}"
        
        # Verify purchase_ok=False is NOT in base domain
        assert 'purchase_ok' not in base_domain, f"purchase_ok should NOT be in base domain: {base_domain}"

    def test_linea_negocio_fields_in_sync_engine(self):
        """Verify x_linea_negocio_id is fetched and both columns are inserted"""
        sync_engine_path = '/app/backend/sync_engine.py'
        
        with open(sync_engine_path, 'r') as f:
            content = f.read()
        
        # Check x_linea_negocio_id is in tmpl_fields
        assert 'x_linea_negocio_id' in content, "x_linea_negocio_id not found in sync_engine.py"
        
        # Check SQL has both linea_negocio_id and linea_negocio columns
        assert 'linea_negocio_id,linea_negocio' in content, "linea_negocio columns not found in SQL"

    def test_x_linea_negocio_sync_method_exists(self):
        """Verify _sync_x_linea_negocio method exists"""
        sync_engine_path = '/app/backend/sync_engine.py'
        
        with open(sync_engine_path, 'r') as f:
            content = f.read()
        
        assert '_sync_x_linea_negocio' in content, "_sync_x_linea_negocio method not found"
        assert "x_linea_negocio" in content.lower(), "x_linea_negocio model reference not found"


class TestMigrationScript:
    """Verify migration script has correct DDL"""
    
    def test_x_linea_negocio_table_ddl_exists(self):
        """x_linea_negocio table DDL should be in migration.py"""
        migration_path = '/app/backend/migration.py'
        
        with open(migration_path, 'r') as f:
            content = f.read()
        
        assert 'CREATE TABLE IF NOT EXISTS odoo.x_linea_negocio' in content
    
    def test_linea_negocio_id_column_ddl_exists(self):
        """ALTER TABLE for linea_negocio_id should be in migration.py"""
        migration_path = '/app/backend/migration.py'
        
        with open(migration_path, 'r') as f:
            content = f.read()
        
        assert 'linea_negocio_id INT NULL' in content or 'ADD COLUMN IF NOT EXISTS linea_negocio_id' in content
    
    def test_x_linea_negocio_job_seed_exists(self):
        """X_LINEA_NEGOCIO job seed should be in migration.py"""
        migration_path = '/app/backend/migration.py'
        
        with open(migration_path, 'r') as f:
            content = f.read()
        
        assert "X_LINEA_NEGOCIO" in content, "X_LINEA_NEGOCIO job seed not found in migration.py"
    
    def test_odoo_tables_list_includes_x_linea_negocio(self):
        """ODOO_TABLES list should include x_linea_negocio"""
        migration_path = '/app/backend/migration.py'
        
        with open(migration_path, 'r') as f:
            content = f.read()
        
        assert '"x_linea_negocio"' in content, "x_linea_negocio not in ODOO_TABLES list"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
