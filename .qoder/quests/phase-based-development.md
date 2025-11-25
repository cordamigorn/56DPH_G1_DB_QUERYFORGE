# QueryForge - Phase 0 & Phase 1 Development Design

## Design Scope

This design document provides comprehensive implementation guidance for:
- **Phase 0**: Project Setup & Foundation
- **Phase 1**: MCP Context Manager

These phases establish the foundational infrastructure and core context gathering capabilities required for QueryForge's automated data pipeline generation system.

---

## Phase 0: Project Setup & Foundation

### Objective

Establish a production-ready development environment with complete project structure, database schema, and all necessary dependencies configured for subsequent module development.

### Environment Requirements

| Component | Specification | Validation Method |
|-----------|--------------|-------------------|
| Python Version | 3.10 or higher | Execute `python --version` and verify output |
| Virtual Environment | Isolated Python environment | Confirm activation shows environment name in shell prompt |
| Package Manager | pip (latest stable) | Execute `pip --version` |
| Database Engine | SQLite 3.40+ | Execute `sqlite3 --version` |

### Virtual Environment Setup Strategy

The virtual environment isolates project dependencies from system-wide Python packages, preventing version conflicts and ensuring reproducibility.

**Setup Process:**

1. Navigate to project root directory: `c:\Users\efese\OneDrive\Masaüstü\labcod`
2. Create virtual environment named `venv`
3. Activate virtual environment using platform-specific activation script
4. Verify activation by checking Python interpreter path points to virtual environment
5. Upgrade pip to latest version within virtual environment

**Activation Verification:**
- Shell prompt displays environment indicator
- Python executable path contains virtual environment directory
- pip list shows minimal base packages only

### Core Dependencies Specification

All dependencies must be pinned to compatible versions ensuring stability and reproducibility.

| Package | Minimum Version | Purpose |
|---------|----------------|---------|
| FastAPI | 0.104.0 | REST API framework with async support |
| uvicorn | 0.24.0 | ASGI server for FastAPI application |
| pydantic | 2.5.0 | Data validation and settings management |
| google-generativeai | 0.3.0 | Gemini API SDK for LLM integration |
| python-dotenv | 1.0.0 | Environment variable management |
| pytest | 7.4.0 | Testing framework |
| pytest-asyncio | 0.21.0 | Async test support |
| aiosqlite | 0.19.0 | Async SQLite database adapter |

**Requirements File Structure:**

The requirements.txt file should list all packages with exact version pins using the `==` operator to ensure deterministic installations across environments.

### Project Directory Structure

```
queryforge/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── pipeline.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mcp.py
│   │   ├── llm.py
│   │   ├── synthesizer.py
│   │   ├── sandbox.py
│   │   ├── repair.py
│   │   └── commit.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── data/
├── sandbox/
├── tests/
│   ├── __init__.py
│   ├── test_mcp.py
│   ├── test_llm.py
│   └── test_database.py
├── .env
├── .gitignore
├── requirements.txt
└── README.md
```

**Directory Purpose Definitions:**

- **app/**: Contains all application source code
- **app/api/routes/**: API endpoint definitions organized by resource
- **app/core/**: Core configuration and database connection management
- **app/models/**: Pydantic schemas for request/response validation
- **app/services/**: Business logic modules for each major component
- **app/utils/**: Shared helper functions and utilities
- **data/**: Storage location for test data files (CSV, JSON)
- **sandbox/**: Isolated workspace for pipeline execution
- **tests/**: All test files following pytest conventions

### Configuration Management Design

Configuration must be externalized from code, supporting multiple environments while protecting sensitive credentials.

**Configuration Parameters:**

| Parameter | Type | Purpose | Example |
|-----------|------|---------|---------|
| DATABASE_URL | String | SQLite database file path | sqlite:///./queryforge.db |
| GEMINI_API_KEY | String (Secret) | Google Gemini API authentication | AIza... |
| DATA_DIRECTORY | String | Root path for data files | ./data |
| SANDBOX_DIRECTORY | String | Isolated execution workspace | ./sandbox |
| MAX_REPAIR_ATTEMPTS | Integer | Repair loop limit | 3 |
| SANDBOX_TIMEOUT_SECONDS | Integer | Per-step execution timeout | 10 |
| ALLOWED_BASH_COMMANDS | List[String] | Whitelisted shell commands | awk,sed,cp,mv,curl |

**Configuration Loading Strategy:**

1. Read environment variables from .env file using python-dotenv
2. Parse and validate all required parameters
3. Provide sensible defaults for optional parameters
4. Raise explicit errors for missing required credentials
5. Expose configuration as singleton accessible throughout application

**Environment File Security:**

The .env file contains sensitive credentials and must be:
- Excluded from version control via .gitignore
- Stored with restricted file permissions
- Never logged or exposed in error messages
- Documented with .env.example template showing required variables

### Database Schema Implementation

The database schema implements complete traceability for pipeline lifecycle management, execution history, and repair operations.

#### Table: Pipelines

Stores pipeline metadata and current execution status.

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique pipeline identifier |
| user_id | INTEGER | NOT NULL | User who created the pipeline |
| prompt_text | TEXT | NOT NULL | Original natural-language request |
| status | VARCHAR(50) | NOT NULL DEFAULT 'pending' | Current pipeline state |
| created_at | TIMESTAMP | NOT NULL DEFAULT CURRENT_TIMESTAMP | Pipeline creation time |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last modification time |

**Status Values:** pending, running, success, failed, repaired

**Indexes:**
- INDEX idx_pipelines_user_id ON Pipelines(user_id)
- INDEX idx_pipelines_status ON Pipelines(status)

#### Table: Pipeline_Steps

Individual executable steps comprising a pipeline.

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique step identifier |
| pipeline_id | INTEGER | FOREIGN KEY REFERENCES Pipelines(id) ON DELETE CASCADE | Parent pipeline reference |
| step_number | INTEGER | NOT NULL | Execution order (1-based) |
| code_type | VARCHAR(10) | NOT NULL CHECK(code_type IN ('bash', 'sql')) | Step execution type |
| script_content | TEXT | NOT NULL | Executable code content |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Step creation time |

**Constraints:**
- UNIQUE(pipeline_id, step_number) - Prevent duplicate step numbers within pipeline

**Indexes:**
- INDEX idx_steps_pipeline ON Pipeline_Steps(pipeline_id)

#### Table: Schema_Snapshots

Pre-execution snapshots of database and filesystem state.

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique snapshot identifier |
| pipeline_id | INTEGER | FOREIGN KEY REFERENCES Pipelines(id) ON DELETE CASCADE | Associated pipeline |
| db_structure | JSON | NOT NULL | Complete database schema at snapshot time |
| file_list | JSON | NOT NULL | Filesystem state at snapshot time |
| snapshot_time | TIMESTAMP | NOT NULL DEFAULT CURRENT_TIMESTAMP | Snapshot capture timestamp |

**JSON Structure Requirements:**

db_structure must contain:
- Array of table definitions
- Column specifications with types
- Primary and foreign key relationships

file_list must contain:
- File paths relative to data directory
- File types and extensions
- Extracted headers for structured files

#### Table: Execution_Logs

Detailed execution records for each pipeline step.

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique log entry identifier |
| pipeline_id | INTEGER | FOREIGN KEY REFERENCES Pipelines(id) ON DELETE CASCADE | Parent pipeline reference |
| step_id | INTEGER | FOREIGN KEY REFERENCES Pipeline_Steps(id) ON DELETE CASCADE | Executed step reference |
| run_time | TIMESTAMP | NOT NULL DEFAULT CURRENT_TIMESTAMP | Execution start time |
| is_successful | BOOLEAN | NOT NULL | Execution outcome indicator |
| stdout | TEXT | NULL | Standard output capture |
| stderr | TEXT | NULL | Error output capture |
| exit_code | INTEGER | NULL | Process exit code |
| execution_time_ms | INTEGER | NULL | Execution duration in milliseconds |

**Indexes:**
- INDEX idx_execution_pipeline ON Execution_Logs(pipeline_id)
- INDEX idx_execution_step ON Execution_Logs(step_id)

#### Table: Repair_Logs

Tracks automatic repair attempts and outcomes.

| Column | Data Type | Constraints | Description |
|--------|-----------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique repair log identifier |
| pipeline_id | INTEGER | FOREIGN KEY REFERENCES Pipelines(id) ON DELETE CASCADE | Pipeline being repaired |
| attempt_number | INTEGER | NOT NULL CHECK(attempt_number BETWEEN 1 AND 3) | Repair attempt sequence number |
| original_error | TEXT | NOT NULL | Error message triggering repair |
| ai_fix_reason | TEXT | NOT NULL | LLM explanation of proposed fix |
| patched_code | TEXT | NOT NULL | Corrected code content |
| repair_time | TIMESTAMP | NOT NULL DEFAULT CURRENT_TIMESTAMP | Repair attempt timestamp |
| repair_successful | BOOLEAN | NOT NULL | Whether repair resolved the issue |

**Constraints:**
- UNIQUE(pipeline_id, attempt_number) - Prevent duplicate attempt numbers

**Indexes:**
- INDEX idx_repair_pipeline ON Repair_Logs(pipeline_id)

### Database Initialization Strategy

Database initialization must be idempotent, allowing safe re-execution without data loss.

**Initialization Sequence:**

1. Check if database file exists at configured path
2. If not exists, create new SQLite database file
3. Execute table creation statements in dependency order:
   - Create Pipelines table first (no foreign key dependencies)
   - Create dependent tables (Pipeline_Steps, Schema_Snapshots, Execution_Logs, Repair_Logs)
4. Create all indexes for query performance
5. Verify schema integrity by querying sqlite_master table
6. Insert sample test data if in development environment

**Migration Script Requirements:**

The migration script must:
- Support incremental schema updates
- Preserve existing data during upgrades
- Log all schema changes with timestamps
- Provide rollback capability for failed migrations
- Validate schema integrity after completion

### Sample Test Data

Initial test data enables immediate validation of Phase 1 MCP functionality.

**Test Database Content:**

Create sample tables representing typical use cases:

**Table: orders**
- Columns: id (INTEGER PRIMARY KEY), customer_name (TEXT), amount (DECIMAL), order_date (DATE)
- Sample rows: 5-10 representative records

**Table: products**
- Columns: product_id (INTEGER PRIMARY KEY), product_name (TEXT), category (TEXT), price (DECIMAL)
- Sample rows: 10-15 product entries

**Test Data Files:**

Create sample files in data directory:

**File: sales.csv**
- Headers: order_id, customer, amount, date
- Content: 20-30 rows of realistic sales data

**File: inventory.json**
- Structure: Array of objects with fields: product_id, stock_level, warehouse_location
- Content: 15-20 inventory records

### Application Entry Point Design

The main.py file serves as the FastAPI application entry point and must be minimal, delegating responsibilities to appropriate modules.

**Responsibilities:**

1. Import FastAPI framework and create application instance
2. Load configuration from environment
3. Initialize database connection pool
4. Register API route modules
5. Configure CORS middleware for development
6. Set up exception handlers for consistent error responses
7. Define application lifespan events for startup/shutdown
8. Expose application instance for ASGI server

**Startup Sequence:**

1. Load environment variables from .env file
2. Validate required configuration parameters
3. Initialize database connection
4. Verify database schema exists
5. Create necessary directories (sandbox, data)
6. Log successful startup with configuration summary

**Shutdown Sequence:**

1. Close database connections gracefully
2. Clean up temporary sandbox files
3. Log shutdown event

### Database Connection Management

Database connections must be managed efficiently using connection pooling and context managers.

**Connection Strategy:**

1. Create async database connection pool at application startup
2. Use dependency injection to provide connections to route handlers
3. Ensure connections are properly closed after each request
4. Implement automatic retry logic for transient connection failures
5. Set appropriate timeout values for long-running queries

**Transaction Management:**

- All write operations must execute within explicit transactions
- Use SAVEPOINT for nested transaction support
- Implement automatic rollback on unhandled exceptions
- Log all transaction commits and rollbacks for audit trail

### Development Environment Verification

After completing Phase 0 setup, verify all components are correctly configured.

**Verification Checklist:**

1. Virtual environment activates successfully
2. All dependencies install without errors
3. Database file created with correct schema
4. All required tables exist with proper constraints
5. Sample test data inserted successfully
6. Configuration loads from .env file
7. FastAPI application starts without errors
8. Application health endpoint returns 200 OK
9. Database queries execute successfully
10. All project directories exist with correct permissions

**Success Indicators:**

- FastAPI development server starts on configured port
- Accessing /docs endpoint displays Swagger UI
- Database connection test query succeeds
- No errors in application startup logs
- pytest discovery finds test files

---

## Phase 1: MCP Context Manager

### Objective

Implement comprehensive context gathering capabilities that extract complete database schema metadata and filesystem information, preventing LLM hallucinations by providing accurate system state.

### MCP Architecture Overview

The Model Context Protocol (MCP) module serves as the authoritative source of truth about available system resources, ensuring generated pipelines reference only existing tables, columns, and files.

**Core Responsibilities:**

1. Database schema introspection and metadata extraction
2. Filesystem scanning and file structure analysis
3. Context caching for performance optimization
4. Structured JSON output generation
5. Error handling for missing or inaccessible resources

**Design Principles:**

- **Accuracy**: All extracted metadata must exactly reflect actual system state
- **Completeness**: Capture all relevant information needed for pipeline generation
- **Performance**: Minimize overhead through intelligent caching
- **Reliability**: Handle edge cases gracefully with clear error messages

### Database Metadata Extraction Design

Database introspection must capture comprehensive schema information without hardcoding table or column names.

**Extraction Strategy:**

Leverage SQLite's system catalog (sqlite_master table) to dynamically discover all schema objects.

**Required Metadata:**

1. **Table Discovery**
   - Query sqlite_master for all tables excluding system tables
   - Extract table names and creation SQL
   - Identify table types (regular, view, temporary)

2. **Column Information**
   - Use PRAGMA table_info(table_name) for each discovered table
   - Extract column name, data type, nullability, default value
   - Identify column position in table definition

3. **Primary Key Detection**
   - Parse PRAGMA table_info output for pk flag
   - Support composite primary keys
   - Handle AUTOINCREMENT attribute

4. **Foreign Key Relationships**
   - Execute PRAGMA foreign_key_list(table_name)
   - Extract referenced table and column names
   - Capture ON DELETE and ON UPDATE actions
   - Build relationship graph for dependency analysis

**Output Schema Structure:**

```
{
  "database": {
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
}
```

**Implementation Function: get_database_schema()**

Input Parameters:
- database_connection: Active SQLite database connection

Return Value:
- Structured dictionary containing complete schema metadata

Error Handling:
- Catch database connection errors and return empty schema with error flag
- Handle malformed table definitions gracefully
- Log warnings for inaccessible tables

Performance Considerations:
- Cache schema metadata with configurable TTL
- Invalidate cache on schema modification events
- Optimize PRAGMA queries by batching when possible

### Filesystem Metadata Extraction Design

Filesystem scanning must comprehensively catalog all data files while extracting structural information from supported formats.

**Scanning Strategy:**

1. Start from configured DATA_DIRECTORY root path
2. Recursively traverse all subdirectories
3. Filter files based on supported extensions
4. Extract format-specific metadata for each file
5. Handle permission errors and inaccessible paths

**Supported File Formats:**

| Format | Extensions | Metadata Extraction |
|--------|-----------|-------------------|
| CSV | .csv | Column headers from first row, delimiter detection, row count estimate |
| JSON | .json | Root structure type (array/object), key extraction for objects, array element schema |
| Text | .txt | File size, line count, encoding detection |

**CSV Header Extraction:**

1. Open file in read mode with appropriate encoding detection
2. Read first line as header row
3. Parse using csv module with automatic delimiter detection
4. Extract column names as list
5. Validate header contains no empty values
6. Handle files without headers by returning positional column names

**JSON Structure Analysis:**

1. Parse JSON file using json module
2. Determine root type (object, array, primitive)
3. For objects: extract all top-level keys
4. For arrays: analyze first element schema
5. Detect nested structures up to 2 levels deep
6. Handle malformed JSON with clear error reporting

**File Metadata Collection:**

For each discovered file, capture:
- Absolute and relative file paths
- File size in bytes
- Last modification timestamp
- File extension and detected type
- Extracted headers or structure information
- Read access verification status

**Output Schema Structure:**

```
{
  "filesystem": {
    "root_path": "/absolute/path/to/data",
    "files": [
      {
        "path": "relative/path/to/file.csv",
        "absolute_path": "/absolute/path/to/data/file.csv",
        "type": "csv",
        "size_bytes": 1024,
        "last_modified": "2025-01-15T10:30:00Z",
        "headers": ["column1", "column2", "column3"],
        "row_count_estimate": 100
      },
      {
        "path": "data/config.json",
        "absolute_path": "/absolute/path/to/data/config.json",
        "type": "json",
        "size_bytes": 512,
        "last_modified": "2025-01-14T15:20:00Z",
        "structure": {
          "root_type": "object",
          "keys": ["setting1", "setting2", "nested_config"]
        }
      }
    ],
    "total_files": 2,
    "scan_timestamp": "2025-01-15T11:00:00Z"
  }
}
```

**Implementation Function: get_filesystem_metadata()**

Input Parameters:
- root_directory: Base path for filesystem scanning

Return Value:
- Structured dictionary containing complete filesystem metadata

Error Handling:
- Skip files with permission errors, log warning
- Handle encoding errors in CSV/text files
- Gracefully handle malformed JSON files
- Return partial results if some files fail

Performance Considerations:
- Limit directory traversal depth to prevent excessive scanning
- Cache file metadata with timestamp-based invalidation
- Support incremental scanning for large directories
- Implement size limits for header extraction (e.g., first 1MB only)

### MCP Integration and Context Assembly

The MCPContextManager class orchestrates database and filesystem metadata extraction, providing a unified context interface.

**Class Structure:**

**Attributes:**
- database_connection: SQLite connection instance
- data_directory: Root path for file scanning
- cache_ttl_seconds: Cache time-to-live configuration
- metadata_cache: In-memory cache for assembled context
- last_cache_update: Timestamp of last cache refresh

**Methods:**

**get_full_context()**
- Purpose: Retrieve complete system context combining database and filesystem metadata
- Parameters: None (uses instance configuration)
- Return: Unified context dictionary
- Caching: Check cache validity before re-scanning
- Error Handling: Return partial context if one source fails

**refresh_cache()**
- Purpose: Force cache invalidation and context re-extraction
- Parameters: None
- Return: Updated context dictionary
- Use Cases: Schema modifications, file uploads, periodic refresh

**validate_context()**
- Purpose: Verify context completeness and integrity
- Parameters: context dictionary
- Return: Boolean indicating validity and list of warnings
- Checks: Required keys present, no null values in critical fields

**Context Merging Strategy:**

1. Execute get_database_schema() to retrieve database metadata
2. Execute get_filesystem_metadata() to retrieve file information
3. Merge results into unified structure:
   ```
   {
     "database": { ... },
     "filesystem": { ... },
     "metadata": {
       "context_generated_at": "timestamp",
       "database_table_count": int,
       "filesystem_file_count": int,
       "cache_status": "fresh/stale"
     }
   }
   ```
4. Validate merged context for completeness
5. Update cache with new context and timestamp
6. Return assembled context

**Cache Management:**

Cache Strategy:
- Store context in memory using dictionary
- Set TTL based on environment (short for development, longer for production)
- Invalidate on explicit refresh requests
- Implement background refresh for long-running applications

Cache Key Generation:
- Combine database connection identifier and data directory path
- Include configuration hash to detect parameter changes

### Error Handling and Edge Cases

The MCP module must gracefully handle various failure scenarios without blocking pipeline generation.

**Database Error Scenarios:**

| Error Type | Handling Strategy |
|------------|------------------|
| Connection failure | Return empty database context with error flag, log critical error |
| Permission denied on table | Skip table, include warning in metadata, continue scanning other tables |
| Corrupted table definition | Log error, exclude table from context, mark schema as partial |
| Empty database | Return valid context with zero tables, indicate no schema available |

**Filesystem Error Scenarios:**

| Error Type | Handling Strategy |
|------------|------------------|
| Directory not found | Return empty filesystem context, log error, suggest configuration check |
| Permission denied on file | Skip file, log warning, continue scanning accessible files |
| Encoding error in CSV | Mark file as unreadable, include in context without headers, log warning |
| Malformed JSON | Include file in context with error flag, log parsing error details |
| Large file timeout | Extract partial metadata (first N bytes), mark as incomplete |

**Validation Rules:**

Context validation must check:
1. At least one of database or filesystem context is populated
2. All required metadata fields are present
3. Data types match expected schema
4. No circular foreign key dependencies
5. File paths are relative and normalized

**Error Response Structure:**

When errors occur, include structured error information in context:

```
{
  "database": { ... },
  "filesystem": { ... },
  "errors": [
    {
      "severity": "warning/error/critical",
      "source": "database/filesystem",
      "message": "Descriptive error message",
      "details": {
        "affected_resource": "table_name or file_path",
        "error_code": "specific error identifier"
      }
    }
  ]
}
```

### Testing Strategy for MCP Module

Comprehensive testing ensures MCP reliability across diverse schema and filesystem configurations.

**Unit Test Coverage:**

**Test: test_database_schema_extraction**
- Setup: Create test database with known schema
- Tables: 3 tables with various column types, primary keys, foreign keys
- Validation: Verify all tables discovered, columns extracted correctly, relationships mapped
- Edge Cases: Empty table, table with no primary key, self-referential foreign key

**Test: test_filesystem_csv_scanning**
- Setup: Create temporary CSV files with various structures
- Files: Standard CSV, CSV without headers, CSV with special characters, empty CSV
- Validation: Correct header extraction, delimiter detection, error handling
- Edge Cases: Single column CSV, CSV with inconsistent row lengths

**Test: test_filesystem_json_scanning**
- Setup: Create temporary JSON files with various structures
- Files: Object, array, nested structures, malformed JSON
- Validation: Structure correctly identified, keys extracted, errors handled gracefully
- Edge Cases: Empty JSON, large JSON files, deeply nested structures

**Test: test_mcp_cache_functionality**
- Setup: Initialize MCP with caching enabled
- Operations: Call get_full_context() twice, verify second call uses cache
- Validation: Cache hit improves performance, cache invalidation works
- Edge Cases: Cache expiration, concurrent access

**Integration Test Coverage:**

**Test: test_mcp_with_sample_data**
- Setup: Use Phase 0 sample database and test files
- Operation: Call get_full_context()
- Validation:
  - All sample tables appear in context
  - All sample files detected
  - Relationships correctly mapped
  - No errors in metadata

**Test: test_mcp_error_recovery**
- Setup: Create scenarios with missing permissions, corrupted files
- Operation: Call get_full_context()
- Validation:
  - Partial context returned
  - Errors logged appropriately
  - No unhandled exceptions
  - Clear error messages in response

**Test: test_mcp_performance**
- Setup: Create database with 20+ tables and 50+ files
- Operation: Measure get_full_context() execution time
- Validation:
  - Context generation completes in < 2 seconds
  - Cache improves subsequent calls by > 80%
  - Memory usage remains reasonable

**Test Data Requirements:**

Create comprehensive test fixtures including:
- Database with diverse table structures
- CSV files with various delimiters and encodings
- JSON files with different nesting levels
- Files with permission restrictions
- Empty and malformed files

### Success Criteria for Phase 1

Phase 1 is considered complete when all of the following criteria are met:

**Functional Requirements:**
1. MCP returns valid JSON with complete database schema for all accessible tables
2. MCP detects all files in configured data directory with correct metadata
3. CSV headers are correctly extracted for well-formed CSV files
4. JSON structure analysis identifies root types and keys
5. No hallucinations of non-existent tables or files in output
6. Error handling provides clear messages for inaccessible resources

**Performance Requirements:**
1. Context generation completes in < 2 seconds for typical workloads (10 tables, 20 files)
2. Cache reduces subsequent context retrieval time by > 80%
3. Memory usage for cached context < 10MB

**Quality Requirements:**
1. Unit test coverage > 90% for all MCP functions
2. Integration tests pass with sample data from Phase 0
3. All edge cases handled without unhandled exceptions
4. Documentation complete with usage examples

**Validation Method:**

Execute comprehensive test suite covering:
- Database with 15 tables including complex relationships
- Data directory with 25 files of mixed types
- Error scenarios with inaccessible resources
- Cache performance benchmarks
- Concurrent access scenarios

---

## Design Rationale

### Technology Selection Justification

**SQLite Selection:**
SQLite was chosen over client-server databases because:
- Zero configuration required for development and testing
- File-based storage simplifies deployment
- Sufficient performance for MVP workload (< 1000 pipelines)
- Built-in transaction support with ACID guarantees
- Rich introspection capabilities via PRAGMA statements

**FastAPI Selection:**
FastAPI provides optimal balance of performance and developer productivity:
- Native async/await support for concurrent operations
- Automatic OpenAPI documentation generation
- Built-in request validation via Pydantic
- High performance comparable to Node.js frameworks
- Excellent type safety with Python type hints

**Gemini API Selection:**
Google Gemini offers specific advantages for pipeline generation:
- Strong structured JSON output capabilities
- Competitive pricing for MVP development
- Good performance on code generation tasks
- Comprehensive Python SDK
- Flexible prompt engineering capabilities

### Design Trade-offs

**Caching Strategy:**
In-memory caching was chosen over Redis/external cache because:
- Simpler architecture for MVP
- Eliminates external dependency
- Sufficient for single-instance deployment
- Easy to upgrade to distributed cache later
- Reduced operational complexity

**Synchronous vs Asynchronous Operations:**
Database operations use async patterns while filesystem operations remain synchronous because:
- Database I/O benefits significantly from async for concurrent queries
- Filesystem operations in Python have limited async benefits
- Reduces complexity for file reading operations
- Maintains code readability
- Can be optimized later if performance requires

**Schema Validation:**
Runtime schema validation preferred over static migration tools because:
- Simpler initial implementation
- Flexible for rapid development iteration
- Sufficient for MVP with limited users
- Migration to Alembic straightforward if needed
- Reduces initial tooling complexity

### Security Considerations

**Configuration Security:**
Environment-based configuration prevents credential exposure:
- API keys never hardcoded in source
- .env file excluded from version control
- Separate configurations per environment
- Audit trail for configuration changes

**Database Access:**
SQLite file permissions restrict unauthorized access:
- File-level permission controls
- Connection string validation
- Prepared statements prevent SQL injection
- Transaction isolation prevents concurrent corruption

**Filesystem Access:**
Directory traversal attacks prevented through:
- Path normalization before file access
- Restriction to configured data directory
- Symbolic link validation
- Permission checks before file operations

---

## Dependencies and Prerequisites

### Phase 0 Prerequisites

Before starting Phase 0 implementation:
1. Python 3.10+ installed on development machine
2. Git installed for version control
3. Text editor or IDE configured for Python development
4. Terminal access with shell command execution
5. Administrator/elevated permissions for package installation

### Phase 1 Prerequisites

Before starting Phase 1 implementation:
1. Phase 0 completed successfully with all verification checks passed
2. Database initialized with sample test data
3. Virtual environment activated
4. All dependencies installed without errors
5. Configuration file (.env) properly set up

### External Dependencies

**Required Services:**
- None for Phase 0 and Phase 1 (operates entirely locally)

**Optional Services:**
- Git repository hosting (GitHub/GitLab) for version control
- Code quality tools (pylint, black, mypy) for development

---

## Monitoring and Observability

### Logging Strategy

**Log Levels:**
- DEBUG: Detailed diagnostic information for development
- INFO: General operational events (startup, context generation)
- WARNING: Unexpected situations that don't prevent operation
- ERROR: Error events that might still allow operation to continue
- CRITICAL: Severe errors requiring immediate attention

**Log Categories:**

| Category | Events to Log |
|----------|--------------|
| Application | Startup, shutdown, configuration loading |
| Database | Connection events, query errors, schema introspection |
| MCP | Context generation, cache hits/misses, extraction errors |
| Filesystem | Directory scanning, file access errors, permission issues |

**Log Format:**

Structured logging with consistent format:
- Timestamp in ISO 8601 format
- Log level
- Module/component name
- Message
- Contextual data (structured fields)

### Performance Metrics

Key metrics to track for Phase 0 and Phase 1:

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Application startup time | < 3 seconds | Time from process start to ready state |
| Database schema extraction | < 500ms | Function execution time |
| Filesystem scanning (20 files) | < 1 second | Function execution time |
| Full context generation | < 2 seconds | End-to-end MCP operation |
| Cache hit rate | > 80% | Cache hits / total requests |

### Health Checks

Implement health check endpoint for operational monitoring:

**Endpoint: GET /health**

Response includes:
- Application status (healthy/degraded/unhealthy)
- Database connectivity status
- Filesystem accessibility status
- Last successful context generation timestamp
- Current cache status

---

## Future Enhancements

### Post-MVP Improvements for MCP

**Advanced Schema Analysis:**
- Index detection and optimization recommendations
- View and trigger discovery
- Stored procedure introspection
- Constraint validation rules

**Enhanced File Support:**
- Excel file (.xlsx) parsing
- Parquet file metadata extraction
- XML structure analysis
- Binary file format detection

**Performance Optimization:**
- Distributed caching with Redis
- Incremental filesystem scanning
- Parallel metadata extraction
- Streaming for large file analysis

**Intelligent Caching:**
- Filesystem watcher for automatic cache invalidation
- Predictive cache warming
- Cache compression for memory efficiency
- Multi-tier caching strategy
