"""
Bash/SQL Pipeline Synthesizer
Converts structured JSON pipelines to executable script files
"""
import os
import json
import stat
import subprocess
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class BashScriptSynthesizer:
    """
    Generates executable Bash scripts from pipeline steps
    """
    
    @staticmethod
    def synthesize(
        step_number: int,
        content: str,
        description: Optional[str] = None
    ) -> str:
        """
        Generate Bash script from step content
        
        Args:
            step_number: Step number in pipeline
            content: Bash command content
            description: Optional step description
            
        Returns:
            Complete Bash script content
        """
        # Build script from template
        script = f"""#!/bin/bash
set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Catch errors in pipes

# Script metadata
SCRIPT_NAME="step_{step_number}.sh"
STEP_NUMBER={step_number}
START_TIME=$(date +%s)

# Logging functions
log_info() {{
    echo "[INFO] [Step $STEP_NUMBER] $1"
}}

log_error() {{
    echo "[ERROR] [Step $STEP_NUMBER] $1" >&2
}}

# Execute main content
log_info "Starting execution"
"""
        
        # Add description as comment if provided
        if description:
            script += f"""
# Description: {description}
"""
        
        # Add main content
        script += f"""
{content}

# Calculate execution time
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log_info "Completed in ${{DURATION}}s"

exit 0
"""
        
        return script
    
    @staticmethod
    def validate_syntax(script_path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate Bash script syntax
        
        Args:
            script_path: Path to script file
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not settings.ENABLE_SYNTAX_VALIDATION:
            return True, None
        
        try:
            # On Windows, we can't use bash -n, so skip validation
            if os.name == 'nt':
                logger.info("Bash syntax validation skipped on Windows")
                return True, None
            
            # Run bash -n to check syntax
            result = subprocess.run(
                ['bash', '-n', script_path],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                return True, None
            else:
                return False, result.stderr
                
        except FileNotFoundError:
            logger.warning("bash command not found, skipping syntax validation")
            return True, None
        except Exception as e:
            logger.warning(f"Bash syntax validation error: {e}")
            return True, None  # Don't fail synthesis on validation errors


class SQLScriptSynthesizer:
    """
    Generates executable SQL scripts from pipeline steps
    """
    
    @staticmethod
    def synthesize(
        step_number: int,
        content: str,
        description: Optional[str] = None
    ) -> str:
        """
        Generate SQL script from step content
        
        Args:
            step_number: Step number in pipeline
            content: SQL statement content
            description: Optional step description
            
        Returns:
            Complete SQL script content
        """
        # Build script from template
        timestamp = datetime.now().isoformat()
        
        script = f"""-- QueryForge Pipeline Step {step_number}
-- Generated: {timestamp}
"""
        
        # Add description as comment if provided
        if description:
            script += f"""-- Description: {description}
"""
        
        script += f"""
-- Enable error reporting
.mode list
.headers on

-- Begin transaction
BEGIN TRANSACTION;

-- Main SQL content
{content}

-- Commit transaction
COMMIT;

-- Log completion
SELECT 'Step {step_number} completed successfully' as status;
"""
        
        return script
    
    @staticmethod
    def validate_syntax(script_content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate SQL script syntax (basic check)
        
        Args:
            script_content: SQL script content
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not settings.ENABLE_SYNTAX_VALIDATION:
            return True, None
        
        try:
            # Basic syntax validation - check for balanced BEGIN/COMMIT
            content_upper = script_content.upper()
            
            # Check for BEGIN without COMMIT
            begin_count = content_upper.count('BEGIN TRANSACTION')
            commit_count = content_upper.count('COMMIT')
            
            if begin_count != commit_count:
                return False, "Unbalanced BEGIN TRANSACTION / COMMIT"
            
            # Check for common SQL keywords present
            has_sql = any(keyword in content_upper for keyword in [
                'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'COPY'
            ])
            
            if not has_sql:
                return False, "No valid SQL statements found"
            
            return True, None
            
        except Exception as e:
            logger.warning(f"SQL syntax validation error: {e}")
            return True, None  # Don't fail synthesis on validation errors


class PipelineSynthesizer:
    """
    Orchestrates conversion of complete pipeline to script files
    """
    
    def __init__(self, output_directory: Optional[str] = None):
        """
        Initialize pipeline synthesizer
        
        Args:
            output_directory: Base directory for script output (uses settings if None)
        """
        self.output_directory = output_directory or settings.SYNTHESIZER_OUTPUT_DIR
        
        # Create base output directory if it doesn't exist
        Path(self.output_directory).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Pipeline synthesizer initialized with output dir: {self.output_directory}")
    
    def synthesize_pipeline(
        self,
        pipeline_id: int,
        pipeline: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Synthesize complete pipeline to script files
        
        Args:
            pipeline_id: Pipeline identifier
            pipeline: List of pipeline steps
            
        Returns:
            Synthesis result
            
        Response structure:
            {
                "success": bool,
                "pipeline_id": int,
                "output_directory": str,
                "scripts": list of script info dicts,
                "manifest_path": str,
                "error": str (if failure)
            }
        """
        try:
            # Create pipeline-specific directory
            pipeline_dir = os.path.join(
                self.output_directory,
                f"pipeline_{pipeline_id}"
            )
            Path(pipeline_dir).mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Synthesizing pipeline {pipeline_id} to {pipeline_dir}")
            
            scripts = []
            
            # Generate script for each step
            for step in pipeline:
                step_number = step.get("step_number", 0)
                step_type = step.get("type", "")
                content = step.get("content", "")
                description = step.get("description")
                
                try:
                    script_info = self._synthesize_step(
                        pipeline_dir,
                        step_number,
                        step_type,
                        content,
                        description
                    )
                    scripts.append(script_info)
                    
                except Exception as e:
                    logger.error(f"Error synthesizing step {step_number}: {e}")
                    return {
                        "success": False,
                        "error": f"Failed to synthesize step {step_number}: {str(e)}",
                        "failed_step": step_number
                    }
            
            # Generate manifest file
            manifest_path = self._generate_manifest(
                pipeline_dir,
                pipeline_id,
                scripts
            )
            
            # Validate all scripts
            validation_result = self._validate_scripts(scripts)
            
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": "Script validation failed",
                    "validation_issues": validation_result["issues"]
                }
            
            logger.info(f"Successfully synthesized {len(scripts)} scripts")
            
            return {
                "success": True,
                "pipeline_id": pipeline_id,
                "output_directory": pipeline_dir,
                "scripts": scripts,
                "manifest_path": manifest_path,
                "total_scripts": len(scripts)
            }
            
        except Exception as e:
            logger.error(f"Pipeline synthesis error: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Synthesis failed: {str(e)}",
                "error_type": "synthesis_error"
            }
    
    def _synthesize_step(
        self,
        pipeline_dir: str,
        step_number: int,
        step_type: str,
        content: str,
        description: Optional[str]
    ) -> Dict[str, Any]:
        """
        Synthesize individual pipeline step
        
        Args:
            pipeline_dir: Pipeline output directory
            step_number: Step number
            step_type: 'bash' or 'sql'
            content: Step content
            description: Optional description
            
        Returns:
            Script information dictionary
        """
        if step_type == "bash":
            # Generate Bash script
            script_content = BashScriptSynthesizer.synthesize(
                step_number,
                content,
                description
            )
            extension = "sh"
            
        elif step_type == "sql":
            # Generate SQL script
            script_content = SQLScriptSynthesizer.synthesize(
                step_number,
                content,
                description
            )
            extension = "sql"
            
        else:
            raise ValueError(f"Unknown step type: {step_type}")
        
        # Create script file
        filename = f"step_{step_number}_{step_type}.{extension}"
        file_path = os.path.join(pipeline_dir, filename)
        
        # Write script to file
        with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
            f.write(script_content)
        
        # Set file permissions (executable for .sh files)
        if extension == "sh":
            self._set_executable_permissions(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        logger.info(f"Created {filename} ({file_size} bytes)")
        
        return {
            "step_number": step_number,
            "type": step_type,
            "filename": filename,
            "path": file_path,
            "size_bytes": file_size,
            "executable": extension == "sh"
        }
    
    def _set_executable_permissions(self, file_path: str) -> None:
        """
        Set executable permissions on script file
        
        Args:
            file_path: Path to script file
        """
        try:
            # On Windows, this has limited effect
            if os.name == 'nt':
                # Windows doesn't have Unix permissions, but we can try
                logger.info(f"Setting permissions on Windows: {file_path}")
            else:
                # Unix-like systems
                permissions = int(settings.SCRIPT_FILE_PERMISSIONS, 8)
                os.chmod(file_path, permissions)
                logger.info(f"Set permissions {settings.SCRIPT_FILE_PERMISSIONS} on {file_path}")
                
        except Exception as e:
            logger.warning(f"Could not set permissions on {file_path}: {e}")
    
    def _generate_manifest(
        self,
        pipeline_dir: str,
        pipeline_id: int,
        scripts: List[Dict[str, Any]]
    ) -> str:
        """
        Generate manifest file for pipeline
        
        Args:
            pipeline_dir: Pipeline output directory
            pipeline_id: Pipeline identifier
            scripts: List of script information
            
        Returns:
            Path to manifest file
        """
        manifest = {
            "pipeline_id": pipeline_id,
            "generated_at": datetime.now().isoformat(),
            "scripts": [
                {
                    "step_number": s["step_number"],
                    "type": s["type"],
                    "filename": s["filename"],
                    "size_bytes": s["size_bytes"]
                }
                for s in scripts
            ],
            "total_scripts": len(scripts)
        }
        
        manifest_path = os.path.join(pipeline_dir, "manifest.json")
        
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        
        logger.info(f"Generated manifest: {manifest_path}")
        
        return manifest_path
    
    def _validate_scripts(self, scripts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate generated scripts
        
        Args:
            scripts: List of script information
            
        Returns:
            Validation result
        """
        issues = []
        
        for script in scripts:
            file_path = script["path"]
            step_number = script["step_number"]
            script_type = script["type"]
            
            # Check file exists
            if not os.path.exists(file_path):
                issues.append({
                    "script": script["filename"],
                    "issue_type": "file_not_found",
                    "message": f"Script file not found: {file_path}"
                })
                continue
            
            # Check file is not empty
            if script["size_bytes"] == 0:
                issues.append({
                    "script": script["filename"],
                    "issue_type": "empty_file",
                    "message": "Script file is empty"
                })
                continue
            
            # Validate syntax based on type
            if script_type == "bash":
                is_valid, error = BashScriptSynthesizer.validate_syntax(file_path)
                if not is_valid:
                    issues.append({
                        "script": script["filename"],
                        "issue_type": "syntax_error",
                        "message": f"Bash syntax error: {error}"
                    })
            
            elif script_type == "sql":
                # Read file content for SQL validation
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                is_valid, error = SQLScriptSynthesizer.validate_syntax(content)
                if not is_valid:
                    issues.append({
                        "script": script["filename"],
                        "issue_type": "syntax_error",
                        "message": f"SQL syntax error: {error}"
                    })
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "total_scripts": len(scripts),
            "valid_scripts": len(scripts) - len(issues)
        }


# Export classes
__all__ = [
    'BashScriptSynthesizer',
    'SQLScriptSynthesizer',
    'PipelineSynthesizer'
]
