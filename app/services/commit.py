"""
Commit Module for QueryForge
Handles safe production deployment of validated pipelines with transactional integrity
"""

import os
import sqlite3
import hashlib
import subprocess
import shutil
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings
from app.core.database import get_db_path
from app.services.mcp import MCPContextManager


class CommitStatus(Enum):
    """Commit status enumeration"""
    NOT_COMMITTED = "not_committed"
    COMMIT_IN_PROGRESS = "commit_in_progress"
    COMMITTED = "committed"
    COMMIT_FAILED = "commit_failed"
    ROLLED_BACK = "rolled_back"


class OperationType(Enum):
    """Filesystem operation type"""
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"
    MOVE = "move"


@dataclass
class ValidationReport:
    """Pre-commit validation report"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    risk_score: int
    risk_level: str  # low, medium, high
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level
        }


@dataclass
class CommitResult:
    """Result of commit operation"""
    success: bool
    pipeline_id: int
    commit_status: str
    snapshot_id: Optional[int] = None
    operations_performed: Optional[Dict[str, Any]] = None
    commit_time: Optional[str] = None
    rollback_available: bool = False
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "pipeline_id": self.pipeline_id,
            "commit_status": self.commit_status,
            "rollback_available": self.rollback_available
        }
        if self.snapshot_id:
            result["snapshot_id"] = self.snapshot_id
        if self.operations_performed:
            result["operations_performed"] = self.operations_performed
        if self.commit_time:
            result["commit_time"] = self.commit_time
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class RollbackResult:
    """Result of rollback operation"""
    success: bool
    pipeline_id: int
    operations_reversed: int
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "pipeline_id": self.pipeline_id,
            "operations_reversed": self.operations_reversed
        }
        if self.error:
            result["error"] = self.error
        return result


class ValidationEngine:
    """Pre-commit validation and risk assessment"""
    
    def __init__(self):
        self.db_path = get_db_path()
    
    def validate_for_commit(self, pipeline_id: int) -> ValidationReport:
        """
        Perform comprehensive pre-commit validation
        
        Args:
            pipeline_id: Pipeline to validate
            
        Returns:
            ValidationReport with validation results
        """
        errors = []
        warnings = []
        risk_score = 0
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Check 1: Pipeline exists
            cursor.execute("SELECT * FROM Pipelines WHERE id = ?", (pipeline_id,))
            pipeline = cursor.fetchone()
            if not pipeline:
                errors.append(f"Pipeline {pipeline_id} not found")
                return ValidationReport(False, errors, warnings, 0, "unknown")
            
            # Check 2: Pipeline status must be sandbox_success or repaired_success
            status = pipeline['status']
            if status not in ('sandbox_success', 'repaired_success', 'success'):
                errors.append(f"Pipeline status is '{status}'. Must be 'sandbox_success' or 'repaired_success' before commit.")
            
            # Check 3: Latest execution must be successful
            cursor.execute("""
                SELECT is_successful FROM Execution_Logs 
                WHERE pipeline_id = ? 
                ORDER BY run_time DESC LIMIT 1
            """, (pipeline_id,))
            latest_exec = cursor.fetchone()
            if not latest_exec or not latest_exec['is_successful']:
                errors.append("Latest execution was not successful")
            
            # Check 4: No pending repair attempts
            cursor.execute("""
                SELECT COUNT(*) as count FROM Repair_Logs 
                WHERE pipeline_id = ? AND repair_successful = 0
            """, (pipeline_id,))
            pending_repairs = cursor.fetchone()['count']
            if pending_repairs > 0:
                warnings.append(f"{pending_repairs} unsuccessful repair attempts exist")
            
            # Check 5: Get pipeline steps for risk assessment
            cursor.execute("""
                SELECT code_type, script_content FROM Pipeline_Steps 
                WHERE pipeline_id = ? ORDER BY step_number
            """, (pipeline_id,))
            steps = cursor.fetchall()
            
            sql_operations = 0
            destructive_operations = 0
            file_deletions = 0
            
            for step in steps:
                if step['code_type'] == 'sql':
                    sql_operations += 1
                    content_upper = step['script_content'].upper()
                    
                    # Check for destructive operations
                    if 'DROP TABLE' in content_upper or 'DROP DATABASE' in content_upper:
                        destructive_operations += 1
                        warnings.append("Pipeline contains DROP TABLE operation")
                    if 'TRUNCATE' in content_upper:
                        destructive_operations += 1
                        warnings.append("Pipeline contains TRUNCATE operation")
                    if 'DELETE' in content_upper and 'WHERE' not in content_upper:
                        destructive_operations += 1
                        warnings.append("Pipeline contains DELETE without WHERE clause")
                
                elif step['code_type'] == 'bash':
                    content_lower = step['script_content'].lower()
                    if 'rm ' in content_lower or 'rm -' in content_lower:
                        file_deletions += 1
                        warnings.append("Pipeline contains file deletion operation")
            
            # Calculate risk score
            risk_score = sql_operations  # 1 point per SQL operation
            risk_score += destructive_operations * 10  # 10 points per destructive op
            risk_score += file_deletions * 5  # 5 points per file deletion
            risk_score += len(steps) * 2  # 2 points per table affected (approximate)
            
            # Determine risk level
            if risk_score <= 10:
                risk_level = "low"
            elif risk_score <= 30:
                risk_level = "medium"
            else:
                risk_level = "high"
                warnings.append(f"High risk score: {risk_score}")
            
        finally:
            conn.close()
        
        is_valid = len(errors) == 0
        
        return ValidationReport(is_valid, errors, warnings, risk_score, risk_level)


class SnapshotManager:
    """Manages pre/post-commit database and filesystem snapshots"""
    
    def __init__(self):
        self.db_path = get_db_path()
        self.mcp = MCPContextManager()
    
    def create_snapshot(self, pipeline_id: int) -> int:
        """
        Create a snapshot of current database and filesystem state
        
        Args:
            pipeline_id: Pipeline ID for snapshot
            
        Returns:
            Snapshot ID
        """
        # Get current context from MCP
        context = self.mcp.get_full_context()
        
        db_structure = json.dumps(context.get('database', {}))
        file_list = json.dumps(context.get('filesystem', {}))
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO Schema_Snapshots (pipeline_id, db_structure, file_list, snapshot_time)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (pipeline_id, db_structure, file_list))
            
            snapshot_id = cursor.lastrowid
            conn.commit()
            
            return snapshot_id
            
        finally:
            conn.close()
    
    def get_snapshot(self, snapshot_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a snapshot by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM Schema_Snapshots WHERE id = ?
            """, (snapshot_id,))
            
            row = cursor.fetchone()
            if row:
                return {
                    "id": row['id'],
                    "pipeline_id": row['pipeline_id'],
                    "db_structure": json.loads(row['db_structure']),
                    "file_list": json.loads(row['file_list']),
                    "snapshot_time": row['snapshot_time']
                }
            return None
            
        finally:
            conn.close()


class DatabaseCommitter:
    """Handles transactional SQL execution on production database"""
    
    def __init__(self):
        self.db_path = get_db_path()
    
    def commit_sql_operations(self, pipeline_id: int, sql_steps: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Execute SQL steps in a single transaction
        
        Args:
            pipeline_id: Pipeline ID
            sql_steps: List of SQL steps to execute
            
        Returns:
            Tuple of (success, error_message)
        """
        if not sql_steps:
            return True, None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction
            cursor.execute("BEGIN TRANSACTION")
            
            for step in sql_steps:
                step_id = step['id']
                sql_content = step['script_content']
                
                # Remove transaction commands from SQL content (we handle transactions here)
                # Remove BEGIN TRANSACTION, COMMIT, ROLLBACK statements
                lines = sql_content.split('\n')
                cleaned_lines = []
                for line in lines:
                    line_upper = line.strip().upper()
                    # Skip transaction control statements
                    if line_upper.startswith('BEGIN TRANSACTION') or \
                       line_upper.startswith('COMMIT') or \
                       line_upper.startswith('ROLLBACK'):
                        continue
                    # Skip comment lines that mention transaction
                    if line.strip().startswith('--') and 'transaction' in line_upper:
                        continue
                    cleaned_lines.append(line)
                
                sql_content_cleaned = '\n'.join(cleaned_lines).strip()
                
                # Skip if only transaction commands were present
                if not sql_content_cleaned:
                    continue
                
                start_time = time.time()
                
                try:
                    # Split SQL into individual statements and execute each
                    statements = [s.strip() for s in sql_content_cleaned.split(';') if s.strip()]
                    for statement in statements:
                        if statement:
                            cursor.execute(statement)
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    
                    # Log successful execution
                    cursor.execute("""
                        INSERT INTO Execution_Logs 
                        (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code, execution_time_ms)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 1, 'SQL executed successfully', '', 0, ?)
                    """, (pipeline_id, step_id, execution_time_ms))
                    
                except sqlite3.Error as e:
                    # Log failed execution
                    cursor.execute("""
                        INSERT INTO Execution_Logs 
                        (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code, execution_time_ms)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 0, '', ?, 1, 0)
                    """, (pipeline_id, step_id, str(e)))
                    
                    # Rollback transaction
                    conn.rollback()
                    return False, f"SQL execution failed: {str(e)}"
            
            # Commit transaction
            conn.commit()
            return True, None
            
        except Exception as e:
            conn.rollback()
            return False, f"Transaction error: {str(e)}"
            
        finally:
            conn.close()


class FilesystemCommitter:
    """Handles bash operations on production filesystem with change logging"""
    
    def __init__(self):
        self.db_path = get_db_path()
        self.data_directory = Path(settings.DATA_DIRECTORY)
        self.backup_directory = Path(settings.DATA_DIRECTORY) / ".backups"
        self.backup_directory.mkdir(exist_ok=True)
    
    def _calculate_file_hash(self, file_path: str) -> Optional[str]:
        """Calculate SHA256 hash of file"""
        try:
            if not os.path.exists(file_path):
                return None
            
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception:
            return None
    
    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create backup of file before modification"""
        try:
            if not os.path.exists(file_path):
                return None
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.basename(file_path)
            backup_filename = f"{filename}_{timestamp}.bak"
            backup_path = self.backup_directory / backup_filename
            
            shutil.copy2(file_path, backup_path)
            return str(backup_path)
        except Exception:
            return None
    
    def commit_file_operations(self, pipeline_id: int, bash_steps: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        Execute bash steps on production filesystem
        
        Args:
            pipeline_id: Pipeline ID
            bash_steps: List of bash steps to execute
            
        Returns:
            Tuple of (success, error_message)
        """
        if not bash_steps:
            return True, None
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for step in bash_steps:
                step_id = step['id']
                bash_content = step['script_content']
                
                # Create temporary script file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = self.data_directory / f"commit_script_{timestamp}.sh"
                
                with open(script_path, 'w') as f:
                    f.write("#!/bin/bash\n")
                    f.write("set -e\n")  # Exit on error
                    f.write(bash_content)
                
                # Make executable
                os.chmod(script_path, 0o755)
                
                start_time = time.time()
                
                try:
                    # Execute bash script
                    result = subprocess.run(
                        ['bash', str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                        cwd=str(self.data_directory)
                    )
                    
                    execution_time_ms = int((time.time() - start_time) * 1000)
                    
                    # Log execution
                    cursor.execute("""
                        INSERT INTO Execution_Logs 
                        (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code, execution_time_ms)
                        VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
                    """, (pipeline_id, step_id, result.returncode == 0, 
                          result.stdout, result.stderr, result.returncode, execution_time_ms))
                    
                    if result.returncode != 0:
                        conn.commit()
                        return False, f"Bash execution failed: {result.stderr}"
                    
                except subprocess.TimeoutExpired:
                    cursor.execute("""
                        INSERT INTO Execution_Logs 
                        (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code, execution_time_ms)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 0, '', 'Execution timeout', 124, 10000)
                    """, (pipeline_id, step_id))
                    conn.commit()
                    return False, "Bash execution timeout"
                
                except Exception as e:
                    cursor.execute("""
                        INSERT INTO Execution_Logs 
                        (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code, execution_time_ms)
                        VALUES (?, ?, CURRENT_TIMESTAMP, 0, '', ?, 1, 0)
                    """, (pipeline_id, step_id, str(e)))
                    conn.commit()
                    return False, f"Bash execution error: {str(e)}"
                
                finally:
                    # Clean up script file
                    if script_path.exists():
                        script_path.unlink()
            
            conn.commit()
            return True, None
            
        finally:
            conn.close()


class CommitService:
    """Orchestrates commit workflow and validation"""
    
    def __init__(self):
        self.db_path = get_db_path()
        self.validator = ValidationEngine()
        self.snapshot_manager = SnapshotManager()
        self.db_committer = DatabaseCommitter()
        self.fs_committer = FilesystemCommitter()
    
    def validate_for_commit(self, pipeline_id: int) -> ValidationReport:
        """
        Validate pipeline before commit
        
        Args:
            pipeline_id: Pipeline to validate
            
        Returns:
            ValidationReport
        """
        return self.validator.validate_for_commit(pipeline_id)
    
    def commit_pipeline(self, pipeline_id: int, force_commit: bool = False) -> CommitResult:
        """
        Commit pipeline to production
        
        Args:
            pipeline_id: Pipeline to commit
            force_commit: Skip high-risk validation
            
        Returns:
            CommitResult
        """
        # Validate
        validation = self.validate_for_commit(pipeline_id)
        
        if not validation.is_valid:
            return CommitResult(
                success=False,
                pipeline_id=pipeline_id,
                commit_status=CommitStatus.COMMIT_FAILED.value,
                error=f"Validation failed: {', '.join(validation.errors)}"
            )
        
        # Check risk level
        if validation.risk_level == "high" and not force_commit:
            return CommitResult(
                success=False,
                pipeline_id=pipeline_id,
                commit_status=CommitStatus.COMMIT_FAILED.value,
                error=f"High-risk pipeline (score: {validation.risk_score}). Set force_commit=true to proceed."
            )
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # Update pipeline status
            cursor.execute("""
                UPDATE Pipelines 
                SET commit_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (CommitStatus.COMMIT_IN_PROGRESS.value, pipeline_id))
            conn.commit()
            
            # Create pre-commit snapshot
            snapshot_id = self.snapshot_manager.create_snapshot(pipeline_id)
            
            # Get pipeline steps
            cursor.execute("""
                SELECT id, step_number, code_type, script_content 
                FROM Pipeline_Steps 
                WHERE pipeline_id = ? 
                ORDER BY step_number
            """, (pipeline_id,))
            
            steps = [dict(row) for row in cursor.fetchall()]
            
            # Separate SQL and bash steps
            sql_steps = [s for s in steps if s['code_type'] == 'sql']
            bash_steps = [s for s in steps if s['code_type'] == 'bash']
            
            operations_performed = {
                "sql_operations": len(sql_steps),
                "file_operations": len(bash_steps),
                "total_steps": len(steps)
            }
            
            # Commit SQL operations
            if sql_steps:
                success, error = self.db_committer.commit_sql_operations(pipeline_id, sql_steps)
                if not success:
                    cursor.execute("""
                        UPDATE Pipelines 
                        SET commit_status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (CommitStatus.COMMIT_FAILED.value, pipeline_id))
                    conn.commit()
                    return CommitResult(
                        success=False,
                        pipeline_id=pipeline_id,
                        commit_status=CommitStatus.COMMIT_FAILED.value,
                        snapshot_id=snapshot_id,
                        error=error,
                        rollback_available=True
                    )
            
            # Commit file operations
            if bash_steps:
                success, error = self.fs_committer.commit_file_operations(pipeline_id, bash_steps)
                if not success:
                    cursor.execute("""
                        UPDATE Pipelines 
                        SET commit_status = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (CommitStatus.COMMIT_FAILED.value, pipeline_id))
                    conn.commit()
                    return CommitResult(
                        success=False,
                        pipeline_id=pipeline_id,
                        commit_status=CommitStatus.COMMIT_FAILED.value,
                        snapshot_id=snapshot_id,
                        error=error,
                        rollback_available=False
                    )
            
            # Update pipeline as committed
            commit_time = datetime.now().isoformat()
            cursor.execute("""
                UPDATE Pipelines 
                SET commit_status = ?, commit_time = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (CommitStatus.COMMITTED.value, commit_time, pipeline_id))
            conn.commit()
            
            return CommitResult(
                success=True,
                pipeline_id=pipeline_id,
                commit_status=CommitStatus.COMMITTED.value,
                snapshot_id=snapshot_id,
                operations_performed=operations_performed,
                commit_time=commit_time,
                rollback_available=True
            )
            
        except Exception as e:
            cursor.execute("""
                UPDATE Pipelines 
                SET commit_status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (CommitStatus.COMMIT_FAILED.value, pipeline_id))
            conn.commit()
            
            return CommitResult(
                success=False,
                pipeline_id=pipeline_id,
                commit_status=CommitStatus.COMMIT_FAILED.value,
                error=f"Commit error: {str(e)}"
            )
            
        finally:
            conn.close()
    
    def rollback_commit(self, pipeline_id: int) -> RollbackResult:
        """
        Rollback a committed pipeline (limited support)
        
        Args:
            pipeline_id: Pipeline to rollback
            
        Returns:
            RollbackResult
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if pipeline is committed
            cursor.execute("""
                SELECT commit_status FROM Pipelines WHERE id = ?
            """, (pipeline_id,))
            
            row = cursor.fetchone()
            if not row:
                return RollbackResult(False, pipeline_id, 0, "Pipeline not found")
            
            commit_status = row[0]
            if commit_status != CommitStatus.COMMITTED.value:
                return RollbackResult(False, pipeline_id, 0, f"Pipeline not committed (status: {commit_status})")
            
            # Note: Database rollback not supported after commit
            # Only filesystem changes can be rolled back
            
            cursor.execute("""
                SELECT COUNT(*) FROM Filesystem_Changes 
                WHERE pipeline_id = ? AND rolled_back = 0
            """, (pipeline_id,))
            
            reversible_ops = cursor.fetchone()[0]
            
            # Update pipeline status
            cursor.execute("""
                UPDATE Pipelines 
                SET commit_status = ?, rollback_time = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (CommitStatus.ROLLED_BACK.value, pipeline_id))
            
            conn.commit()
            
            return RollbackResult(
                success=True,
                pipeline_id=pipeline_id,
                operations_reversed=0,  # Manual rollback required
                error="Database operations cannot be automatically rolled back after commit. Manual intervention required."
            )
            
        finally:
            conn.close()
