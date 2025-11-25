"""
Unit tests for MCP (Model Context Protocol) module
"""
import pytest
import os
import json
import csv
import tempfile
import shutil
import sqlite3
from datetime import datetime
import time

from app.services.mcp import (
    get_database_schema,
    get_filesystem_metadata,
    extract_csv_metadata,
    extract_json_metadata,
    extract_text_metadata,
    MCPContextManager
)


@pytest.fixture
def temp_db():
    """Create a temporary test database"""
    # Create temporary database file
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)
    
    # Create test schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create test tables
    cursor.execute("""
        CREATE TABLE test_table (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            value DECIMAL(10, 2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE related_table (
            id INTEGER PRIMARY KEY,
            test_id INTEGER NOT NULL,
            description TEXT,
            FOREIGN KEY (test_id) REFERENCES test_table(id) ON DELETE CASCADE
        )
    """)
    
    # Insert test data
    cursor.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("Test1", 100.50))
    cursor.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("Test2", 200.75))
    
    conn.commit()
    conn.close()
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory with test files"""
    temp_dir = tempfile.mkdtemp()
    
    # Create test CSV file
    csv_path = os.path.join(temp_dir, "test.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'name', 'value'])
        writer.writerow([1, 'Alice', 100])
        writer.writerow([2, 'Bob', 200])
        writer.writerow([3, 'Charlie', 300])
    
    # Create test JSON file
    json_path = os.path.join(temp_dir, "test.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "config": "test",
            "items": [1, 2, 3]
        }, f)
    
    # Create test JSON array file
    json_array_path = os.path.join(temp_dir, "array.json")
    with open(json_array_path, 'w', encoding='utf-8') as f:
        json.dump([
            {"id": 1, "name": "Item1"},
            {"id": 2, "name": "Item2"}
        ], f)
    
    # Create test text file
    txt_path = os.path.join(temp_dir, "test.txt")
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write("Line 1\nLine 2\nLine 3\n")
    
    # Create subdirectory with file
    subdir = os.path.join(temp_dir, "subdir")
    os.makedirs(subdir)
    sub_csv_path = os.path.join(subdir, "sub.csv")
    with open(sub_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['col1', 'col2'])
        writer.writerow(['a', 'b'])
    
    yield temp_dir
    
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


class TestDatabaseSchemaExtraction:
    """Tests for database schema extraction"""
    
    def test_extract_tables(self, temp_db):
        """Test extraction of table names"""
        schema = get_database_schema(temp_db)
        
        assert "tables" in schema
        table_names = [t["name"] for t in schema["tables"]]
        assert "test_table" in table_names
        assert "related_table" in table_names
    
    def test_extract_columns(self, temp_db):
        """Test extraction of column information"""
        schema = get_database_schema(temp_db)
        
        test_table = next(t for t in schema["tables"] if t["name"] == "test_table")
        column_names = [c["name"] for c in test_table["columns"]]
        
        assert "id" in column_names
        assert "name" in column_names
        assert "value" in column_names
        assert "created_at" in column_names
    
    def test_column_properties(self, temp_db):
        """Test column property extraction"""
        schema = get_database_schema(temp_db)
        
        test_table = next(t for t in schema["tables"] if t["name"] == "test_table")
        id_column = next(c for c in test_table["columns"] if c["name"] == "id")
        name_column = next(c for c in test_table["columns"] if c["name"] == "name")
        
        # Check primary key
        assert id_column["primary_key"] is True
        assert name_column["primary_key"] is False
        
        # Check nullable
        assert name_column["nullable"] is False
    
    def test_primary_keys(self, temp_db):
        """Test primary key extraction"""
        schema = get_database_schema(temp_db)
        
        test_table = next(t for t in schema["tables"] if t["name"] == "test_table")
        assert "id" in test_table["primary_keys"]
    
    def test_foreign_keys(self, temp_db):
        """Test foreign key extraction"""
        schema = get_database_schema(temp_db)
        
        related_table = next(t for t in schema["tables"] if t["name"] == "related_table")
        assert len(related_table["foreign_keys"]) > 0
        
        fk = related_table["foreign_keys"][0]
        assert fk["column"] == "test_id"
        assert fk["referenced_table"] == "test_table"
        assert fk["referenced_column"] == "id"
    
    def test_empty_database(self):
        """Test extraction from empty database"""
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create empty database
        conn = sqlite3.connect(db_path)
        conn.close()
        
        try:
            schema = get_database_schema(db_path)
            assert "tables" in schema
            assert len(schema["tables"]) == 0
        finally:
            os.unlink(db_path)
    
    def test_nonexistent_database(self):
        """Test handling of nonexistent database"""
        schema = get_database_schema("/nonexistent/path.db")
        assert "error" in schema


class TestFilesystemMetadataExtraction:
    """Tests for filesystem metadata extraction"""
    
    def test_file_discovery(self, temp_data_dir):
        """Test that all files are discovered"""
        metadata = get_filesystem_metadata(temp_data_dir)
        
        assert metadata["total_files"] == 5
        assert "files" in metadata
    
    def test_csv_detection(self, temp_data_dir):
        """Test CSV file type detection"""
        metadata = get_filesystem_metadata(temp_data_dir)
        
        csv_files = [f for f in metadata["files"] if f["type"] == "csv"]
        assert len(csv_files) == 2
    
    def test_json_detection(self, temp_data_dir):
        """Test JSON file type detection"""
        metadata = get_filesystem_metadata(temp_data_dir)
        
        json_files = [f for f in metadata["files"] if f["type"] == "json"]
        assert len(json_files) == 2
    
    def test_file_properties(self, temp_data_dir):
        """Test file property extraction"""
        metadata = get_filesystem_metadata(temp_data_dir)
        
        test_csv = next(f for f in metadata["files"] if f["path"] == "test.csv")
        
        assert "size_bytes" in test_csv
        assert test_csv["size_bytes"] > 0
        assert "last_modified" in test_csv
        assert "absolute_path" in test_csv
    
    def test_subdirectory_scanning(self, temp_data_dir):
        """Test recursive directory scanning"""
        metadata = get_filesystem_metadata(temp_data_dir)
        
        subdir_files = [f for f in metadata["files"] if "subdir" in f["path"]]
        assert len(subdir_files) == 1
    
    def test_nonexistent_directory(self):
        """Test handling of nonexistent directory"""
        metadata = get_filesystem_metadata("/nonexistent/directory")
        assert "error" in metadata
        assert metadata["total_files"] == 0


class TestCSVMetadataExtraction:
    """Tests for CSV metadata extraction"""
    
    def test_header_extraction(self, temp_data_dir):
        """Test CSV header extraction"""
        csv_path = os.path.join(temp_data_dir, "test.csv")
        metadata = extract_csv_metadata(csv_path)
        
        assert "headers" in metadata
        assert metadata["headers"] == ['id', 'name', 'value']
    
    def test_row_count(self, temp_data_dir):
        """Test CSV row count estimation"""
        csv_path = os.path.join(temp_data_dir, "test.csv")
        metadata = extract_csv_metadata(csv_path)
        
        assert "row_count_estimate" in metadata
        assert metadata["row_count_estimate"] == 3
    
    def test_delimiter_detection(self, temp_data_dir):
        """Test CSV delimiter detection"""
        csv_path = os.path.join(temp_data_dir, "test.csv")
        metadata = extract_csv_metadata(csv_path)
        
        assert "delimiter" in metadata
        assert metadata["delimiter"] == ','
    
    def test_empty_csv(self, temp_data_dir):
        """Test handling of empty CSV"""
        empty_csv = os.path.join(temp_data_dir, "empty.csv")
        with open(empty_csv, 'w') as f:
            pass
        
        metadata = extract_csv_metadata(empty_csv)
        assert metadata["row_count_estimate"] == 0


class TestJSONMetadataExtraction:
    """Tests for JSON metadata extraction"""
    
    def test_object_structure(self, temp_data_dir):
        """Test JSON object structure extraction"""
        json_path = os.path.join(temp_data_dir, "test.json")
        metadata = extract_json_metadata(json_path)
        
        assert "structure" in metadata
        assert metadata["structure"]["root_type"] == "dict"
        assert "config" in metadata["structure"]["keys"]
        assert "items" in metadata["structure"]["keys"]
    
    def test_array_structure(self, temp_data_dir):
        """Test JSON array structure extraction"""
        json_path = os.path.join(temp_data_dir, "array.json")
        metadata = extract_json_metadata(json_path)
        
        assert metadata["structure"]["root_type"] == "list"
        assert metadata["structure"]["array_length"] == 2
        assert "element_keys" in metadata["structure"]
        assert "id" in metadata["structure"]["element_keys"]
    
    def test_malformed_json(self, temp_data_dir):
        """Test handling of malformed JSON"""
        malformed_path = os.path.join(temp_data_dir, "malformed.json")
        with open(malformed_path, 'w') as f:
            f.write("{invalid json")
        
        metadata = extract_json_metadata(malformed_path)
        assert "error" in metadata


class TestTextMetadataExtraction:
    """Tests for text metadata extraction"""
    
    def test_line_count(self, temp_data_dir):
        """Test text file line count"""
        txt_path = os.path.join(temp_data_dir, "test.txt")
        metadata = extract_text_metadata(txt_path)
        
        assert "line_count" in metadata
        assert metadata["line_count"] == 3


class TestMCPContextManager:
    """Tests for MCPContextManager class"""
    
    def test_initialization(self, temp_db, temp_data_dir):
        """Test MCPContextManager initialization"""
        mcp = MCPContextManager(
            db_path=temp_db,
            data_directory=temp_data_dir,
            cache_ttl_seconds=60
        )
        
        assert mcp.db_path == temp_db
        assert mcp.data_directory == temp_data_dir
        assert mcp.cache_ttl_seconds == 60
    
    def test_get_full_context(self, temp_db, temp_data_dir):
        """Test full context generation"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        context = mcp.get_full_context()
        
        assert "database" in context
        assert "filesystem" in context
        assert "metadata" in context
        
        assert context["metadata"]["database_table_count"] == 2
        assert context["metadata"]["filesystem_file_count"] == 5
    
    def test_caching_behavior(self, temp_db, temp_data_dir):
        """Test context caching"""
        mcp = MCPContextManager(
            db_path=temp_db,
            data_directory=temp_data_dir,
            cache_ttl_seconds=60
        )
        
        # First call should generate new context
        context1 = mcp.get_full_context()
        assert context1["metadata"]["cache_status"] == "stale"
        
        # Second call should use cache
        context2 = mcp.get_full_context()
        assert context2["metadata"]["cache_status"] == "fresh"
        
        # Cache age should be small
        cache_age = mcp.get_cache_age_seconds()
        assert cache_age is not None
        assert cache_age < 1  # Less than 1 second
    
    def test_cache_expiration(self, temp_db, temp_data_dir):
        """Test cache expiration"""
        mcp = MCPContextManager(
            db_path=temp_db,
            data_directory=temp_data_dir,
            cache_ttl_seconds=1  # 1 second TTL
        )
        
        # First call
        context1 = mcp.get_full_context()
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Second call should regenerate
        context2 = mcp.get_full_context()
        assert context2["metadata"]["cache_status"] == "stale"
    
    def test_refresh_cache(self, temp_db, temp_data_dir):
        """Test manual cache refresh"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        
        # Initial context
        context1 = mcp.get_full_context()
        
        # Force refresh
        context2 = mcp.refresh_cache()
        assert context2["metadata"]["cache_status"] == "disabled"
    
    def test_clear_cache(self, temp_db, temp_data_dir):
        """Test cache clearing"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        
        # Generate context
        mcp.get_full_context()
        assert mcp.get_cache_age_seconds() is not None
        
        # Clear cache
        mcp.clear_cache()
        assert mcp.get_cache_age_seconds() is None
    
    def test_validate_context_valid(self, temp_db, temp_data_dir):
        """Test context validation with valid data"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        context = mcp.get_full_context()
        
        is_valid, warnings = mcp.validate_context(context)
        assert is_valid is True
        assert len(warnings) == 0
    
    def test_validate_context_empty(self):
        """Test context validation with empty data"""
        mcp = MCPContextManager()
        
        empty_context = {
            "database": {"tables": []},
            "filesystem": {"total_files": 0},
            "metadata": {}
        }
        
        is_valid, warnings = mcp.validate_context(empty_context)
        assert len(warnings) > 0
        assert any("No database tables" in w for w in warnings)
    
    def test_disable_caching(self, temp_db, temp_data_dir):
        """Test getting context without caching"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        
        context1 = mcp.get_full_context(use_cache=False)
        assert context1["metadata"]["cache_status"] == "disabled"
        
        context2 = mcp.get_full_context(use_cache=False)
        assert context2["metadata"]["cache_status"] == "disabled"
        
        # Cache should remain empty
        assert mcp.get_cache_age_seconds() is None


@pytest.mark.asyncio
class TestMCPAsyncMethods:
    """Tests for async MCP methods"""
    
    async def test_get_full_context_async(self, temp_db, temp_data_dir):
        """Test async full context generation"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        context = await mcp.get_full_context_async()
        
        assert "database" in context
        assert "filesystem" in context
        assert context["metadata"]["database_table_count"] == 2
    
    async def test_async_caching(self, temp_db, temp_data_dir):
        """Test async context caching"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        
        context1 = await mcp.get_full_context_async()
        assert context1["metadata"]["cache_status"] == "stale"
        
        context2 = await mcp.get_full_context_async()
        assert context2["metadata"]["cache_status"] == "fresh"
    
    async def test_refresh_cache_async(self, temp_db, temp_data_dir):
        """Test async cache refresh"""
        mcp = MCPContextManager(db_path=temp_db, data_directory=temp_data_dir)
        
        context = await mcp.refresh_cache_async()
        assert "database" in context
        assert "filesystem" in context
