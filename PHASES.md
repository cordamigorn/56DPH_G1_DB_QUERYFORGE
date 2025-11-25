# QUERYFORGE — Development Phases

**Project:** QueryForge - Automated Data Pipeline Generation System  
**Based on:** Product Requirements Document (PRD)  
**Development Approach:** Iterative, Module-by-Module Implementation

---

## 📊 Completion Status

✅ **Phase 0: Project Setup & Foundation** - COMPLETE  
✅ **Phase 1: MCP Context Manager** - COMPLETE  
✅ **Phase 2: LLM Pipeline Generator** - COMPLETE  
✅ **Phase 3: Bash/SQL Synthesizer** - COMPLETE  
⬜ **Phase 4: Sandbox Execution** - PENDING  
⬜ **Phase 5: Error Detection & Repair Loop** - PENDING  
⬜ **Phase 6: Commit Module** - PENDING  
⬜ **Phase 7: FastAPI Integration** - PENDING  
⬜ **Phase 8: Integration & Testing** - PENDING  
⬜ **Phase 9: Documentation & Deployment** - PENDING  

**Overall Progress:** 4/10 Phases (40%) ✅

**Last Updated:** November 24, 2025

---

## Phase 0: Project Setup & Foundation

### 0.1 Environment Setup
- [x] Install Python 3.10+
- [x] Set up virtual environment
- [x] Install core dependencies:
  - FastAPI 0.104+
  - SQLite3
  - Google Gemini API SDK
  - Pydantic for data validation
  - pytest for testing

### 0.2 Project Structure
```
queryforge/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       └── pipeline.py     # Pipeline endpoints
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Configuration management
│   │   └── database.py         # Database connection
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py          # Pydantic models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── mcp.py              # Context Manager
│   │   ├── llm.py              # LLM Pipeline Generator
│   │   ├── synthesizer.py      # Bash/SQL Synthesizer
│   │   ├── sandbox.py          # Sandbox Execution
│   │   ├── repair.py           # Repair Module
│   │   └── commit.py           # Commit Service
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── data/                       # Test data directory
├── sandbox/                    # Sandbox workspace
├── tests/
│   ├── __init__.py
│   ├── test_mcp.py
│   ├── test_llm.py
│   └── ...
├── .env                        # Environment variables (Gemini API key)
├── requirements.txt
└── README.md
```

### 0.3 Database Initialization
- [x] Create SQLite database schema
- [x] Implement all 5 required tables:
  - `Pipelines`
  - `Pipeline_Steps`
  - `Schema_Snapshots`
  - `Execution_Logs`
  - `Repair_Logs`
- [x] Create database migration script
- [x] Add sample test data

**Deliverable:** Working project structure with initialized database

---

## Phase 1: MCP Context Manager

### 1.1 Database Metadata Extraction
- [x] Implement `get_database_schema()` function
  - Extract table names
  - Extract column information (name, type, nullable)
  - Extract primary keys
  - Extract foreign key relationships
- [x] Return structured JSON format

### 1.2 Filesystem Metadata Extraction
- [x] Implement `get_filesystem_metadata()` function
  - Scan data directory
  - List files with extensions
  - Extract CSV headers (using csv.reader)
  - Extract JSON structure
  - Get file sizes and timestamps
- [x] Return structured JSON format

### 1.3 MCP Integration
- [x] Create `MCPContextManager` class
- [x] Implement `get_full_context()` method
  - Combine database + filesystem metadata
  - Cache results for performance
- [x] Add error handling for missing files/tables

### 1.4 Testing
- [x] Unit tests for database introspection
- [x] Unit tests for filesystem scanning
- [x] Integration test with sample data
- [x] Verify JSON output format

**Deliverable:** Working MCP module that returns complete context

**Success Criteria:**
- MCP returns valid JSON with database schema
- MCP detects all files in data directory
- CSV headers are correctly extracted
- No hallucinations of non-existent resources

---

## Phase 2: LLM Pipeline Generator

### 2.1 Gemini API Integration
- [x] Set up Gemini API credentials
- [x] Create `GeminiClient` class
- [x] Implement retry logic for API failures
- [x] Add timeout handling (3 seconds max)

### 2.2 Prompt Engineering
- [x] Design system prompt template
  - Include MCP context
  - Specify output format (JSON)
  - Define allowed Bash commands
  - Define SQL constraints
- [x] Create user prompt template
- [x] Test prompt with sample requests

### 2.3 Pipeline Generation Logic
- [x] Implement `generate_pipeline(prompt, context)` function
- [x] Parse LLM response into structured JSON
- [x] Validate generated pipeline:
  - Check for non-existent tables/files
  - Verify Bash command whitelist
  - Ensure proper execution order
- [x] Handle malformed LLM responses

### 2.4 Testing
- [x] Test with simple requests (e.g., "Import CSV")
- [x] Test with complex multi-step requests
- [x] Test edge cases (non-existent files)
- [x] Validate JSON output structure

**Deliverable:** LLM module that generates valid pipelines

**Success Criteria:**
- Pipeline generation completes in < 3 seconds
- All generated syntax is valid
- No references to non-existent resources
- Output follows strict JSON format

**Status:** ✅ COMPLETE - All tests passing (18/18)

---

## Phase 3: Bash/SQL Synthesizer

### 3.1 Script File Generation
- [x] Implement `synthesize_bash(step_content)` function
  - Generate .sh file with proper shebang
  - Add error handling (set -e)
  - Add logging statements
  - Set executable permissions
- [x] Implement `synthesize_sql(step_content)` function
  - Generate .sql file
  - Add transaction wrappers
  - Add error handling

### 3.2 Pipeline Orchestration
- [x] Create `PipelineSynthesizer` class
- [x] Implement `synthesize_pipeline(pipeline_json)` method
  - Generate numbered script files (step_1.sh, step_2.sql, etc.)
  - Store in temporary directory
  - Return file paths list

### 3.3 Testing
- [x] Test Bash script generation
- [x] Test SQL script generation
- [x] Test mixed pipeline generation
- [x] Verify file permissions

**Deliverable:** Synthesizer that converts JSON to executable scripts

**Success Criteria:**
- Scripts are syntactically valid
- File permissions are correct
- Proper error handling in each script

**Status:** ✅ COMPLETE - All tests passing (17/17)

---

## Phase 4: Sandbox Execution

### 4.1 Sandbox Environment Setup
- [ ] Create isolated sandbox directory structure
- [ ] Implement filesystem restrictions
  - Block access to real filesystem
  - Allow only /tmp writes
- [ ] Implement command whitelist enforcement
  - Allow: awk, sed, cp, mv, curl
  - Block: rm, dd, sudo, wget (without whitelist)

### 4.2 Execution Engine
- [ ] Create `SandboxRunner` class
- [ ] Implement `execute_step(script_path)` method using subprocess
  - Capture stdout
  - Capture stderr
  - Capture exit code
  - Measure execution time
  - Enforce 10-second timeout
- [ ] Implement `execute_pipeline(steps)` method
  - Execute steps in order
  - Stop at first failure
  - Return execution logs

### 4.3 Resource Limits
- [ ] Implement CPU/memory limits (if possible with subprocess)
- [ ] Add timeout enforcement
- [ ] Add cleanup after execution

### 4.4 Logging
- [ ] Save execution results to `Execution_Logs` table
  - pipeline_id
  - step_id
  - run_time
  - is_successful
  - stdout/stderr
  - exit_code
  - execution_time_ms

### 4.5 Testing
- [ ] Test successful pipeline execution
- [ ] Test failed pipeline (stops at error)
- [ ] Test timeout scenarios
- [ ] Test command whitelist enforcement
- [ ] Verify logs are saved correctly

**Deliverable:** Working sandbox execution module

**Success Criteria:**
- Pipeline stops at first error
- All output logged with timestamps
- Sandbox cleanup after execution
- No state persists between runs
- Execution completes in < 10 seconds per step

---

## Phase 5: Error Detection & Repair Loop

### 5.1 Error Analysis Module
- [ ] Create `ErrorAnalyzer` class
- [ ] Implement `analyze_error(execution_log)` method
  - Parse stderr for error messages
  - Identify error type (file not found, syntax error, table missing)
  - Extract relevant context

### 5.2 Repair Generator
- [ ] Create `RepairModule` class
- [ ] Implement `generate_fix(error, original_step, context)` method
  - Send error + step + context to Gemini API
  - Request corrected step
  - Validate fix
- [ ] Implement repair attempt tracking

### 5.3 Repair Loop Logic
- [ ] Implement `repair_and_retry(pipeline_id)` function
  - Get execution error
  - Analyze error
  - Generate fix
  - Update pipeline step
  - Retry execution
  - Log repair attempt
- [ ] Implement maximum retry limit (3 attempts)
- [ ] Prevent infinite loops

### 5.4 Repair Logging
- [ ] Save repair attempts to `Repair_Logs` table
  - pipeline_id
  - attempt_number
  - original_error
  - ai_fix_reason
  - patched_code
  - repair_time
  - repair_successful

### 5.5 Testing
- [ ] Test with common errors (table not found)
- [ ] Test with syntax errors
- [ ] Test maximum retry limit
- [ ] Test successful repair
- [ ] Verify logs are saved

**Deliverable:** Self-healing repair module

**Success Criteria:**
- Maximum 3 repair attempts enforced
- All attempts logged in Repair_Logs
- Repair success rate > 70% for common errors
- Infinite loop prevention works

---

## Phase 6: Commit Module

### 6.1 Pre-Commit Validation
- [ ] Create `CommitService` class
- [ ] Implement `validate_for_commit(pipeline_id)` method
  - Verify sandbox execution success
  - Check file integrity
  - Validate database transaction readiness

### 6.2 Database Commit
- [ ] Implement `commit_sql_operations(steps)` method
  - Begin transaction
  - Execute SQL steps on real database
  - Commit on success
  - Rollback on failure

### 6.3 Filesystem Commit
- [ ] Implement `commit_file_operations(steps)` method
  - Execute Bash steps on real filesystem
  - Log all file operations
  - Support reversal if possible

### 6.4 Rollback Strategy
- [ ] Implement transaction rollback for SQL
- [ ] Implement filesystem operation logging
- [ ] Create before/after snapshots in `Schema_Snapshots`

### 6.5 Testing
- [ ] Test successful commit
- [ ] Test rollback on SQL failure
- [ ] Test filesystem operations
- [ ] Verify snapshots are saved

**Deliverable:** Safe commit module with rollback

**Success Criteria:**
- Only executes after sandbox success
- All database operations are transactional
- Rollback works on failure
- Full audit trail maintained

---

## Phase 7: FastAPI Integration

### 7.1 API Endpoints Implementation

#### POST /pipeline/create
- [ ] Implement endpoint
- [ ] Request validation (Pydantic models)
- [ ] Call MCP for context
- [ ] Call LLM for pipeline generation
- [ ] Save pipeline to database
- [ ] Return pipeline_id and draft

#### POST /pipeline/run/{id}
- [ ] Implement endpoint
- [ ] Retrieve pipeline from database
- [ ] Synthesize scripts
- [ ] Execute in sandbox
- [ ] Save execution logs
- [ ] Return execution results

#### POST /pipeline/repair/{id}
- [ ] Implement endpoint
- [ ] Trigger repair loop
- [ ] Return repair status

#### GET /pipeline/{id}/logs
- [ ] Implement endpoint
- [ ] Retrieve all logs from database
- [ ] Format response with execution + repair logs

### 7.2 Error Handling
- [ ] Add global exception handlers
- [ ] Return proper HTTP status codes
- [ ] Format error responses consistently

### 7.3 Testing
- [ ] Test all endpoints with Postman/curl
- [ ] Test error responses
- [ ] Test end-to-end flow

**Deliverable:** Complete REST API

**Success Criteria:**
- All 4 endpoints working
- Proper error handling
- API response time < 2 seconds (excluding LLM)

---

## Phase 8: Integration & End-to-End Testing

### 8.1 Integration Tests
- [ ] Test complete pipeline flow:
  1. Create pipeline from prompt
  2. Run in sandbox
  3. Detect error (if any)
  4. Repair and retry
  5. Commit to production
- [ ] Test with multiple scenarios:
  - Simple CSV import
  - Multi-step transformation
  - Error + repair scenario
  - Complex ETL pipeline

### 8.2 Data Validation
- [ ] Verify database integrity
- [ ] Check log completeness
- [ ] Validate snapshots

### 8.3 Performance Testing
- [ ] Measure pipeline generation time
- [ ] Measure sandbox execution time
- [ ] Measure API response times
- [ ] Verify performance requirements met

### 8.4 Security Testing
- [ ] Test sandbox isolation
- [ ] Test command whitelist
- [ ] Test SQL injection prevention
- [ ] Test user isolation

**Deliverable:** Fully tested system

**Success Criteria:**
- All 9 MVP acceptance criteria met
- Test coverage > 80%
- Performance requirements satisfied
- Security constraints enforced

---

## Phase 9: Documentation & Deployment

### 9.1 Code Documentation
- [ ] Add docstrings to all functions
- [ ] Add inline comments for complex logic
- [ ] Generate API documentation (Swagger/OpenAPI)

### 9.2 User Documentation
- [ ] Create usage examples
- [ ] Document API endpoints
- [ ] Create troubleshooting guide

### 9.3 Deployment Preparation
- [ ] Create requirements.txt
- [ ] Document environment setup
- [ ] Create startup scripts
- [ ] Add configuration guide

### 9.4 Final Testing
- [ ] Run all tests
- [ ] Verify MVP completion criteria
- [ ] Performance validation
- [ ] Security validation

**Deliverable:** Production-ready QueryForge MVP

---

## Phase 10: Optional Enhancements (Post-MVP)

### 10.1 UI Development
- [ ] Create web interface for pipeline creation
- [ ] Add pipeline monitoring dashboard
- [ ] Visualize execution logs

### 10.2 Advanced Features
- [ ] Pipeline templates
- [ ] Scheduled pipeline execution
- [ ] Multi-user support with authentication
- [ ] Pipeline versioning
- [ ] Advanced error analytics

### 10.3 Performance Optimization
- [ ] Implement caching for MCP context
- [ ] Add async execution for multiple pipelines
- [ ] Optimize database queries

---

## Timeline Estimation

| Phase | Estimated Duration | Dependencies |
|-------|-------------------|--------------|
| Phase 0: Setup | 1-2 days | None |
| Phase 1: MCP | 2-3 days | Phase 0 |
| Phase 2: LLM Generator | 3-4 days | Phase 1 |
| Phase 3: Synthesizer | 2 days | Phase 2 |
| Phase 4: Sandbox | 4-5 days | Phase 3 |
| Phase 5: Repair Loop | 3-4 days | Phase 2, 4 |
| Phase 6: Commit | 2-3 days | Phase 4 |
| Phase 7: API | 2-3 days | All previous |
| Phase 8: Testing | 3-4 days | Phase 7 |
| Phase 9: Documentation | 2 days | Phase 8 |

**Total Estimated Duration:** 24-33 days (4-6 weeks)

---

## Development Best Practices

### Code Quality
- Follow PEP 8 style guide for Python
- Write comprehensive docstrings
- Use type hints throughout
- Keep functions small and focused

### Testing Strategy
- Write tests before/during implementation (TDD encouraged)
- Aim for > 80% code coverage
- Test both success and failure paths
- Use fixtures for test data

### Version Control
- Commit frequently with clear messages
- Create feature branches for each phase
- Use pull requests for code review
- Tag releases (v0.1-mvp, etc.)

### Security Mindset
- Never trust user input
- Sanitize all file paths
- Enforce command whitelists strictly
- Use parameterized SQL queries
- Log security-relevant events

---

## Success Metrics

### MVP Completion Checklist
- [ ] Accept natural-language request
- [ ] Generate hybrid Bash+SQL pipeline
- [ ] Introspect schema + filesystem
- [ ] Execute pipeline in sandbox
- [ ] Detect and log errors
- [ ] Automatically repair faulty steps
- [ ] Re-run until successful
- [ ] Commit final correct pipeline to real DB
- [ ] Store full traceability in DB

### Performance Metrics
- [ ] Pipeline generation < 3 seconds
- [ ] Sandbox execution < 10 seconds per step
- [ ] Database queries < 1 second
- [ ] API response time < 2 seconds

### Quality Metrics
- [ ] Test coverage > 80%
- [ ] Zero critical security vulnerabilities
- [ ] All API endpoints documented
- [ ] Repair success rate > 70%

---

**Ready to start development!** 🚀
