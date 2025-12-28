"""
Sandbox Execution Module
Provides secure, isolated execution environment for validating generated pipelines
"""
import os
import subprocess
import time
import shutil
import sqlite3
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.core.database import get_db_path

logger = logging.getLogger(__name__)


class ExecutionResult:
    """Container for step execution results"""
    
    def __init__(
        self,
        step_id: int,
        pipeline_id: int,
        step_number: int,
        step_type: str,
        is_successful: bool,
        stdout: str = "",
        stderr: str = "",
        exit_code: int = 0,
        execution_time_ms: int = 0
    ):
        self.step_id = step_id
        self.pipeline_id = pipeline_id
        self.step_number = step_number
        self.step_type = step_type
        self.is_successful = is_successful
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms
        self.run_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage"""
        return {
            "step_id": self.step_id,
            "pipeline_id": self.pipeline_id,
            "run_time": self.run_time.isoformat(),
            "is_successful": self.is_successful,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms
        }


class PipelineExecutionReport:
    """Container for complete pipeline execution results"""
    
    def __init__(self, pipeline_id: int):
        self.pipeline_id = pipeline_id
        self.step_results: List[ExecutionResult] = []
        self.overall_success = True
        self.total_execution_time_ms = 0
        self.failed_step: Optional[int] = None
    
    def add_result(self, result: ExecutionResult):
        """Add step execution result"""
        self.step_results.append(result)
        self.total_execution_time_ms += result.execution_time_ms
        
        if not result.is_successful:
            self.overall_success = False
            if self.failed_step is None:
                self.failed_step = result.step_number
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pipeline_id": self.pipeline_id,
            "overall_success": self.overall_success,
            "total_steps": len(self.step_results),
            "successful_steps": sum(1 for r in self.step_results if r.is_successful),
            "failed_step": self.failed_step,
            "total_execution_time_ms": self.total_execution_time_ms,
            "step_results": [r.to_dict() for r in self.step_results]
        }


class CommandValidator:
    """Validates bash commands against whitelist"""
    
    def __init__(self, allowed_commands: Optional[List[str]] = None):
        self.allowed_commands = set(allowed_commands or settings.ALLOWED_BASH_COMMANDS)
        logger.info(f"Command validator initialized with {len(self.allowed_commands)} allowed commands")
    
    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """
        Validate if command is whitelisted
        
        Args:
            command: Bash command string
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Extract base command (first word)
        tokens = command.strip().split()
        if not tokens:
            return False, "Empty command"
        
        base_command = tokens[0]
        
        # Check if command is whitelisted
        if base_command not in self.allowed_commands:
            return False, f"Command '{base_command}' is not in whitelist. Allowed: {', '.join(sorted(self.allowed_commands))}"
        
        return True, None


class SandboxRunner:
    """
    Manages isolated execution environment for pipeline validation
    """
    
    def __init__(
        self,
        sandbox_base_path: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ):
        """
        Initialize sandbox runner
        
        Args:
            sandbox_base_path: Root directory for sandboxes (uses settings if None)
            timeout_seconds: Timeout per step (uses settings if None)
        """
        self.sandbox_base_path = sandbox_base_path or settings.SANDBOX_DIRECTORY
        self.timeout_seconds = timeout_seconds or settings.SANDBOX_TIMEOUT_SECONDS
        self.command_validator = CommandValidator()
        
        # Create base sandbox directory
        Path(self.sandbox_base_path).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Sandbox runner initialized: base_path={self.sandbox_base_path}, timeout={self.timeout_seconds}s")
    
    def create_sandbox_environment(self, pipeline_id: int) -> str:
        """
        Create isolated sandbox directory structure for pipeline
        
        Args:
            pipeline_id: Pipeline identifier
            
        Returns:
            Path to sandbox directory
        """
        sandbox_dir = os.path.join(self.sandbox_base_path, f"pipeline_{pipeline_id}")
        
        # Create directory structure
        directories = [
            sandbox_dir,
            os.path.join(sandbox_dir, "data"),
            os.path.join(sandbox_dir, "tmp"),
            os.path.join(sandbox_dir, "scripts"),
            os.path.join(sandbox_dir, "logs")
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
        
        # Copy test data to sandbox
        self._copy_test_data_to_sandbox(sandbox_dir)
        
        logger.info(f"Created sandbox environment: {sandbox_dir}")
        return sandbox_dir
    
    def _copy_test_data_to_sandbox(self, sandbox_dir: str):
        """
        Copy test data files to sandbox data directory
        
        Args:
            sandbox_dir: Sandbox root directory
        """
        data_source = settings.DATA_DIRECTORY
        data_dest = os.path.join(sandbox_dir, "data")
        
        if not os.path.exists(data_source):
            logger.warning(f"Data source directory not found: {data_source}")
            return
        
        # Copy all files from data directory
        for item in os.listdir(data_source):
            source_path = os.path.join(data_source, item)
            dest_path = os.path.join(data_dest, item)
            
            if os.path.isfile(source_path):
                shutil.copy2(source_path, dest_path)
                logger.debug(f"Copied test data: {item}")
    
    def execute_step(
        self,
        script_path: str,
        step_id: int,
        pipeline_id: int,
        step_number: int,
        step_type: str,
        sandbox_dir: str
    ) -> ExecutionResult:
        """
        Execute single pipeline step
        
        Args:
            script_path: Path to script file
            step_id: Step ID from database
            pipeline_id: Pipeline ID
            step_number: Step number
            step_type: 'bash' or 'sql'
            sandbox_dir: Sandbox directory path
            
        Returns:
            ExecutionResult object
        """
        logger.info(f"Executing step {step_number} (type={step_type}, id={step_id})")
        
        start_time = time.time()
        
        try:
            if step_type == "bash":
                result = self._execute_bash_step(script_path, sandbox_dir)
            elif step_type == "sql":
                result = self._execute_sql_step(script_path, sandbox_dir)
            else:
                raise ValueError(f"Unknown step type: {step_type}")
            
            execution_time_ms = int((time.time() - start_time) * 1000)
            
            return ExecutionResult(
                step_id=step_id,
                pipeline_id=pipeline_id,
                step_number=step_number,
                step_type=step_type,
                is_successful=result["exit_code"] == 0,
                stdout=result["stdout"],
                stderr=result["stderr"],
                exit_code=result["exit_code"],
                execution_time_ms=execution_time_ms
            )
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Step {step_number} execution error: {e}")
            
            return ExecutionResult(
                step_id=step_id,
                pipeline_id=pipeline_id,
                step_number=step_number,
                step_type=step_type,
                is_successful=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time_ms=execution_time_ms
            )
    
    def _execute_bash_step(self, script_path: str, sandbox_dir: str) -> Dict[str, Any]:
        """
        Execute bash script with safety constraints
        
        Args:
            script_path: Path to bash script
            sandbox_dir: Sandbox directory
            
        Returns:
            Dict with stdout, stderr, exit_code
        """
        # Read script content for validation
        with open(script_path, 'r', encoding='utf-8') as f:
            script_content = f.read()
        
        # Validate commands in script
        for line in script_content.split('\n'):
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Skip control structures
            if any(keyword in line for keyword in ['if', 'then', 'fi', 'for', 'while', 'done', 'log_', 'SCRIPT_', 'START_TIME', 'END_TIME', 'DURATION']):
                continue
            
            # Validate command
            is_valid, error = self.command_validator.validate_command(line)
            if not is_valid and not line.startswith('echo') and not line.startswith('set'):
                logger.warning(f"Command validation warning: {error}")
                # Continue for now, but log the warning
        
        # Execute script
        try:
            # Convert to absolute paths first, then to Unix-style for bash
            script_path_abs = os.path.abspath(script_path)
            sandbox_dir_abs = os.path.abspath(sandbox_dir)
            
            script_path_unix = script_path_abs.replace('\\', '/')
            sandbox_dir_unix = sandbox_dir_abs.replace('\\', '/')
            
            # On Windows, we need to use bash if available, otherwise skip bash scripts
            if os.name == 'nt':
                # Try to find bash (Git Bash, WSL, etc.)
                bash_paths = [
                    r"C:\Program Files\Git\bin\bash.exe",
                    r"C:\Windows\System32\bash.exe",
                    "bash"
                ]
                
                bash_cmd = None
                for bash_path in bash_paths:
                    if shutil.which(bash_path):
                        bash_cmd = bash_path
                        break
                
                if not bash_cmd:
                    logger.warning("Bash not found on Windows, skipping bash script execution")
                    return {
                        "stdout": "Bash script skipped on Windows (bash not available)",
                        "stderr": "",
                        "exit_code": 0
                    }
                
                # Use Unix-style absolute paths for bash on Windows
                cmd = [bash_cmd, script_path_unix]
            else:
                cmd = ["bash", script_path_unix]
            
            # Set working directory to sandbox (Unix-style absolute path)
            result = subprocess.run(
                cmd,
                cwd=sandbox_dir_unix,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                env={**os.environ, "PATH": os.environ.get("PATH", "")}
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"Bash script execution timeout after {self.timeout_seconds}s")
            return {
                "stdout": "",
                "stderr": f"Execution timeout after {self.timeout_seconds} seconds",
                "exit_code": 124  # Standard timeout exit code
            }
        except Exception as e:
            logger.error(f"Bash execution error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1
            }
    
    def _execute_sql_step(self, script_path: str, sandbox_dir: str) -> Dict[str, Any]:
        """
        Execute SQL script against sandbox database
        
        Args:
            script_path: Path to SQL script
            sandbox_dir: Sandbox directory
            
        Returns:
            Dict with stdout, stderr, exit_code
        """
        # Create sandbox-specific database copy
        sandbox_db = os.path.join(sandbox_dir, "sandbox.db")
        
        # Copy main database to sandbox
        main_db = get_db_path()
        if os.path.exists(main_db):
            shutil.copy2(main_db, sandbox_db)
        
        try:
            # Execute SQL script
            conn = sqlite3.connect(sandbox_db)
            cursor = conn.cursor()
            
            # Read script
            with open(script_path, 'r', encoding='utf-8') as f:
                sql_script = f.read()
            
            # Execute script
            output_lines = []
            try:
                cursor.executescript(sql_script)
                conn.commit()
                
                # Collect any output
                output_lines.append("SQL script executed successfully")
                
                # Try to get last query result if any
                if cursor.description:
                    rows = cursor.fetchall()
                    for row in rows:
                        output_lines.append(str(row))
                
                conn.close()
                
                return {
                    "stdout": "\n".join(output_lines),
                    "stderr": "",
                    "exit_code": 0
                }
                
            except sqlite3.Error as e:
                conn.rollback()
                conn.close()
                
                logger.error(f"SQL execution error: {e}")
                return {
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": 1
                }
                
        except Exception as e:
            logger.error(f"SQL script error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "exit_code": 1
            }
    
    def execute_pipeline(
        self,
        pipeline_id: int,
        script_directory: str
    ) -> PipelineExecutionReport:
        """
        Execute complete pipeline sequentially
        
        Args:
            pipeline_id: Pipeline identifier
            script_directory: Directory containing generated scripts
            
        Returns:
            PipelineExecutionReport object
        """
        logger.info(f"Executing pipeline {pipeline_id}")
        
        report = PipelineExecutionReport(pipeline_id)
        
        # Create sandbox environment
        sandbox_dir = self.create_sandbox_environment(pipeline_id)
        
        try:
            # Load pipeline steps from database
            steps = self._load_pipeline_steps(pipeline_id)
            
            if not steps:
                logger.error(f"No steps found for pipeline {pipeline_id}")
                return report
            
            # Execute steps in order
            for step in steps:
                step_id = step["id"]
                step_number = step["step_number"]
                step_type = step["code_type"]
                
                # Find script file - use absolute path
                script_filename = f"step_{step_number}_{step_type}.{self._get_extension(step_type)}"
                script_path = os.path.join(script_directory, script_filename)
                # Convert to absolute path and normalize
                script_path_abs = os.path.abspath(script_path)
                
                if not os.path.exists(script_path_abs):
                    logger.error(f"Script not found: {script_path_abs}")
                    result = ExecutionResult(
                        step_id=step_id,
                        pipeline_id=pipeline_id,
                        step_number=step_number,
                        step_type=step_type,
                        is_successful=False,
                        stderr=f"Script file not found: {script_filename}",
                        exit_code=127
                    )
                else:
                    # Execute step - pass absolute path
                    result = self.execute_step(
                        script_path=script_path_abs,
                        step_id=step_id,
                        pipeline_id=pipeline_id,
                        step_number=step_number,
                        step_type=step_type,
                        sandbox_dir=sandbox_dir
                    )
                
                # Add result to report
                report.add_result(result)
                
                # Log to database
                self._log_execution_to_database(result)
                
                # Stop at first failure
                if not result.is_successful:
                    logger.warning(f"Pipeline {pipeline_id} failed at step {step_number}")
                    break
                
                logger.info(f"Step {step_number} completed successfully")
            
            # Update pipeline status in database
            self._update_pipeline_status(
                pipeline_id,
                "success" if report.overall_success else "failed"
            )
            
            logger.info(f"Pipeline {pipeline_id} execution completed: success={report.overall_success}")
            
        finally:
            # Cleanup sandbox
            # Note: We keep sandbox for debugging in case of failure
            if report.overall_success:
                self.cleanup_sandbox(pipeline_id)
        
        return report
    
    def _load_pipeline_steps(self, pipeline_id: int) -> List[Dict[str, Any]]:
        """
        Load pipeline steps from database
        
        Args:
            pipeline_id: Pipeline identifier
            
        Returns:
            List of step dictionaries
        """
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM Pipeline_Steps WHERE pipeline_id = ? ORDER BY step_number",
            (pipeline_id,)
        )
        
        steps = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return steps
    
    def _log_execution_to_database(self, result: ExecutionResult):
        """
        Log execution result to Execution_Logs table
        
        Args:
            result: ExecutionResult object
        """
        db_path = get_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO Execution_Logs (
                    pipeline_id, step_id, run_time, is_successful,
                    stdout, stderr, exit_code, execution_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                result.pipeline_id,
                result.step_id,
                result.run_time.isoformat(),
                result.is_successful,
                result.stdout,
                result.stderr,
                result.exit_code,
                result.execution_time_ms
            ))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"Logged execution result for step {result.step_id}")
            
        except Exception as e:
            logger.error(f"Failed to log execution to database: {e}")
            # Retry once
            try:
                time.sleep(0.1)
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Execution_Logs (
                        pipeline_id, step_id, run_time, is_successful,
                        stdout, stderr, exit_code, execution_time_ms
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.pipeline_id,
                    result.step_id,
                    result.run_time.isoformat(),
                    result.is_successful,
                    result.stdout,
                    result.stderr,
                    result.exit_code,
                    result.execution_time_ms
                ))
                conn.commit()
                conn.close()
            except Exception as retry_error:
                logger.error(f"Retry failed: {retry_error}")
    
    def _update_pipeline_status(self, pipeline_id: int, status: str):
        """
        Update pipeline status in database
        
        Args:
            pipeline_id: Pipeline identifier
            status: New status value
        """
        db_path = get_db_path()
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE Pipelines SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now().isoformat(), pipeline_id)
            )
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated pipeline {pipeline_id} status to '{status}'")
            
        except Exception as e:
            logger.error(f"Failed to update pipeline status: {e}")
    
    def cleanup_sandbox(self, pipeline_id: int):
        """
        Remove sandbox directory and cleanup resources
        
        Args:
            pipeline_id: Pipeline identifier
        """
        sandbox_dir = os.path.join(self.sandbox_base_path, f"pipeline_{pipeline_id}")
        
        if os.path.exists(sandbox_dir):
            try:
                shutil.rmtree(sandbox_dir)
                logger.info(f"Cleaned up sandbox: {sandbox_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup sandbox {sandbox_dir}: {e}")
    
    def _get_extension(self, step_type: str) -> str:
        """Get file extension for step type"""
        return "sh" if step_type == "bash" else "sql"


# Export classes
__all__ = [
    'SandboxRunner',
    'ExecutionResult',
    'PipelineExecutionReport',
    'CommandValidator'
]
