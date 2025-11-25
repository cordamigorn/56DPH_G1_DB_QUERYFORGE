"""
Database connection and schema management
"""
import sqlite3
import aiosqlite
from typing import AsyncGenerator
from contextlib import asynccontextmanager
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


# Database schema definition
SCHEMA_SQL = """
-- Pipelines table: Stores pipeline metadata and status
CREATE TABLE IF NOT EXISTS Pipelines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    prompt_text TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CHECK (status IN ('pending', 'running', 'success', 'failed', 'repaired'))
);

CREATE INDEX IF NOT EXISTS idx_pipelines_user_id ON Pipelines(user_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_status ON Pipelines(status);

-- Pipeline_Steps table: Individual executable steps within a pipeline
CREATE TABLE IF NOT EXISTS Pipeline_Steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    step_number INTEGER NOT NULL,
    code_type VARCHAR(10) NOT NULL,
    script_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES Pipelines(id) ON DELETE CASCADE,
    CHECK (code_type IN ('bash', 'sql')),
    UNIQUE(pipeline_id, step_number)
);

CREATE INDEX IF NOT EXISTS idx_steps_pipeline ON Pipeline_Steps(pipeline_id);

-- Schema_Snapshots table: Pre-execution snapshots of database and filesystem state
CREATE TABLE IF NOT EXISTS Schema_Snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    db_structure JSON NOT NULL,
    file_list JSON NOT NULL,
    snapshot_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pipeline_id) REFERENCES Pipelines(id) ON DELETE CASCADE
);

-- Execution_Logs table: Detailed execution records for each pipeline step
CREATE TABLE IF NOT EXISTS Execution_Logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    step_id INTEGER NOT NULL,
    run_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_successful BOOLEAN NOT NULL,
    stdout TEXT,
    stderr TEXT,
    exit_code INTEGER,
    execution_time_ms INTEGER,
    FOREIGN KEY (pipeline_id) REFERENCES Pipelines(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES Pipeline_Steps(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_pipeline ON Execution_Logs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_execution_step ON Execution_Logs(step_id);

-- Repair_Logs table: Tracks automatic repair attempts
CREATE TABLE IF NOT EXISTS Repair_Logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL,
    original_error TEXT NOT NULL,
    ai_fix_reason TEXT NOT NULL,
    patched_code TEXT NOT NULL,
    repair_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    repair_successful BOOLEAN NOT NULL,
    FOREIGN KEY (pipeline_id) REFERENCES Pipelines(id) ON DELETE CASCADE,
    CHECK (attempt_number BETWEEN 1 AND 3),
    UNIQUE(pipeline_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS idx_repair_pipeline ON Repair_Logs(pipeline_id);
"""


def get_db_path() -> str:
    """
    Get database file path from configuration
    
    Returns:
        str: Database file path
    """
    # Extract path from SQLite URL (sqlite:///./queryforge.db -> ./queryforge.db)
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite:///"):
        return db_url.replace("sqlite:///", "")
    return db_url


def init_database() -> None:
    """
    Initialize database schema synchronously
    Creates all tables and indexes if they don't exist
    """
    db_path = get_db_path()
    logger.info(f"Initializing database at: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
        # Execute schema creation
        cursor.executescript(SCHEMA_SQL)
        
        conn.commit()
        logger.info("Database schema initialized successfully")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Created tables: {[t[0] for t in tables]}")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def init_database_async() -> None:
    """
    Initialize database schema asynchronously
    Creates all tables and indexes if they don't exist
    """
    db_path = get_db_path()
    logger.info(f"Initializing database asynchronously at: {db_path}")
    
    try:
        async with aiosqlite.connect(db_path) as db:
            # Enable foreign key constraints
            await db.execute("PRAGMA foreign_keys = ON")
            
            # Execute schema creation
            await db.executescript(SCHEMA_SQL)
            
            await db.commit()
            logger.info("Database schema initialized successfully (async)")
            
    except Exception as e:
        logger.error(f"Error initializing database (async): {e}")
        raise


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    Async context manager for database connections
    
    Yields:
        aiosqlite.Connection: Async database connection
        
    Usage:
        async with get_db() as db:
            await db.execute("SELECT * FROM Pipelines")
    """
    db_path = get_db_path()
    
    async with aiosqlite.connect(db_path) as db:
        # Enable foreign key constraints
        await db.execute("PRAGMA foreign_keys = ON")
        # Enable row factory for dict-like access
        db.row_factory = aiosqlite.Row
        
        try:
            yield db
        except Exception as e:
            logger.error(f"Database error: {e}")
            await db.rollback()
            raise
        else:
            await db.commit()


def verify_schema() -> bool:
    """
    Verify database schema integrity
    
    Returns:
        bool: True if schema is valid
        
    Raises:
        ValueError: If schema is invalid
    """
    db_path = get_db_path()
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check for required tables
        required_tables = ['Pipelines', 'Pipeline_Steps', 'Schema_Snapshots', 
                          'Execution_Logs', 'Repair_Logs']
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        missing_tables = set(required_tables) - set(existing_tables)
        if missing_tables:
            raise ValueError(f"Missing required tables: {missing_tables}")
        
        logger.info("Database schema verification successful")
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Schema verification failed: {e}")
        raise


# Initialize database on module import (for testing)
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize database
    init_database()
    
    # Verify schema
    verify_schema()
    
    print("Database initialized and verified successfully!")
