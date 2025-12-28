"""
Error Detection & Repair Loop Module
Automatically detects, analyzes, and repairs pipeline execution failures
"""
import re
import time
import sqlite3
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

import google.generativeai as genai

from app.core.config import settings
from app.core.database import get_db_path
from app.services.llm import GeminiClient

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error classification categories"""
    FILE_NOT_FOUND = "file_not_found"
    TABLE_MISSING = "table_missing"
    SYNTAX_ERROR = "syntax_error"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    DATA_VALIDATION = "data_validation"
    SCHEMA_MISMATCH = "schema_mismatch"
    UNKNOWN = "unknown"


class ErrorReport:
    """Container for error analysis results"""
    
    def __init__(
        self,
        execution_log_id: int,
        pipeline_id: int,
        step_id: int,
        step_number: int,
        step_type: str,
        original_content: str,
        error_message: str,
        exit_code: int,
        category: ErrorCategory = ErrorCategory.UNKNOWN
    ):
        self.execution_log_id = execution_log_id
        self.pipeline_id = pipeline_id
        self.step_id = step_id
        self.step_number = step_number
        self.step_type = step_type
        self.original_content = original_content
        self.error_message = error_message
        self.exit_code = exit_code
        self.category = category
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "execution_log_id": self.execution_log_id,
            "pipeline_id": self.pipeline_id,
            "step_id": self.step_id,
            "step_number": self.step_number,
            "step_type": self.step_type,
            "original_content": self.original_content,
            "error_message": self.error_message,
            "exit_code": self.exit_code,
            "category": self.category.value
        }


class ContextSnapshot:
    """Container for repair context information"""
    
    def __init__(
        self,
        database_schema: Dict[str, Any],
        file_list: List[str],
        previous_steps: List[Dict[str, Any]],
        pipeline_prompt: str
    ):
        self.database_schema = database_schema
        self.file_list = file_list
        self.previous_steps = previous_steps
        self.pipeline_prompt = pipeline_prompt
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "database_schema": self.database_schema,
            "file_list": self.file_list,
            "previous_steps": self.previous_steps,
            "pipeline_prompt": self.pipeline_prompt
        }


class ErrorAnalyzer:
    """Analyzes execution failures and classifies error types"""
    
    def __init__(self):
        logger.info("Error analyzer initialized")
    
    def analyze_execution_failure(self, execution_log_id: int) -> Optional[ErrorReport]:
        """
        Extract error details from execution log
        
        Args:
            execution_log_id: ID of failed execution log
            
        Returns:
            ErrorReport object or None if not found
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Load execution log with step details
        cursor.execute("""
            SELECT 
                el.id as log_id,
                el.pipeline_id,
                el.step_id,
                el.stderr,
                el.exit_code,
                ps.step_number,
                ps.code_type,
                ps.script_content
            FROM Execution_Logs el
            JOIN Pipeline_Steps ps ON el.step_id = ps.id
            WHERE el.id = ? AND el.is_successful = 0
        """, (execution_log_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.error(f"Execution log {execution_log_id} not found or not failed")
            return None
        
        # Create error report
        error_message = row["stderr"] or "Unknown error"
        
        report = ErrorReport(
            execution_log_id=row["log_id"],
            pipeline_id=row["pipeline_id"],
            step_id=row["step_id"],
            step_number=row["step_number"],
            step_type=row["code_type"],
            original_content=row["script_content"],
            error_message=error_message,
            exit_code=row["exit_code"]
        )
        
        # Classify error
        report.category = self.classify_error_type(error_message)
        
        logger.info(f"Analyzed error: category={report.category.value}, step={report.step_number}")
        
        return report
    
    def classify_error_type(self, error_message: str) -> ErrorCategory:
        """
        Classify error type based on error message
        
        Args:
            error_message: Error text from stderr
            
        Returns:
            ErrorCategory enum value
        """
        error_lower = error_message.lower()
        
        # Database table errors (check BEFORE file errors due to "does not exist" overlap)
        if any(pattern in error_lower for pattern in [
            "table does not exist",
            "no such table",
            "unknown table"
        ]):
            return ErrorCategory.TABLE_MISSING
        
        # File-related errors
        if any(pattern in error_lower for pattern in [
            "no such file",
            "cannot open",
            "file not found",
            "does not exist"
        ]):
            return ErrorCategory.FILE_NOT_FOUND
        
        # Syntax errors
        if any(pattern in error_lower for pattern in [
            "syntax error",
            "unexpected token",
            "parse error",
            "invalid syntax"
        ]):
            return ErrorCategory.SYNTAX_ERROR
        
        # Permission errors
        if any(pattern in error_lower for pattern in [
            "permission denied",
            "access denied",
            "forbidden"
        ]):
            return ErrorCategory.PERMISSION_DENIED
        
        # Timeout errors
        if any(pattern in error_lower for pattern in [
            "timeout",
            "timed out",
            "time limit exceeded"
        ]):
            return ErrorCategory.TIMEOUT
        
        # Data validation errors
        if any(pattern in error_lower for pattern in [
            "constraint violation",
            "null value",
            "integrity constraint",
            "foreign key constraint"
        ]):
            return ErrorCategory.DATA_VALIDATION
        
        # Schema mismatch
        if any(pattern in error_lower for pattern in [
            "column",
            "field",
            "mismatch",
            "incompatible"
        ]):
            return ErrorCategory.SCHEMA_MISMATCH
        
        return ErrorCategory.UNKNOWN
    
    def extract_relevant_context(
        self,
        pipeline_id: int,
        step_id: int
    ) -> ContextSnapshot:
        """
        Gather context information for repair
        
        Args:
            pipeline_id: Pipeline identifier
            step_id: Failed step identifier
            
        Returns:
            ContextSnapshot object
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get pipeline prompt
        cursor.execute(
            "SELECT prompt_text FROM Pipelines WHERE id = ?",
            (pipeline_id,)
        )
        row = cursor.fetchone()
        pipeline_prompt = row["prompt_text"] if row else ""
        
        # Get previous successful steps
        cursor.execute("""
            SELECT step_number, code_type, script_content
            FROM Pipeline_Steps
            WHERE pipeline_id = ? AND step_number < (
                SELECT step_number FROM Pipeline_Steps WHERE id = ?
            )
            ORDER BY step_number
        """, (pipeline_id, step_id))
        
        previous_steps = [dict(row) for row in cursor.fetchall()]
        
        # Get schema snapshot
        cursor.execute(
            "SELECT db_structure, file_list FROM Schema_Snapshots WHERE pipeline_id = ? ORDER BY snapshot_time DESC LIMIT 1",
            (pipeline_id,)
        )
        row = cursor.fetchone()
        
        if row:
            import json
            database_schema = json.loads(row["db_structure"])
            file_list = json.loads(row["file_list"])
        else:
            database_schema = {}
            file_list = []
        
        conn.close()
        
        return ContextSnapshot(
            database_schema=database_schema,
            file_list=file_list,
            previous_steps=previous_steps,
            pipeline_prompt=pipeline_prompt
        )


class RepairModule:
    """Generates corrected pipeline steps using LLM"""
    
    def __init__(self):
        self.gemini_client = GeminiClient()
        self.repair_history: Dict[int, List[str]] = {}  # pipeline_id -> list of fix hashes
        logger.info("Repair module initialized")
    
    def generate_fix(
        self,
        error_report: ErrorReport,
        context: ContextSnapshot
    ) -> Dict[str, Any]:
        """
        Create corrected step using LLM
        
        Args:
            error_report: Error analysis results
            context: Context information for repair
            
        Returns:
            Dictionary with repair result
            
        Response structure:
            {
                "success": bool,
                "patched_code": str (if success),
                "fix_reason": str (if success),
                "error": str (if failure)
            }
        """
        logger.info(f"Generating fix for step {error_report.step_number}, category={error_report.category.value}")
        
        # Build repair prompt
        prompt = self._build_repair_prompt(error_report, context)
        
        # Call Gemini API
        api_response = self.gemini_client.generate_content(prompt)
        
        if not api_response["success"]:
            return {
                "success": False,
                "error": api_response.get("error", "API call failed")
            }
        
        # Parse response
        parse_result = self._parse_repair_response(api_response["response"])
        
        if not parse_result["success"]:
            return {
                "success": False,
                "error": parse_result.get("error", "Failed to parse repair response")
            }
        
        patched_code = parse_result["patched_code"]
        fix_reason = parse_result["fix_reason"]
        
        # Check for duplicate fix
        if self._is_duplicate_fix(error_report.pipeline_id, patched_code):
            logger.warning("Duplicate fix detected")
            return {
                "success": False,
                "error": "LLM generated identical fix to previous attempt"
            }
        
        # Record fix hash
        self._record_fix(error_report.pipeline_id, patched_code)
        
        return {
            "success": True,
            "patched_code": patched_code,
            "fix_reason": fix_reason
        }
    
    def _build_repair_prompt(
        self,
        error_report: ErrorReport,
        context: ContextSnapshot
    ) -> str:
        """
        Build LLM prompt for repair
        
        Args:
            error_report: Error analysis results
            context: Context information
            
        Returns:
            Complete repair prompt
        """
        # Extract database table info
        tables = context.database_schema.get("tables", [])
        table_descriptions = []
        for table in tables:
            table_name = table.get("name", "unknown")
            columns = table.get("columns", [])
            column_desc = ", ".join([
                f"{col.get('name', '?')} ({col.get('type', '?')})"
                for col in columns
            ])
            table_descriptions.append(f"- {table_name}: {column_desc}")
        
        tables_text = "\n".join(table_descriptions) if table_descriptions else "No tables available"
        
        # Extract file list
        files_text = "\n".join([f"- {f}" for f in context.file_list]) if context.file_list else "No files available"
        
        # Format previous steps
        previous_steps_text = ""
        if context.previous_steps:
            for step in context.previous_steps:
                previous_steps_text += f"\nStep {step['step_number']} ({step['code_type']}):\n{step['script_content']}\n"
        else:
            previous_steps_text = "No previous steps"
        
        # Sanitize error message to avoid safety triggers
        sanitized_error = error_report.error_message.replace("bash:", "shell:")
        sanitized_error = sanitized_error.replace("/usr/bin/bash", "shell")
        
        # Build prompt with safer language
        prompt = f"""You are a helpful code correction assistant. A data processing step encountered an issue.

AVAILABLE RESOURCES:
Database Tables:
{tables_text}

Data Files:
{files_text}

Allowed Shell Commands: {', '.join(settings.ALLOWED_BASH_COMMANDS)}

User Request: {context.pipeline_prompt}

PREVIOUS STEPS:
{previous_steps_text}

STEP THAT NEEDS CORRECTION:
Step {error_report.step_number} ({error_report.step_type}):
{error_report.original_content}

ISSUE DETECTED:
Category: {error_report.category.value}
Details: {sanitized_error}

PLEASE PROVIDE:
A corrected version of the step that resolves the issue.

OUTPUT FORMAT (JSON only):
{{
  "fix_reason": "explanation of the correction",
  "patched_code": "corrected {error_report.step_type} code"
}}

IMPORTANT:
- Return valid JSON only
- No markdown formatting
- Use only listed resources
- Correct the specific issue mentioned"""
        
        return prompt
    
    def _parse_repair_response(self, response_text: str) -> Dict[str, Any]:
        """
        Parse LLM repair response
        
        Args:
            response_text: Raw response from Gemini
            
        Returns:
            Dictionary with parsing result
        """
        try:
            import json
            
            # Remove markdown code blocks
            text = re.sub(r'```json\s*', '', response_text)
            text = re.sub(r'```\s*', '', text)
            
            # Parse JSON
            data = json.loads(text.strip())
            
            # Validate required fields
            if "patched_code" not in data:
                return {
                    "success": False,
                    "error": "Missing 'patched_code' in response"
                }
            
            if "fix_reason" not in data:
                data["fix_reason"] = "No explanation provided"
            
            return {
                "success": True,
                "patched_code": data["patched_code"],
                "fix_reason": data["fix_reason"]
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return {
                "success": False,
                "error": f"Invalid JSON in response: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _is_duplicate_fix(self, pipeline_id: int, patched_code: str) -> bool:
        """
        Check if fix is duplicate of previous attempt
        
        Args:
            pipeline_id: Pipeline identifier
            patched_code: Proposed fix code
            
        Returns:
            True if duplicate, False otherwise
        """
        # Calculate hash of patched code
        code_hash = hashlib.md5(patched_code.encode()).hexdigest()
        
        # Check against previous fixes for this pipeline
        if pipeline_id in self.repair_history:
            if code_hash in self.repair_history[pipeline_id]:
                return True
        
        return False
    
    def _record_fix(self, pipeline_id: int, patched_code: str):
        """
        Record fix hash to detect duplicates
        
        Args:
            pipeline_id: Pipeline identifier
            patched_code: Fix code
        """
        code_hash = hashlib.md5(patched_code.encode()).hexdigest()
        
        if pipeline_id not in self.repair_history:
            self.repair_history[pipeline_id] = []
        
        self.repair_history[pipeline_id].append(code_hash)
    
    def validate_fix(self, patched_code: str, step_type: str) -> Tuple[bool, Optional[str]]:
        """
        Verify fix is valid before application
        
        Args:
            patched_code: Corrected code
            step_type: 'bash' or 'sql'
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic validation
        if not patched_code or not patched_code.strip():
            return False, "Patched code is empty"
        
        # Type-specific validation
        if step_type == "bash":
            # Check for prohibited commands
            lines = patched_code.split('\n')
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                tokens = line.split()
                if tokens:
                    command = tokens[0]
                    if command not in settings.ALLOWED_BASH_COMMANDS and command not in ['echo', 'set', 'if', 'then', 'fi', 'for', 'while', 'done']:
                        return False, f"Prohibited command in fix: {command}"
        
        elif step_type == "sql":
            # Basic SQL validation
            upper = patched_code.upper()
            if "DROP TABLE" in upper or "TRUNCATE" in upper:
                return False, "Destructive SQL operation in fix"
        
        return True, None
    
    def apply_fix(
        self,
        pipeline_id: int,
        step_id: int,
        patched_code: str
    ) -> bool:
        """
        Update step in database with corrected code
        
        Args:
            pipeline_id: Pipeline identifier
            step_id: Step identifier
            patched_code: Corrected code
            
        Returns:
            True if successful, False otherwise
        """
        db_path = get_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE Pipeline_Steps SET script_content = ? WHERE id = ? AND pipeline_id = ?",
                (patched_code, step_id, pipeline_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Applied fix to step {step_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to apply fix: {e}")
            return False


class RepairLoop:
    """Orchestrates the error detection and repair workflow"""
    
    def __init__(self):
        self.error_analyzer = ErrorAnalyzer()
        self.repair_module = RepairModule()
        self.max_attempts = settings.MAX_REPAIR_ATTEMPTS
        logger.info(f"Repair loop initialized with max_attempts={self.max_attempts}")
    
    def repair_and_retry(
        self,
        pipeline_id: int,
        execution_log_id: int
    ) -> Dict[str, Any]:
        """
        Execute repair loop for failed pipeline
        
        Args:
            pipeline_id: Pipeline identifier
            execution_log_id: Failed execution log ID
            
        Returns:
            Dictionary with repair result
            
        Response structure:
            {
                "success": bool,
                "attempts": int,
                "final_status": str,
                "error": str (if failure)
            }
        """
        logger.info(f"Starting repair loop for pipeline {pipeline_id}")
        
        # Check current attempt count
        current_attempts = self._get_repair_attempt_count(pipeline_id)
        
        if current_attempts >= self.max_attempts:
            logger.error(f"Maximum repair attempts ({self.max_attempts}) already reached")
            self._mark_pipeline_failed(pipeline_id)
            return {
                "success": False,
                "attempts": current_attempts,
                "final_status": "failed",
                "error": f"Maximum repair attempts ({self.max_attempts}) exceeded"
            }
        
        # Analyze error
        error_report = self.error_analyzer.analyze_execution_failure(execution_log_id)
        
        if not error_report:
            return {
                "success": False,
                "attempts": current_attempts,
                "final_status": "failed",
                "error": "Failed to analyze execution error"
            }
        
        # Extract context
        context = self.error_analyzer.extract_relevant_context(
            pipeline_id,
            error_report.step_id
        )
        
        # Generate fix
        fix_result = self.repair_module.generate_fix(error_report, context)
        
        if not fix_result["success"]:
            self._log_repair_attempt(
                pipeline_id=pipeline_id,
                attempt_number=current_attempts + 1,
                original_error=error_report.error_message,
                ai_fix_reason="Failed to generate fix",
                patched_code="",
                repair_successful=False
            )
            return {
                "success": False,
                "attempts": current_attempts + 1,
                "final_status": "failed",
                "error": fix_result.get("error", "Fix generation failed")
            }
        
        patched_code = fix_result["patched_code"]
        fix_reason = fix_result["fix_reason"]
        
        # Validate fix
        is_valid, validation_error = self.repair_module.validate_fix(
            patched_code,
            error_report.step_type
        )
        
        if not is_valid:
            self._log_repair_attempt(
                pipeline_id=pipeline_id,
                attempt_number=current_attempts + 1,
                original_error=error_report.error_message,
                ai_fix_reason=fix_reason,
                patched_code=patched_code,
                repair_successful=False
            )
            return {
                "success": False,
                "attempts": current_attempts + 1,
                "final_status": "failed",
                "error": f"Fix validation failed: {validation_error}"
            }
        
        # Apply fix
        if not self.repair_module.apply_fix(
            pipeline_id,
            error_report.step_id,
            patched_code
        ):
            self._log_repair_attempt(
                pipeline_id=pipeline_id,
                attempt_number=current_attempts + 1,
                original_error=error_report.error_message,
                ai_fix_reason=fix_reason,
                patched_code=patched_code,
                repair_successful=False
            )
            return {
                "success": False,
                "attempts": current_attempts + 1,
                "final_status": "failed",
                "error": "Failed to apply fix to database"
            }
        
        # Log repair attempt (will be updated after retry)
        self._log_repair_attempt(
            pipeline_id=pipeline_id,
            attempt_number=current_attempts + 1,
            original_error=error_report.error_message,
            ai_fix_reason=fix_reason,
            patched_code=patched_code,
            repair_successful=True  # Optimistic, will be verified after retry
        )
        
        logger.info(f"Repair attempt {current_attempts + 1} completed for pipeline {pipeline_id}")
        
        return {
            "success": True,
            "attempts": current_attempts + 1,
            "final_status": "repaired",
            "fix_reason": fix_reason,
            "patched_code": patched_code
        }
    
    def _get_repair_attempt_count(self, pipeline_id: int) -> int:
        """
        Get number of repair attempts for pipeline
        
        Args:
            pipeline_id: Pipeline identifier
            
        Returns:
            Number of attempts
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT COUNT(*) FROM Repair_Logs WHERE pipeline_id = ?",
            (pipeline_id,)
        )
        
        count = cursor.fetchone()[0]
        conn.close()
        
        return count
    
    def _log_repair_attempt(
        self,
        pipeline_id: int,
        attempt_number: int,
        original_error: str,
        ai_fix_reason: str,
        patched_code: str,
        repair_successful: bool
    ):
        """
        Log repair attempt to Repair_Logs table
        
        Args:
            pipeline_id: Pipeline identifier
            attempt_number: Repair attempt number (1-3)
            original_error: Error message
            ai_fix_reason: LLM explanation
            patched_code: Corrected code
            repair_successful: Whether repair worked
        """
        db_path = get_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO Repair_Logs (
                    pipeline_id, attempt_number, original_error,
                    ai_fix_reason, patched_code, repair_time, repair_successful
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                pipeline_id,
                attempt_number,
                original_error,
                ai_fix_reason,
                patched_code,
                datetime.now().isoformat(),
                repair_successful
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Logged repair attempt {attempt_number} for pipeline {pipeline_id}")
            
        except Exception as e:
            logger.error(f"Failed to log repair attempt: {e}")
    
    def _mark_pipeline_failed(self, pipeline_id: int):
        """
        Mark pipeline as permanently failed
        
        Args:
            pipeline_id: Pipeline identifier
        """
        db_path = get_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE Pipelines SET status = 'failed', updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), pipeline_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Marked pipeline {pipeline_id} as failed")
            
        except Exception as e:
            logger.error(f"Failed to mark pipeline as failed: {e}")


# Export classes
__all__ = [
    'ErrorAnalyzer',
    'RepairModule',
    'RepairLoop',
    'ErrorReport',
    'ErrorCategory',
    'ContextSnapshot'
]
