#!/usr/bin/env python3
"""
Backend API Test Suite for Odoo ODS Schema Manager
Tests all PostgreSQL-connected API endpoints
"""

import requests
import sys
import time
from datetime import datetime

class OdooODSAPITester:
    def __init__(self, base_url="https://pos-data-mirror.preview.emergentagent.com/api"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.failures = []

    def run_test(self, name, method, endpoint, expected_status, data=None, check_response=None):
        """Run a single API test with optional response validation"""
        url = f"{self.base_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=30)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=60)

            success = response.status_code == expected_status
            response_data = {}
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw_response": response.text}

            if success:
                # Additional response validation if provided
                if check_response:
                    validation_result = check_response(response_data)
                    if validation_result is not True:
                        success = False
                        print(f"❌ Failed - Response validation failed: {validation_result}")
                        self.failures.append(f"{name}: Response validation failed - {validation_result}")
                    else:
                        print(f"✅ Passed - Status: {response.status_code}")
                        print(f"   Response validation: OK")
                else:
                    print(f"✅ Passed - Status: {response.status_code}")
                
                if success:
                    self.tests_passed += 1
                    
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response_data}")
                self.failures.append(f"{name}: Expected status {expected_status}, got {response.status_code}")

            return success, response_data

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            self.failures.append(f"{name}: Exception - {str(e)}")
            return False, {}

    def test_connection(self):
        """Test PostgreSQL connection"""
        def check_conn(response_data):
            if not response_data.get('connected'):
                return "Connection not established"
            if 'version' not in response_data:
                return "PostgreSQL version not returned"
            print(f"   PostgreSQL version: {response_data['version'][:50]}...")
            return True
        
        return self.run_test(
            "PostgreSQL Connection Test",
            "GET",
            "connection/test",
            200,
            check_response=check_conn
        )

    def test_migration_status(self):
        """Test migration status endpoint"""
        def check_status(response_data):
            if not response_data.get('schema_exists'):
                return "Schema 'odoo' does not exist"
            
            tables_found = response_data.get('tables_found', 0)
            views_found = response_data.get('views_found', 0)
            expected_tables = response_data.get('tables_expected', 13)
            expected_views = response_data.get('views_expected', 3)
            
            if tables_found < expected_tables:
                return f"Found {tables_found} tables, expected {expected_tables}"
            if views_found < expected_views:
                return f"Found {views_found} views, expected {expected_views}"
                
            if not response_data.get('all_ok'):
                return "Migration status shows not all_ok"
                
            print(f"   Schema exists: {response_data.get('schema_exists')}")
            print(f"   Tables: {tables_found}/{expected_tables}")
            print(f"   Views: {views_found}/{expected_views}")
            print(f"   Indexes: {response_data.get('indexes_count', 0)}")
            print(f"   All OK: {response_data.get('all_ok')}")
            return True
        
        return self.run_test(
            "Migration Status Check",
            "GET",
            "migration/status",
            200,
            check_response=check_status
        )

    def test_schema_tables(self):
        """Test schema tables endpoint"""
        def check_tables(response_data):
            tables = response_data.get('tables', [])
            if len(tables) < 16:  # 13 tables + 3 views
                return f"Expected at least 16 items (tables + views), got {len(tables)}"
            
            table_count = len([t for t in tables if t.get('type') == 'TABLE'])
            view_count = len([t for t in tables if t.get('type') == 'VIEW'])
            
            if table_count < 13:
                return f"Expected 13 tables, got {table_count}"
            if view_count < 3:
                return f"Expected 3 views, got {view_count}"
                
            all_exist = all(t.get('exists') for t in tables)
            if not all_exist:
                missing = [t['name'] for t in tables if not t.get('exists')]
                return f"Some tables/views don't exist: {missing}"
                
            print(f"   Found {table_count} tables and {view_count} views")
            print(f"   All items exist: {all_exist}")
            return True
        
        return self.run_test(
            "Schema Tables List",
            "GET",
            "schema/tables",
            200,
            check_response=check_tables
        )

    def test_sync_jobs(self):
        """Test sync jobs endpoint"""
        def check_jobs(response_data):
            jobs = response_data.get('jobs', [])
            expected_jobs = ['RES_COMPANY', 'RES_USERS', 'RES_PARTNER', 'PRODUCTS', 'ATTRIBUTES', 'POS_ORDERS']
            
            if len(jobs) < 6:
                return f"Expected 6 jobs, got {len(jobs)}"
                
            job_codes = [j.get('job_code') for j in jobs]
            missing = [code for code in expected_jobs if code not in job_codes]
            
            if missing:
                return f"Missing job codes: {missing}"
                
            # Check that jobs have proper structure
            for job in jobs:
                if not job.get('run_time'):
                    return f"Job {job.get('job_code')} missing run_time"
                    
            print(f"   Found {len(jobs)} sync jobs: {', '.join(job_codes)}")
            return True
        
        return self.run_test(
            "Sync Jobs List",
            "GET",
            "sync-jobs",
            200,
            check_response=check_jobs
        )

    def test_sync_logs(self):
        """Test sync logs endpoint (empty expected)"""
        def check_logs(response_data):
            logs = response_data.get('logs', [])
            print(f"   Found {len(logs)} sync execution logs")
            return True  # Empty is expected initially
        
        return self.run_test(
            "Sync Logs List",
            "GET",
            "sync-logs",
            200,
            check_response=check_logs
        )

    def test_schema_indexes(self):
        """Test schema indexes endpoint"""
        def check_indexes(response_data):
            indexes = response_data.get('indexes', [])
            if len(indexes) < 38:  # Expected 38+ indexes
                return f"Expected at least 38 indexes, got {len(indexes)}"
                
            # Check index structure
            for idx in indexes[:3]:  # Check first few
                if not idx.get('indexname') or not idx.get('tablename'):
                    return "Indexes missing required fields (indexname, tablename)"
                    
            print(f"   Found {len(indexes)} indexes in odoo schema")
            return True
        
        return self.run_test(
            "Schema Indexes List", 
            "GET",
            "schema/indexes",
            200,
            check_response=check_indexes
        )

    def test_execute_migration(self):
        """Test migration execution endpoint"""
        def check_migration(response_data):
            if not response_data.get('success'):
                return f"Migration failed: {response_data.get('message', 'Unknown error')}"
                
            if 'duration_ms' not in response_data:
                return "Migration duration not returned"
                
            print(f"   Migration completed in {response_data.get('duration_ms')}ms")
            print(f"   Message: {response_data.get('message', 'N/A')}")
            return True
        
        return self.run_test(
            "Execute Migration",
            "POST", 
            "migrate",
            200,
            check_response=check_migration
        )

    def test_stock_locations(self):
        """Test stock-locations endpoint"""
        def check_locations(response_data):
            if 'locations' not in response_data:
                return "Missing 'locations' key in response"
            
            locations = response_data['locations']
            if len(locations) < 52:  # Expected ~52 locations
                return f"Expected ~52 locations, got {len(locations)}"
                
            # Check location structure
            if locations:
                loc = locations[0]
                required_fields = ['odoo_id', 'name', 'complete_name', 'usage', 'active', 'odoo_write_date']
                for field in required_fields:
                    if field not in loc:
                        return f"Location missing required field: {field}"
                        
                # Check if ordered by write_date desc (if dates available)
                if len(locations) >= 2 and locations[0].get('odoo_write_date') and locations[1].get('odoo_write_date'):
                    if locations[0]['odoo_write_date'] < locations[1]['odoo_write_date']:
                        return "Locations not ordered by odoo_write_date DESC"
            
            print(f"   Found {len(locations)} stock locations")
            print(f"   First location: {locations[0].get('name', 'N/A') if locations else 'None'}")
            return True
        
        return self.run_test(
            "Stock Locations - List All",
            "GET",
            "stock-locations",
            200,
            check_response=check_locations
        )

    def test_stock_locations_search(self):
        """Test stock-locations search functionality"""
        def check_search(response_data):
            if 'locations' not in response_data:
                return "Missing 'locations' key in response"
            
            locations = response_data['locations']
            # With search=AP, should get some results but less than total
            if len(locations) == 0:
                return "Search for 'AP' returned no results - expected some matches"
            
            # Check that returned locations contain 'AP' in relevant fields
            for loc in locations[:3]:  # Check first few
                name_match = 'AP' in (loc.get('name') or '').upper()
                x_nombre_match = 'AP' in (loc.get('x_nombre') or '').upper() 
                complete_name_match = 'AP' in (loc.get('complete_name') or '').upper()
                
                if not (name_match or x_nombre_match or complete_name_match):
                    return f"Location {loc.get('name')} doesn't contain 'AP' in searchable fields"
            
            print(f"   Search 'AP' returned {len(locations)} locations")
            return True
        
        return self.run_test(
            "Stock Locations - Search by 'AP'",
            "GET",
            "stock-locations?search=AP",
            200,
            check_response=check_search
        )

    def test_pos_lines_full(self):
        """Test pos-lines-full endpoint with pagination"""
        def check_pos_lines(response_data):
            required_fields = ['rows', 'total', 'page', 'page_size', 'total_pages']
            for field in required_fields:
                if field not in response_data:
                    return f"Missing required field: {field}"
            
            if response_data['page'] != 1 or response_data['page_size'] != 50:
                return f"Expected page=1, page_size=50, got page={response_data['page']}, page_size={response_data['page_size']}"
                
            rows = response_data['rows']
            total = response_data['total']
            
            if total > 0 and len(rows) == 0:
                return f"Total={total} but rows is empty"
                
            if len(rows) > 50:
                return f"Expected max 50 rows per page, got {len(rows)}"
            
            # Check row structure if data exists
            if rows:
                row = rows[0]
                expected_fields = ['company_key', 'date_order', 'state', 'order_id', 'pos_order_line_id', 
                                 'product_id', 'qty', 'price_unit', 'discount', 'price_subtotal', 
                                 'talla', 'color', 'marca', 'tipo', 'tela']
                for field in expected_fields:
                    if field not in row:
                        return f"POS line row missing field: {field}"
            
            print(f"   Found {total} total POS lines, showing {len(rows)} on page 1")
            print(f"   Total pages: {response_data['total_pages']}")
            return True
        
        return self.run_test(
            "POS Lines Full - Paginated List",
            "GET",
            "pos-lines-full?page=1&page_size=50&date_from=2026-02-01",
            200,
            check_response=check_pos_lines
        )

    def test_pos_lines_full_filters(self):
        """Test pos-lines-full with company filter"""
        def check_filtered_lines(response_data):
            if 'rows' not in response_data:
                return "Missing 'rows' key in response"
                
            rows = response_data['rows']
            
            # Check that all returned rows have company_key = Ambission
            for row in rows:
                if row.get('company_key') != 'Ambission':
                    return f"Expected company_key=Ambission, got {row.get('company_key')}"
            
            print(f"   Filtered by company=Ambission: {len(rows)} rows")
            return True
        
        return self.run_test(
            "POS Lines Full - Filter by Company",
            "GET", 
            "pos-lines-full?company_key=Ambission",
            200,
            check_response=check_filtered_lines
        )

    def test_health_endpoint(self):
        """Test health endpoint for system monitoring"""
        def check_health(response_data):
            required_sections = ['tables', 'pos_by_company', 'orphan_lines', 'recent_errors']
            for section in required_sections:
                if section not in response_data:
                    return f"Missing health section: {section}"
            
            # Check tables section
            tables = response_data['tables']
            expected_tables = ['res_partner', 'product_template', 'product_product', 
                             'stock_location', 'pos_order', 'pos_order_line']
            
            if len(tables) != 6:
                return f"Expected 6 table health checks, got {len(tables)}"
            
            table_names = [t.get('table') for t in tables]
            for expected in expected_tables:
                if expected not in table_names:
                    return f"Missing health check for table: {expected}"
            
            # Check pos_by_company section
            pos_by_company = response_data['pos_by_company']
            if len(pos_by_company) < 2:
                return f"Expected POS data for at least 2 companies, got {len(pos_by_company)}"
                
            company_keys = [p.get('company_key') for p in pos_by_company]
            if 'Ambission' not in company_keys or 'ProyectoModa' not in company_keys:
                return f"Expected Ambission and ProyectoModa companies, got: {company_keys}"
            
            # Check orphan_lines
            orphan_lines = response_data['orphan_lines']
            if orphan_lines != 0:
                return f"Expected 0 orphan lines for healthy system, got {orphan_lines}"
            
            # Check recent_errors structure
            recent_errors = response_data['recent_errors']
            print(f"   Tables health: {len(tables)} tables checked")
            print(f"   POS by company: {len(pos_by_company)} companies")
            print(f"   Orphan lines: {orphan_lines} (should be 0)")
            print(f"   Recent errors: {len(recent_errors)} errors")
            return True
        
        return self.run_test(
            "Health Check - System Monitoring",
            "GET",
            "health",
            200,
            check_response=check_health
        )

    def test_root_endpoint(self):
        """Test root API endpoint"""
        def check_root(response_data):
            if 'message' not in response_data:
                return "Root endpoint missing message"
            print(f"   Message: {response_data.get('message')}")
            return True
        
        return self.run_test(
            "Root API Endpoint",
            "GET",
            "",
            200,
            check_response=check_root
        )

def main():
    print("=== Odoo ODS Backend API Test Suite ===")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = OdooODSAPITester()
    
    # Run all tests in logical order
    print("\n" + "="*50)
    print("TESTING BACKEND API ENDPOINTS")
    print("="*50)
    
    # Test basic connectivity first
    tester.test_root_endpoint()
    tester.test_connection()
    
    # Test migration status (should show existing schema)
    tester.test_migration_status()
    
    # Test data retrieval endpoints
    tester.test_schema_tables()
    tester.test_sync_jobs() 
    tester.test_sync_logs()
    tester.test_schema_indexes()
    
    # Test migration execution (idempotent)
    tester.test_execute_migration()
    
    print("\n" + "="*50)
    print("TESTING VALIDATION ENDPOINTS")
    print("="*50)
    
    # Test new validation endpoints
    tester.test_stock_locations()
    tester.test_stock_locations_search()
    tester.test_pos_lines_full()
    tester.test_pos_lines_full_filters()
    tester.test_health_endpoint()
    
    # Re-test status after migration
    print("\n--- Re-testing status after migration ---")
    tester.test_migration_status()

    # Final results
    print("\n" + "="*50)
    print(f"FINAL RESULTS: {tester.tests_passed}/{tester.tests_run} tests passed")
    print("="*50)
    
    if tester.failures:
        print("\nFAILURES:")
        for i, failure in enumerate(tester.failures, 1):
            print(f"{i}. {failure}")
    else:
        print("\n✅ All tests passed!")
    
    success_rate = (tester.tests_passed / tester.tests_run) * 100 if tester.tests_run > 0 else 0
    print(f"\nSuccess rate: {success_rate:.1f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())