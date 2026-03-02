"""
Test Sync Control API endpoints for job status, run, and batch operations.
Tests: GET /api/odoo-sync/job-status, POST /api/odoo-sync/run, POST /api/odoo-sync/run-batch
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# 9 expected job codes
EXPECTED_JOB_CODES = [
    "RES_COMPANY", "STOCK_LOCATIONS", "STOCK_QUANTS", "RES_USERS",
    "RES_PARTNER", "PRODUCTS", "ATTRIBUTES", "POS_ORDERS", "AR_CREDIT_INVOICES"
]


class TestOdooSyncJobStatus:
    """Test GET /api/odoo-sync/job-status endpoint"""

    def test_get_all_jobs_returns_200(self):
        """GET /api/odoo-sync/job-status returns 200 with all 9 jobs"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        assert response.status_code == 200
        data = response.json()
        
        # Verify jobs array exists
        assert "jobs" in data
        assert isinstance(data["jobs"], list)
        assert len(data["jobs"]) == 9, f"Expected 9 jobs, got {len(data['jobs'])}"
        
    def test_get_all_jobs_contains_expected_job_codes(self):
        """All 9 expected job codes are present"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        data = response.json()
        
        returned_job_codes = [j["job_code"] for j in data["jobs"]]
        for expected_code in EXPECTED_JOB_CODES:
            assert expected_code in returned_job_codes, f"Missing job code: {expected_code}"

    def test_get_all_jobs_returns_last_runs(self):
        """Response includes last_runs dictionary"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        data = response.json()
        
        assert "last_runs" in data
        assert isinstance(data["last_runs"], dict)

    def test_get_all_jobs_returns_running_jobs(self):
        """Response includes running_jobs array"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        data = response.json()
        
        assert "running_jobs" in data
        assert isinstance(data["running_jobs"], list)

    def test_job_has_required_fields(self):
        """Each job object has required fields"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status")
        data = response.json()
        
        required_fields = ["job_code", "enabled", "schedule_type", "mode", "chunk_size", "company_scope"]
        for job in data["jobs"]:
            for field in required_fields:
                assert field in job, f"Job {job.get('job_code')} missing field: {field}"

    def test_get_specific_job_products(self):
        """GET /api/odoo-sync/job-status?job_code=PRODUCTS returns specific job"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "PRODUCTS"})
        assert response.status_code == 200
        data = response.json()
        
        assert "job" in data
        assert data["job"]["job_code"] == "PRODUCTS"
        assert "last_run" in data

    def test_get_specific_job_has_last_run(self):
        """Specific job response includes last_run details"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "PRODUCTS"})
        data = response.json()
        
        # last_run may be None if never run, but key should exist
        assert "last_run" in data
        if data["last_run"]:
            assert "status" in data["last_run"]
            assert "rows_upserted" in data["last_run"]

    def test_get_nonexistent_job_returns_error(self):
        """GET with invalid job_code returns error"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "INVALID_JOB"})
        assert response.status_code == 200  # API returns 200 with error in body
        data = response.json()
        assert "error" in data


class TestOdooSyncRun:
    """Test POST /api/odoo-sync/run endpoint - DO NOT actually run full sync"""

    def test_run_endpoint_accepts_request(self):
        """POST /api/odoo-sync/run accepts request and returns success structure"""
        # Note: This will actually start a background job
        # But as per instructions, we just verify endpoint accepts request
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run",
            json={"job_code": "RES_COMPANY"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should return success structure with message
        assert "success" in data
        assert "message" in data
        
    def test_run_endpoint_requires_job_code(self):
        """POST without job_code should fail validation"""
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run",
            json={}
        )
        # Pydantic will return 422 for missing required field
        assert response.status_code == 422

    def test_run_endpoint_accepts_mode_param(self):
        """POST accepts optional mode parameter"""
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run",
            json={"job_code": "RES_USERS", "mode": "INCREMENTAL"}
        )
        assert response.status_code == 200


class TestOdooSyncRunBatch:
    """Test POST /api/odoo-sync/run-batch endpoint"""

    def test_batch_endpoint_accepts_request(self):
        """POST /api/odoo-sync/run-batch accepts array of job_codes"""
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run-batch",
            json={"job_codes": ["RES_COMPANY"], "stop_on_error": True}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "success" in data
        assert "message" in data

    def test_batch_endpoint_returns_job_codes(self):
        """Batch endpoint returns the submitted job_codes"""
        job_codes = ["RES_USERS"]
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run-batch",
            json={"job_codes": job_codes, "stop_on_error": True}
        )
        data = response.json()
        
        if data.get("success"):
            assert "job_codes" in data
            assert data["job_codes"] == job_codes

    def test_batch_endpoint_requires_job_codes(self):
        """POST without job_codes should fail validation"""
        response = requests.post(
            f"{BASE_URL}/api/odoo-sync/run-batch",
            json={"stop_on_error": True}
        )
        assert response.status_code == 422


class TestMacroJobCodes:
    """Test that macro job codes match expected values"""

    def test_clientes_macro_job_res_partner(self):
        """Clientes macro uses RES_PARTNER job"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "RES_PARTNER"})
        data = response.json()
        assert data.get("job", {}).get("job_code") == "RES_PARTNER"

    def test_ventas_macro_job_pos_orders(self):
        """Ventas macro uses POS_ORDERS job"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "POS_ORDERS"})
        data = response.json()
        assert data.get("job", {}).get("job_code") == "POS_ORDERS"

    def test_productos_macro_jobs_products_attributes(self):
        """Productos macro uses PRODUCTS and ATTRIBUTES jobs"""
        for job_code in ["PRODUCTS", "ATTRIBUTES"]:
            response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": job_code})
            data = response.json()
            assert data.get("job", {}).get("job_code") == job_code

    def test_stock_macro_job_stock_quants(self):
        """Stock macro uses STOCK_QUANTS job"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "STOCK_QUANTS"})
        data = response.json()
        assert data.get("job", {}).get("job_code") == "STOCK_QUANTS"

    def test_creditos_macro_job_ar_credit_invoices(self):
        """Créditos macro uses AR_CREDIT_INVOICES job"""
        response = requests.get(f"{BASE_URL}/api/odoo-sync/job-status", params={"job_code": "AR_CREDIT_INVOICES"})
        data = response.json()
        assert data.get("job", {}).get("job_code") == "AR_CREDIT_INVOICES"
