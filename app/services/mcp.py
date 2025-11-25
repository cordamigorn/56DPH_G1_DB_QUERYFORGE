"""
MCP (Model Context Protocol) Context Manager
Handles database schema and filesystem metadata extraction
"""
import os
import json
import csv
import sqlite3
import aiosqlite
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.core.config import settings
from app.core.database import get_db_path

logger = logging.getLogger(__name__)


def get_database_schema(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract complete database schema metadata
    
    Args:
        db_path: Path to SQLite database file (uses default if None)
        
    Returns:
        Dictionary containing complete database schema information
        
    Structure:
        {
            "tables": [
                {
                    "name": "table_name",
                    "columns": [
                        {
                            "name": "column_name",
                            "type": "data_type",
                            "nullable": true/false,
                            "primary_key": true/false,
                            "default_value": "value or null"
                        }
                    ],
                    "primary_keys": ["column_name"],
                    "foreign_keys": [
                        {
                            "column": "local_column",
                            "referenced_table": "foreign_table",
                            "referenced_column": "foreign_column",
                            "on_delete": "action",
                            "on_update": "action"
                        }
                    ]
                }
            ]
        }
    """
    if db_path is None:
        db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get all user tables (exclude system tables)
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        
        table_names = [row[0] for row in cursor.fetchall()]
        
        tables = []
        for table_name in table_names:
            table_info = {
                "name": table_name,
                "columns": [],
                "primary_keys": [],
                "foreign_keys": []
            }
            
            # Get column information using PRAGMA table_info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            
            for col in columns_info:
                # col: (cid, name, type, notnull, dflt_value, pk)
                column = {
                    "name": col[1],
                    "type": col[2],
                    "nullable": not bool(col[3]),
                    "primary_key": bool(col[5]),
                    "default_value": col[4]
                }
                table_info["columns"].append(column)
                
                # Track primary keys
                if col[5]:  # pk flag
                    table_info["primary_keys"].append(col[1])
            
            # Get foreign key information using PRAGMA foreign_key_list
            cursor.execute(f"PRAGMA foreign_key_list({table_name})")
            fk_info = cursor.fetchall()
            
            for fk in fk_info:
                # fk: (id, seq, table, from, to, on_update, on_delete, match)
                foreign_key = {
                    "column": fk[3],
                    "referenced_table": fk[2],
                    "referenced_column": fk[4],
                    "on_update": fk[5] or "NO ACTION",
                    "on_delete": fk[6] or "NO ACTION"
                }
                table_info["foreign_keys"].append(foreign_key)
            
            tables.append(table_info)
        
        conn.close()
        
        result = {"tables": tables}
        logger.info(f"Extracted schema for {len(tables)} tables")
        return result
        
    except Exception as e:
        logger.error(f"Error extracting database schema: {e}")
        return {
            "tables": [],
            "error": str(e)
        }


async def get_database_schema_async(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract complete database schema metadata asynchronously
    
    Args:
        db_path: Path to SQLite database file (uses default if None)
        
    Returns:
        Dictionary containing complete database schema information
    """
    if db_path is None:
        db_path = get_db_path()
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Get all user tables
            async with db.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """) as cursor:
                rows = await cursor.fetchall()
                table_names = [row[0] for row in rows]
            
            tables = []
            for table_name in table_names:
                table_info = {
                    "name": table_name,
                    "columns": [],
                    "primary_keys": [],
                    "foreign_keys": []
                }
                
                # Get column information
                async with db.execute(f"PRAGMA table_info({table_name})") as cursor:
                    columns_info = await cursor.fetchall()
                
                for col in columns_info:
                    column = {
                        "name": col[1],
                        "type": col[2],
                        "nullable": not bool(col[3]),
                        "primary_key": bool(col[5]),
                        "default_value": col[4]
                    }
                    table_info["columns"].append(column)
                    
                    if col[5]:
                        table_info["primary_keys"].append(col[1])
                
                # Get foreign key information
                async with db.execute(f"PRAGMA foreign_key_list({table_name})") as cursor:
                    fk_info = await cursor.fetchall()
                
                for fk in fk_info:
                    foreign_key = {
                        "column": fk[3],
                        "referenced_table": fk[2],
                        "referenced_column": fk[4],
                        "on_update": fk[5] or "NO ACTION",
                        "on_delete": fk[6] or "NO ACTION"
                    }
                    table_info["foreign_keys"].append(foreign_key)
                
                tables.append(table_info)
            
            result = {"tables": tables}
            logger.info(f"Extracted schema for {len(tables)} tables (async)")
            return result
            
    except Exception as e:
        logger.error(f"Error extracting database schema (async): {e}")
        return {
            "tables": [],
            "error": str(e)
        }


def get_filesystem_metadata(root_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract filesystem metadata including file information and structure
    
    Args:
        root_directory: Root path for scanning (uses DATA_DIRECTORY if None)
        
    Returns:
        Dictionary containing filesystem metadata
        
    Structure:
        {
            "root_path": "/absolute/path/to/data",
            "files": [
                {
                    "path": "relative/path/file.csv",
                    "absolute_path": "/absolute/path/to/data/file.csv",
                    "type": "csv",
                    "size_bytes": 1024,
                    "last_modified": "2025-01-15T10:30:00Z",
                    "headers": ["col1", "col2", ...],  # For CSV
                    "row_count_estimate": 100,  # For CSV
                    "structure": {...}  # For JSON
                }
            ],
            "total_files": 2,
            "scan_timestamp": "2025-01-15T11:00:00Z"
        }
    """
    if root_directory is None:
        root_directory = settings.DATA_DIRECTORY
    
    root_path = os.path.abspath(root_directory)
    
    if not os.path.exists(root_path):
        logger.warning(f"Data directory not found: {root_path}")
        return {
            "root_path": root_path,
            "files": [],
            "total_files": 0,
            "scan_timestamp": datetime.now().isoformat(),
            "error": f"Directory not found: {root_path}"
        }
    
    files = []
    errors = []
    
    try:
        # Walk through directory tree
        for dirpath, dirnames, filenames in os.walk(root_path):
            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                relative_path = os.path.relpath(file_path, root_path)
                
                try:
                    # Get file stats
                    file_stat = os.stat(file_path)
                    file_info = {
                        "path": relative_path.replace('\\', '/'),  # Normalize path separators
                        "absolute_path": file_path,
                        "size_bytes": file_stat.st_size,
                        "last_modified": datetime.fromtimestamp(file_stat.st_mtime).isoformat()
                    }
                    
                    # Determine file type and extract metadata
                    _, ext = os.path.splitext(filename)
                    ext = ext.lower()
                    
                    if ext == '.csv':
                        file_info["type"] = "csv"
                        csv_metadata = extract_csv_metadata(file_path)
                        file_info.update(csv_metadata)
                        
                    elif ext == '.json':
                        file_info["type"] = "json"
                        json_metadata = extract_json_metadata(file_path)
                        file_info.update(json_metadata)
                        
                    elif ext in ['.txt', '.log']:
                        file_info["type"] = "text"
                        text_metadata = extract_text_metadata(file_path)
                        file_info.update(text_metadata)
                        
                    else:
                        file_info["type"] = "other"
                    
                    files.append(file_info)
                    
                except Exception as e:
                    logger.warning(f"Error processing file {filename}: {e}")
                    errors.append({
                        "file": relative_path,
                        "error": str(e)
                    })
        
        result = {
            "root_path": root_path,
            "files": files,
            "total_files": len(files),
            "scan_timestamp": datetime.now().isoformat()
        }
        
        if errors:
            result["errors"] = errors
        
        logger.info(f"Scanned {len(files)} files in {root_path}")
        return result
        
    except Exception as e:
        logger.error(f"Error scanning filesystem: {e}")
        return {
            "root_path": root_path,
            "files": [],
            "total_files": 0,
            "scan_timestamp": datetime.now().isoformat(),
            "error": str(e)
        }


def extract_csv_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from CSV file
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Dictionary with CSV metadata (headers, delimiter, row count estimate)
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            # Read first few lines to detect delimiter and headers
            sample = f.read(8192)  # Read first 8KB
            f.seek(0)
            
            # Detect delimiter
            sniffer = csv.Sniffer()
            try:
                dialect = sniffer.sniff(sample)
                delimiter = dialect.delimiter
            except:
                delimiter = ','  # Default to comma
            
            # Read headers
            reader = csv.reader(f, delimiter=delimiter)
            try:
                headers = next(reader)
                headers = [h.strip() for h in headers if h.strip()]
            except StopIteration:
                headers = []
            
            # Count rows (estimate from first chunk)
            f.seek(0)
            row_count = sum(1 for _ in f) - 1  # Subtract header row
        
        return {
            "headers": headers,
            "delimiter": delimiter,
            "row_count_estimate": max(0, row_count)
        }
        
    except Exception as e:
        logger.warning(f"Error extracting CSV metadata from {file_path}: {e}")
        return {
            "headers": [],
            "error": str(e)
        }


def extract_json_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from JSON file
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Dictionary with JSON structure metadata
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        structure = {
            "root_type": type(data).__name__
        }
        
        if isinstance(data, dict):
            structure["keys"] = list(data.keys())
        elif isinstance(data, list):
            structure["array_length"] = len(data)
            if data and isinstance(data[0], dict):
                structure["element_keys"] = list(data[0].keys())
        
        return {"structure": structure}
        
    except Exception as e:
        logger.warning(f"Error extracting JSON metadata from {file_path}: {e}")
        return {
            "structure": {},
            "error": str(e)
        }


def extract_text_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from text file
    
    Args:
        file_path: Path to text file
        
    Returns:
        Dictionary with text file metadata
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        
        return {
            "line_count": len(lines),
            "encoding": "utf-8"
        }
        
    except Exception as e:
        logger.warning(f"Error extracting text metadata from {file_path}: {e}")
        return {
            "line_count": 0,
            "error": str(e)
        }


class MCPContextManager:
    """
    Model Context Protocol Context Manager
    
    Orchestrates database and filesystem metadata extraction with caching
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        data_directory: Optional[str] = None,
        cache_ttl_seconds: int = 300
    ):
        """
        Initialize MCP Context Manager
        
        Args:
            db_path: Database file path (uses default if None)
            data_directory: Data directory path (uses default if None)
            cache_ttl_seconds: Cache time-to-live in seconds (default: 300)
        """
        self.db_path = db_path or get_db_path()
        self.data_directory = data_directory or settings.DATA_DIRECTORY
        self.cache_ttl_seconds = cache_ttl_seconds
        
        # Cache storage
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
    
    def _is_cache_valid(self) -> bool:
        """
        Check if cached context is still valid
        
        Returns:
            bool: True if cache is valid and not expired
        """
        if self._cache is None or self._cache_timestamp is None:
            return False
        
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self.cache_ttl_seconds
    
    def get_full_context(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get complete system context combining database and filesystem metadata
        
        Args:
            use_cache: Whether to use cached context if available (default: True)
            
        Returns:
            Dictionary containing complete system context
            
        Structure:
            {
                "database": { ... },
                "filesystem": { ... },
                "metadata": {
                    "context_generated_at": "timestamp",
                    "database_table_count": int,
                    "filesystem_file_count": int,
                    "cache_status": "fresh/stale/disabled"
                }
            }
        """
        # Check cache
        if use_cache and self._is_cache_valid():
            logger.info("Using cached context")
            cache_status = "fresh"
            context = self._cache.copy()
            context["metadata"]["cache_status"] = cache_status
            return context
        
        # Generate new context
        logger.info("Generating new context")
        
        # Extract database schema
        database_metadata = get_database_schema(self.db_path)
        
        # Extract filesystem metadata
        filesystem_metadata = get_filesystem_metadata(self.data_directory)
        
        # Build complete context
        context = {
            "database": database_metadata,
            "filesystem": filesystem_metadata,
            "metadata": {
                "context_generated_at": datetime.now().isoformat(),
                "database_table_count": len(database_metadata.get("tables", [])),
                "filesystem_file_count": filesystem_metadata.get("total_files", 0),
                "cache_status": "disabled" if not use_cache else "stale"
            }
        }
        
        # Validate context
        is_valid, warnings = self.validate_context(context)
        if warnings:
            context["metadata"]["warnings"] = warnings
        
        # Update cache
        if use_cache:
            self._cache = context.copy()
            self._cache_timestamp = datetime.now()
            logger.info("Context cached")
        
        return context
    
    async def get_full_context_async(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get complete system context asynchronously
        
        Args:
            use_cache: Whether to use cached context if available (default: True)
            
        Returns:
            Dictionary containing complete system context
        """
        # Check cache
        if use_cache and self._is_cache_valid():
            logger.info("Using cached context (async)")
            cache_status = "fresh"
            context = self._cache.copy()
            context["metadata"]["cache_status"] = cache_status
            return context
        
        # Generate new context
        logger.info("Generating new context (async)")
        
        # Extract database schema asynchronously
        database_metadata = await get_database_schema_async(self.db_path)
        
        # Extract filesystem metadata (synchronous, but fast)
        filesystem_metadata = get_filesystem_metadata(self.data_directory)
        
        # Build complete context
        context = {
            "database": database_metadata,
            "filesystem": filesystem_metadata,
            "metadata": {
                "context_generated_at": datetime.now().isoformat(),
                "database_table_count": len(database_metadata.get("tables", [])),
                "filesystem_file_count": filesystem_metadata.get("total_files", 0),
                "cache_status": "disabled" if not use_cache else "stale"
            }
        }
        
        # Validate context
        is_valid, warnings = self.validate_context(context)
        if warnings:
            context["metadata"]["warnings"] = warnings
        
        # Update cache
        if use_cache:
            self._cache = context.copy()
            self._cache_timestamp = datetime.now()
            logger.info("Context cached (async)")
        
        return context
    
    def refresh_cache(self) -> Dict[str, Any]:
        """
        Force cache invalidation and context re-extraction
        
        Returns:
            Newly generated context
        """
        logger.info("Forcing cache refresh")
        return self.get_full_context(use_cache=False)
    
    async def refresh_cache_async(self) -> Dict[str, Any]:
        """
        Force cache invalidation and context re-extraction (async)
        
        Returns:
            Newly generated context
        """
        logger.info("Forcing cache refresh (async)")
        return await self.get_full_context_async(use_cache=False)
    
    def validate_context(self, context: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate context completeness and integrity
        
        Args:
            context: Context dictionary to validate
            
        Returns:
            Tuple of (is_valid, warnings)
        """
        warnings = []
        
        # Check if at least one source has data
        has_database = len(context.get("database", {}).get("tables", [])) > 0
        has_filesystem = context.get("filesystem", {}).get("total_files", 0) > 0
        
        if not has_database and not has_filesystem:
            warnings.append("No database tables or filesystem data found")
        
        # Check for errors in extraction
        if "error" in context.get("database", {}):
            warnings.append(f"Database extraction error: {context['database']['error']}")
        
        if "error" in context.get("filesystem", {}):
            warnings.append(f"Filesystem extraction error: {context['filesystem']['error']}")
        
        # Check for file extraction errors
        if "errors" in context.get("filesystem", {}):
            error_count = len(context["filesystem"]["errors"])
            warnings.append(f"{error_count} file(s) had extraction errors")
        
        is_valid = len(warnings) == 0 or (has_database or has_filesystem)
        
        return is_valid, warnings
    
    def clear_cache(self) -> None:
        """
        Clear cached context
        """
        self._cache = None
        self._cache_timestamp = None
        logger.info("Cache cleared")
    
    def get_cache_age_seconds(self) -> Optional[float]:
        """
        Get age of cached context in seconds
        
        Returns:
            Age in seconds, or None if no cache exists
        """
        if self._cache_timestamp is None:
            return None
        
        return (datetime.now() - self._cache_timestamp).total_seconds()


# Test functions
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("Testing database schema extraction...")
    db_schema = get_database_schema()
    print(json.dumps(db_schema, indent=2)[:500] + "...\n")
    
    print("="*80)
    
    print("\nTesting filesystem metadata extraction...")
    fs_metadata = get_filesystem_metadata()
    print(json.dumps(fs_metadata, indent=2)[:500] + "...\n")
    
    print("="*80)
    
    print("\nTesting MCPContextManager...")
    mcp = MCPContextManager(cache_ttl_seconds=60)
    
    print("\n1. Getting full context (fresh):")
    context = mcp.get_full_context()
    print(f"  - Database tables: {context['metadata']['database_table_count']}")
    print(f"  - Filesystem files: {context['metadata']['filesystem_file_count']}")
    print(f"  - Cache status: {context['metadata']['cache_status']}")
    
    print("\n2. Getting full context (cached):")
    context2 = mcp.get_full_context()
    print(f"  - Cache status: {context2['metadata']['cache_status']}")
    print(f"  - Cache age: {mcp.get_cache_age_seconds():.2f} seconds")
    
    print("\n3. Refreshing cache:")
    context3 = mcp.refresh_cache()
    print(f"  - Cache status: {context3['metadata']['cache_status']}")
    
    print("\n4. Validating context:")
    is_valid, warnings = mcp.validate_context(context)
    print(f"  - Valid: {is_valid}")
    print(f"  - Warnings: {warnings if warnings else 'None'}")
    
    print("\n✅ MCPContextManager test complete!")
