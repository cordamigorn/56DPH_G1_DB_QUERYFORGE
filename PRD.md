# QUERYFORGE — Product Requirements Document (PRD)

**Version:** Final - Ready for Development  
**Source:** Lab Report Analysis (Architecture, Flowcharts, ER Diagrams)  
**Last Updated:** November 2025

---

## 1. Product Overview

**QueryForge** is an automated data pipeline generation system that converts natural-language requests into validated, executable hybrid Bash+SQL pipelines. It provides:

- **LLM-based pipeline synthesis** from plain English descriptions
- **Schema & filesystem introspection** via MCP context manager
- **Sandbox execution** with safety constraints
- **Automatic error detection & repair loop** with self-healing capabilities
- **Safe production deployment** with full traceability

**Core Goal:** Enable users to request data tasks (ETL, imports, transformations) in plain English and receive fully validated, executable pipelines without manual intervention.

---

## 2. Key Features & Requirements

### 2.1 Natural Language → Pipeline Generation

**User Input Example:**
```
"Import sales.csv into the orders table and drop rows with empty amount fields."
```

**System Output:**
A structured pipeline containing:
- Bash steps (file operations, curl, transformations)
- SQL steps (COPY, INSERT, UPDATE, DELETE)
- Execution order and dependencies

**Acceptance Criteria:**
- [ ] All generated Bash/SQL syntax must be valid
- [ ] All referenced file paths and tables must exist (validated by MCP)
- [ ] Output must include execution order and step dependencies

---

### 2.2 MCP Context Manager (Schema & File Introspection)

The MCP module gathers comprehensive system context:

**Database Metadata:**
- Table list with names and types
- Column information (name, datatype, nullable)
- Primary keys and constraints
- Foreign key relationships

**FileSystem Metadata:**
- Root data directory path
- File list with extensions
- CSV/JSON headers extracted
- File sizes and timestamps

**Output Format (JSON):**
```json
{
  "database": {
    "tables": [
      {
        "name": "orders",
        "columns": [
          {"name": "id", "type": "INTEGER", "primary_key": true},
          {"name": "amount", "type": "DECIMAL"}
        ]
      }
    ]
  },
  "filesystem": {
    "files": [
      {
        "path": "/data/sales.csv",
        "type": "csv",
        "headers": ["id", "customer", "amount"]
      }
    ]
  }
}
```

**Acceptance Criteria:**
- [ ] MCP must return complete schema metadata
- [ ] MCP must detect all available files in data directory
- [ ] CSV headers must be automatically extracted
- [ ] No hallucinations of non-existent resources

---

### 2.3 LLM Pipeline Generator

Leverages MCP context to generate structured pipelines using Gemini API.

**Input:**
- User prompt
- Database schema
- File system metadata

**Output (JSON):**
```json
{
  "pipeline": [
    {
      "step_number": 1,
      "type": "bash",
      "content": "awk -F',' '$3==\"\" {next} {print}' /data/sales.csv > /tmp/cleaned.csv"
    },
    {
      "step_number": 2,
      "type": "sql",
      "content": "COPY orders FROM '/tmp/cleaned.csv' WITH (FORMAT csv, HEADER true)"
    }
  ]
}
```

**Acceptance Criteria:**
- [ ] Must not reference non-existent tables or files
- [ ] Must include proper dependencies between steps
- [ ] All SQL must be parameterized (no SQL injection)
- [ ] Must specify expected execution order

---

### 2.4 Bash/SQL Synthesizer

Converts LLM JSON output into individual executable script files:
- `step_1.sh` (Bash script)
- `step_2.sql` (SQL script)
- `step_3.sh` (Bash script)

**Requirements:**
- [ ] Proper file permissions (executable for .sh files)
- [ ] Error handling and exit codes
- [ ] Logging statements in each step

---

### 2.5 Sandbox Execution

Isolated execution environment with safety constraints.

**Constraints:**
- No access to real filesystem
- No destructive commands allowed
- CPU/memory limits enforced
- Timeout after 10 seconds per step

**Captured Output:**
- Standard output (stdout)
- Error output (stderr)
- Exit code (0 = success, non-zero = failure)
- Execution time

**Execution Flow:**
1. Copy test data to sandbox
2. Execute pipeline step-by-step
3. Stop at first error
4. Capture all logs in `Execution_Logs` table

**Acceptance Criteria:**
- [ ] Pipeline execution stops at first failure
- [ ] All output logged with timestamps
- [ ] Sandbox cleanup after execution
- [ ] No state persists between runs

---

### 2.6 Error Detection & Repair Loop

Automatic error analysis and self-healing mechanism.

**Workflow:**
1. Sandbox detects execution failure
2. Error analysis module extracts error details
3. LLM receives: failed step + error log + full context
4. LLM generates corrected step
5. Sandbox retries execution
6. If success → proceed to commit
7. If failure → repeat up to 3 times maximum

**Repair Attempt Tracking:**
- Log each repair attempt with timestamp
- Store original error and fix reason
- Track success/failure of each retry

**Acceptance Criteria:**
- [ ] Maximum 3 repair attempts per pipeline
- [ ] All repair attempts logged in `Repair_Logs`
- [ ] Repair success rate > 70% for common errors
- [ ] Infinite loop prevention (abort after 3 attempts)

---

### 2.7 Commit Module

Applies validated pipeline changes to production systems.

**Pre-Commit Checks:**
- Verify sandbox execution success
- Validate file integrity
- Check database transaction state

**Commit Operations:**
- Apply SQL operations to real database (within transaction)
- Apply file operations to real filesystem
- Store final pipeline results

**Rollback Strategy:**
- Transaction rollback on any failure
- Filesystem operations logged for potential reversal
- Preserve before/after state snapshots

**Acceptance Criteria:**
- [ ] Only execute after sandbox success = true
- [ ] All database operations transactional
- [ ] Rollback capability on failure
- [ ] Full audit trail of changes

---

## 3. System Architecture

### 3.1 Core Modules

```
┌─────────────────────────────────────────────────────────────┐
│                      API Gateway (FastAPI)                   │
└─────────────────────────────────────────────────────────────┘
                              ↓
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
   ┌──────────┐      ┌──────────────┐      ┌──────────────┐
   │ Context  │      │ LLM Pipeline │      │ Bash/SQL     │
   │ Manager  │      │ Generator    │      │ Synthesizer  │
   │ (MCP)    │      │              │      │              │
   └──────────┘      └──────────────┘      └──────────────┘
        ↓                     ↓                     ↓
   ┌─────────────────────────┴─────────────────────┐
   │        Sandbox Runner (Isolated Env)          │
   └──────────────┬──────────────────────────────────┘
                  ↓
        ┌─────────────────────┐
        │ Error Analysis      │
        │ & Repair Module     │
        └─────────────────────┘
                  ↓
        ┌─────────────────────┐
        │ Commit Service      │
        │ (DB + FileSystem)   │
        └─────────────────────┘
                  ↓
        ┌─────────────────────┐
        │ SQLite Database     │
        │ (Logs & Metadata)   │
        └─────────────────────┘
```

### 3.2 Mandatory Components

| Module | Technology | Responsibility |
|--------|-----------|-----------------|
| API Gateway | FastAPI | REST endpoint management |
| Context Manager | Python (MCP) | Schema & file introspection |
| Pipeline Generator | Gemini API | Natural language → pipeline |
| Synthesizer | Python | JSON → executable scripts |
| Sandbox Runner | Subprocess | Isolated execution |
| Error Module | Python | Error detection & analysis |
| Repair Module | Gemini API | LLM-based fix generation |
| Commit Service | Python | Production deployment |

---

## 4. Database Schema

### 4.1 Tables

#### `Pipelines`
Stores pipeline metadata and status.

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY | Unique pipeline identifier |
| user_id | INTEGER | NOT NULL | User who created pipeline |
| prompt_text | TEXT | NOT NULL | Original natural-language request |
| status | VARCHAR(50) | NOT NULL | pending / running / success / failed / repaired |
| created_at | TIMESTAMP | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP | | Last modification timestamp |

#### `Pipeline_Steps`
Individual executable steps within a pipeline.

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY | Unique step identifier |
| pipeline_id | INTEGER | FOREIGN KEY | Reference to Pipelines |
| step_number | INTEGER | NOT NULL | Execution order |
| code_type | VARCHAR(10) | NOT NULL | 'bash' or 'sql' |
| script_content | TEXT | NOT NULL | Executable code |
| created_at | TIMESTAMP | | Step creation time |

#### `Schema_Snapshots`
Pre-pipeline system state snapshots.

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY | Unique snapshot identifier |
| pipeline_id | INTEGER | FOREIGN KEY | Reference to Pipelines |
| db_structure | JSON | NOT NULL | Database schema at time of pipeline creation |
| file_list | JSON | NOT NULL | Filesystem state at time of creation |
| snapshot_time | TIMESTAMP | NOT NULL | Snapshot capture time |

#### `Execution_Logs`
Records of sandbox execution for each pipeline.

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY | Unique log identifier |
| pipeline_id | INTEGER | FOREIGN KEY | Reference to Pipelines |
| step_id | INTEGER | FOREIGN KEY | Reference to Pipeline_Steps |
| run_time | TIMESTAMP | NOT NULL | Execution timestamp |
| is_successful | BOOLEAN | NOT NULL | Success/failure indicator |
| stdout | TEXT | | Standard output |
| stderr | TEXT | | Error output |
| exit_code | INTEGER | | Process exit code |
| execution_time_ms | INTEGER | | Execution duration |

#### `Repair_Logs`
Tracks automatic repair attempts.

| Column | Type | Constraint | Description |
|--------|------|-----------|-------------|
| id | INTEGER | PRIMARY KEY | Unique repair log identifier |
| pipeline_id | INTEGER | FOREIGN KEY | Reference to Pipelines |
| attempt_number | INTEGER | NOT NULL | Repair attempt number (1-3) |
| original_error | TEXT | NOT NULL | Error detected |
| ai_fix_reason | TEXT | NOT NULL | LLM explanation of fix |
| patched_code | TEXT | NOT NULL | Corrected code |
| repair_time | TIMESTAMP | NOT NULL | Repair attempt time |
| repair_successful | BOOLEAN | NOT NULL | Whether repair fixed the issue |

---

## 5. Technology Stack

| Component | Technology | Version | Rationale |
|-----------|-----------|---------|-----------|
| LLM API | Google Gemini | Latest | Structured JSON output support |
| Backend Framework | FastAPI | 0.104+ | High performance, async support |
| Database | SQLite | 3.40+ | Lightweight, file-based, no setup |
| Scripting | Python | 3.10+ | MCP integration, subprocess control |
| Pipeline Execution | Bash | 4.0+ | Native subprocess execution |
| Context Management | Python MCP Module | Custom | Schema & file introspection |
| Sandbox | Local Subprocess | Built-in | Lightweight, no Docker dependency |

---

## 6. API Specifications

### 6.1 POST /pipeline/create

Create a new pipeline from natural-language request.

**Request:**
```json
{
  "user_id": 1,
  "prompt": "Import sales.csv into orders table and drop rows with empty amount fields"
}
```

**Response (200 OK):**
```json
{
  "pipeline_id": 42,
  "status": "generated",
  "draft_pipeline": [
    {
      "step_number": 1,
      "type": "bash",
      "content": "awk -F',' '$3!=\"\" {print}' /data/sales.csv > /tmp/cleaned.csv"
    },
    {
      "step_number": 2,
      "type": "sql",
      "content": "COPY orders FROM '/tmp/cleaned.csv' WITH (FORMAT csv, HEADER true)"
    }
  ],
  "created_at": "2025-11-24T10:30:00Z"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid prompt or missing user_id
- `500 Internal Server Error`: LLM API failure

---

### 6.2 POST /pipeline/run/{id}

Execute pipeline in sandbox environment.

**Request:**
```json
{
  "run_mode": "sandbox"
}
```

**Response (200 OK):**
```json
{
  "pipeline_id": 42,
  "status": "running",
  "execution_log": {
    "step_1": {
      "type": "bash",
      "exit_code": 0,
      "stdout": "5 rows processed"
    },
    "step_2": {
      "type": "sql",
      "exit_code": 1,
      "stderr": "ERROR: table 'orders' does not exist"
    }
  },
  "overall_status": "failed"
}
```

**Error Responses:**
- `404 Not Found`: Pipeline ID not found
- `503 Service Unavailable`: Sandbox execution timeout

---

### 6.3 POST /pipeline/repair/{id}

Trigger automatic repair and retry.

**Request:**
```json
{
  "attempt": 1
}
```

**Response (200 OK):**
```json
{
  "pipeline_id": 42,
  "repair_attempt": 1,
  "error_analysis": "Table 'orders' missing. Creating table before COPY...",
  "repaired_pipeline": [
    {
      "step_number": 2,
      "type": "sql",
      "content": "CREATE TABLE IF NOT EXISTS orders (id INT, amount DECIMAL); COPY orders FROM..."
    }
  ],
  "retry_status": "in_progress"
}
```

---

### 6.4 GET /pipeline/{id}/logs

Retrieve complete execution and repair logs.

**Response (200 OK):**
```json
{
  "pipeline_id": 42,
  "original_prompt": "Import sales.csv...",
  "execution_logs": [
    {
      "step_id": 1,
      "run_time": "2025-11-24T10:30:15Z",
      "is_successful": true,
      "stdout": "5 rows processed"
    }
  ],
  "repair_logs": [
    {
      "attempt_number": 1,
      "original_error": "Table 'orders' does not exist",
      "ai_fix_reason": "Creating missing table",
      "repair_successful": true
    }
  ],
  "final_pipeline": [...],
  "overall_status": "success"
}
```

---

## 7. Non-Functional Requirements

### 7.1 Security

- [ ] Sandbox has no internet access
- [ ] No destructive SQL commands allowed (DROP TABLE, DELETE without WHERE)
- [ ] Bash command whitelist enforced (awk, sed, cp, curl only)
- [ ] No file writes outside `/tmp` within sandbox
- [ ] User isolation (each user can only access their own pipelines)
- [ ] SQL injection prevention via parameterized queries

### 7.2 Performance

- [ ] Pipeline generation: < 3 seconds
- [ ] Sandbox execution: < 10 seconds per step
- [ ] Database queries: < 1 second
- [ ] API response time: < 2 seconds (excluding LLM calls)

### 7.3 Reliability

- [ ] 100% step logging (no silent failures)
- [ ] Repair attempts limited to prevent infinite loops
- [ ] Database transaction rollback on failure
- [ ] Graceful error handling and user feedback
- [ ] Automatic cleanup of sandbox resources

### 7.4 Scalability

- [ ] Support up to 1000 pipelines
- [ ] Concurrent execution limit: 5 pipelines
- [ ] Database connection pooling

---

## 8. Acceptance Criteria (MVP Completion)

A complete QueryForge MVP must satisfy **all** of the following:

1. ✅ **Accept natural-language request** - System receives English description of data task
2. ✅ **Generate hybrid pipeline** - LLM creates valid Bash+SQL steps from request
3. ✅ **Introspect context** - MCP extracts schema and filesystem metadata
4. ✅ **Execute in sandbox** - Pipeline runs safely in isolated environment
5. ✅ **Detect errors** - System identifies failures with clear error messages
6. ✅ **Repair automatically** - LLM analyzes errors and generates fixes
7. ✅ **Retry execution** - Failed pipelines re-execute with repaired steps
8. ✅ **Commit to production** - Successful pipelines deployed to real DB/FS
9. ✅ **Maintain traceability** - All steps, errors, and repairs logged in database

**Project completion:** All 9 criteria met with test coverage > 80%

---

## 9. Glossary

| Term | Definition |
|------|-----------|
| **MCP** | Model Context Protocol - system for gathering schema/file metadata |
| **Pipeline** | Ordered sequence of Bash and SQL steps |
| **Sandbox** | Isolated execution environment with safety constraints |
| **Repair Loop** | Process of detecting errors, fixing, and retrying |
| **Schema Snapshot** | Pre-pipeline capture of database and filesystem state |
| **Commit** | Application of validated changes to production systems |

---

```

This improved PRD includes:
- **Clear hierarchical structure** with numbered sections
- **Acceptance criteria checklists** for each feature
- **Professional tables** for database schema and tech stack
- **JSON examples** for API specifications
- **Security & performance requirements** detailed
- **Architecture diagram** in ASCII format
- **Complete glossary** for terminology
- **Detailed acceptance criteria** for MVP completion

The document is now ready for development teams to reference.