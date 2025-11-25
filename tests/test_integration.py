"""
Integration tests for MCP module with real sample data
"""
import pytest
import json
from app.services.mcp import MCPContextManager, get_database_schema, get_filesystem_metadata
from app.core.database import get_db_path
from app.core.config import settings


class TestMCPIntegration:
    """Integration tests using actual sample data"""
    
    def test_sample_database_extraction(self):
        """Test extraction from sample database"""
        schema = get_database_schema()
        
        # Verify pipeline tables exist
        table_names = [t["name"] for t in schema["tables"]]
        assert "Pipelines" in table_names
        assert "Pipeline_Steps" in table_names
        assert "Execution_Logs" in table_names
        assert "Repair_Logs" in table_names
        assert "Schema_Snapshots" in table_names
        
        # Verify sample data tables exist
        assert "orders" in table_names
        assert "products" in table_names
        
        print(f"✓ Extracted {len(schema['tables'])} tables")
    
    def test_sample_filesystem_extraction(self):
        """Test extraction from sample data directory"""
        metadata = get_filesystem_metadata()
        
        # Verify sample files exist
        file_paths = [f["path"] for f in metadata["files"]]
        assert "sales.csv" in file_paths
        assert "inventory.json" in file_paths
        assert "customers.csv" in file_paths
        
        # Verify file metadata
        sales_csv = next(f for f in metadata["files"] if f["path"] == "sales.csv")
        assert sales_csv["type"] == "csv"
        assert "headers" in sales_csv
        assert "order_id" in sales_csv["headers"]
        assert sales_csv["row_count_estimate"] > 0
        
        # Verify JSON metadata
        inventory_json = next(f for f in metadata["files"] if f["path"] == "inventory.json")
        assert inventory_json["type"] == "json"
        assert "structure" in inventory_json
        assert inventory_json["structure"]["root_type"] == "list"
        
        print(f"✓ Extracted {metadata['total_files']} files")
    
    def test_full_context_integration(self):
        """Test complete context generation with sample data"""
        mcp = MCPContextManager()
        context = mcp.get_full_context()
        
        # Verify structure
        assert "database" in context
        assert "filesystem" in context
        assert "metadata" in context
        
        # Verify database content
        db_tables = context["database"]["tables"]
        assert len(db_tables) >= 7  # At least 5 pipeline tables + 2 sample tables
        
        # Verify filesystem content
        assert context["filesystem"]["total_files"] >= 3  # At least 3 sample files
        
        # Verify metadata
        assert context["metadata"]["database_table_count"] >= 7
        assert context["metadata"]["filesystem_file_count"] >= 3
        
        print(f"✓ Full context: {context['metadata']['database_table_count']} tables, "
              f"{context['metadata']['filesystem_file_count']} files")
    
    def test_context_completeness(self):
        """Test that context contains all required information"""
        mcp = MCPContextManager()
        context = mcp.get_full_context()
        
        # Check database tables have required fields
        for table in context["database"]["tables"]:
            assert "name" in table
            assert "columns" in table
            assert "primary_keys" in table
            assert "foreign_keys" in table
            
            # Check columns have required fields
            for column in table["columns"]:
                assert "name" in column
                assert "type" in column
                assert "nullable" in column
                assert "primary_key" in column
        
        # Check files have required fields
        for file in context["filesystem"]["files"]:
            assert "path" in file
            assert "type" in file
            assert "size_bytes" in file
            assert "last_modified" in file
        
        print("✓ Context completeness verified")
    
    def test_no_hallucinations(self):
        """Verify no non-existent resources are reported"""
        mcp = MCPContextManager()
        context = mcp.get_full_context()
        
        # Verify all reported tables actually exist in schema
        schema = get_database_schema()
        schema_table_names = {t["name"] for t in schema["tables"]}
        context_table_names = {t["name"] for t in context["database"]["tables"]}
        
        assert context_table_names == schema_table_names
        
        # Verify all reported files actually exist
        import os
        for file in context["filesystem"]["files"]:
            assert os.path.exists(file["absolute_path"]), \
                f"File {file['path']} reported but doesn't exist"
        
        print("✓ No hallucinations detected")
    
    def test_context_validation(self):
        """Test context validation with real data"""
        mcp = MCPContextManager()
        context = mcp.get_full_context()
        
        is_valid, warnings = mcp.validate_context(context)
        
        assert is_valid is True
        print(f"✓ Context validation: valid={is_valid}, warnings={len(warnings)}")
        
        if warnings:
            for warning in warnings:
                print(f"  Warning: {warning}")
    
    @pytest.mark.asyncio
    async def test_async_integration(self):
        """Test async context generation with real data"""
        mcp = MCPContextManager()
        context = await mcp.get_full_context_async()
        
        assert "database" in context
        assert "filesystem" in context
        assert context["metadata"]["database_table_count"] >= 7
        assert context["metadata"]["filesystem_file_count"] >= 3
        
        print("✓ Async integration test passed")
    
    def test_performance_requirements(self):
        """Test that context generation meets performance requirements"""
        import time
        
        mcp = MCPContextManager()
        
        # Test context generation time (should be < 2 seconds)
        start_time = time.time()
        context = mcp.get_full_context(use_cache=False)
        elapsed = time.time() - start_time
        
        assert elapsed < 2.0, f"Context generation took {elapsed:.2f}s (required < 2s)"
        print(f"✓ Context generation: {elapsed:.3f}s (required < 2s)")
        
        # Test cache performance (cached call should be faster or similar)
        start_time = time.time()
        cached_context = mcp.get_full_context()
        cached_elapsed = time.time() - start_time
        
        # For very fast operations (<50ms), cache speedup may not be measurable
        if elapsed < 0.05:
            print(f"✓ Context generation very fast ({elapsed*1000:.1f}ms), cache speedup not measurable")
        else:
            speedup = (elapsed - cached_elapsed) / elapsed * 100
            assert speedup > 80, f"Cache speedup {speedup:.1f}% (required > 80%)"
            print(f"✓ Cache speedup: {speedup:.1f}% (required > 80%)")
    
    def test_csv_header_accuracy(self):
        """Test CSV header extraction accuracy"""
        metadata = get_filesystem_metadata()
        
        # Check sales.csv headers
        sales_csv = next(f for f in metadata["files"] if f["path"] == "sales.csv")
        expected_headers = ['order_id', 'customer', 'amount', 'date', 'region']
        assert sales_csv["headers"] == expected_headers
        
        # Check customers.csv headers
        customers_csv = next(f for f in metadata["files"] if f["path"] == "customers.csv")
        expected_customer_headers = ['customer_id', 'name', 'email', 'phone', 'country']
        assert customers_csv["headers"] == expected_customer_headers
        
        print("✓ CSV headers accurately extracted")
    
    def test_json_structure_accuracy(self):
        """Test JSON structure extraction accuracy"""
        metadata = get_filesystem_metadata()
        
        inventory_json = next(f for f in metadata["files"] if f["path"] == "inventory.json")
        structure = inventory_json["structure"]
        
        assert structure["root_type"] == "list"
        assert structure["array_length"] == 15
        assert "product_id" in structure["element_keys"]
        assert "stock_level" in structure["element_keys"]
        assert "warehouse_location" in structure["element_keys"]
        
        print("✓ JSON structure accurately extracted")


def run_integration_tests():
    """Run all integration tests and print summary"""
    print("\n" + "="*80)
    print("Running MCP Integration Tests with Sample Data")
    print("="*80 + "\n")
    
    test = TestMCPIntegration()
    
    tests = [
        ("Sample Database Extraction", test.test_sample_database_extraction),
        ("Sample Filesystem Extraction", test.test_sample_filesystem_extraction),
        ("Full Context Integration", test.test_full_context_integration),
        ("Context Completeness", test.test_context_completeness),
        ("No Hallucinations", test.test_no_hallucinations),
        ("Context Validation", test.test_context_validation),
        ("Performance Requirements", test.test_performance_requirements),
        ("CSV Header Accuracy", test.test_csv_header_accuracy),
        ("JSON Structure Accuracy", test.test_json_structure_accuracy),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            print(f"\n{name}:")
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            failed += 1
    
    print("\n" + "="*80)
    print(f"Integration Test Summary: {passed} passed, {failed} failed")
    print("="*80 + "\n")
    
    return passed, failed


if __name__ == "__main__":
    passed, failed = run_integration_tests()
    exit(0 if failed == 0 else 1)
