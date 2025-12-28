"""
Pydantic models for QueryForge API
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# Request Models

class PipelineCreateRequest(BaseModel):
    """Request model for creating a pipeline"""
    user_id: int = Field(..., description="User identifier", ge=1)
    prompt: str = Field(..., description="Natural language task description", min_length=1)
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "prompt": "Import inventory.json into products table"
            }
        }


class PipelineRunRequest(BaseModel):
    """Request model for running a pipeline"""
    run_mode: str = Field(default="sandbox", description="Execution mode: sandbox or production")
    
    class Config:
        json_schema_extra = {
            "example": {
                "run_mode": "sandbox"
            }
        }


class PipelineRepairRequest(BaseModel):
    """Request model for repairing a pipeline"""
    max_attempts: int = Field(default=3, description="Maximum repair attempts", ge=1, le=5)
    auto_retry: bool = Field(default=True, description="Automatically retry after repair")
    
    class Config:
        json_schema_extra = {
            "example": {
                "max_attempts": 3,
                "auto_retry": True
            }
        }


class PipelineCommitRequest(BaseModel):
    """Request model for committing a pipeline"""
    force_commit: bool = Field(default=False, description="Bypass high-risk warnings")
    create_backup: bool = Field(default=True, description="Create pre-commit backup")
    
    class Config:
        json_schema_extra = {
            "example": {
                "force_commit": False,
                "create_backup": True
            }
        }


# Response Models

class PipelineStep(BaseModel):
    """Model for a pipeline step"""
    step_number: int = Field(..., description="Step execution order")
    type: str = Field(..., description="Step type: bash or sql")
    content: str = Field(..., description="Executable script content")
    description: Optional[str] = Field(None, description="Step description")


class PipelineCreateResponse(BaseModel):
    """Response model for pipeline creation"""
    success: bool = Field(..., description="Operation success status")
    pipeline_id: Optional[int] = Field(None, description="Generated pipeline ID")
    status: Optional[str] = Field(None, description="Pipeline status")
    draft_pipeline: Optional[List[PipelineStep]] = Field(None, description="Generated pipeline steps")
    created_at: Optional[str] = Field(None, description="Creation timestamp")
    context_used: Optional[ContextSummary] = Field(None, description="Context summary")
    warnings: Optional[List[Dict[str, Any]]] = Field(None, description="Validation warnings")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_type: Optional[str] = Field(None, description="Error type classification")
    validation_errors: Optional[List[Any]] = Field(None, description="Validation error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "pipeline_id": 42,
                "status": "generated",
                "draft_pipeline": [
                    {
                        "step_number": 1,
                        "type": "bash",
                        "content": "awk -F',' '$3!=\"\" {print}' data/sales.csv > /tmp/cleaned.csv",
                        "description": "Filter rows with non-empty amounts"
                    }
                ],
                "created_at": "2025-11-24T10:30:00Z"
            }
        }


class SynthesisResult(BaseModel):
    """Model for synthesis result"""
    success: bool
    output_directory: Optional[str] = None
    total_scripts: Optional[int] = None
    error: Optional[str] = None


class ExecutionStepLog(BaseModel):
    """Model for step execution log"""
    type: str
    exit_code: int
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class PipelineRunResponse(BaseModel):
    """Response model for pipeline execution"""
    success: bool
    pipeline_id: int
    status: str
    synthesis_result: Optional[SynthesisResult] = None
    execution_log: Optional[Dict[str, ExecutionStepLog]] = None
    overall_status: Optional[str] = None
    error: Optional[str] = None


class RepairLog(BaseModel):
    """Model for repair log"""
    attempt_number: int
    original_error: str
    ai_fix_reason: str
    repair_successful: bool


class PipelineRepairResponse(BaseModel):
    """Response model for pipeline repair"""
    success: bool
    pipeline_id: int
    repair_attempts: List[Dict[str, Any]] = Field(default_factory=list)
    current_status: Optional[str] = None
    final_execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ContextSummary(BaseModel):
    """Summary of MCP context used"""
    tables_referenced: List[str] = Field(default_factory=list)
    files_referenced: List[str] = Field(default_factory=list)
    total_steps: int = 0


class PipelineCommitResponse(BaseModel):
    """Response model for pipeline commit"""
    success: bool
    pipeline_id: int
    commit_status: str
    snapshot_id: Optional[int] = None
    operations_performed: Optional[Dict[str, Any]] = None
    commit_time: Optional[str] = None
    rollback_available: bool = False
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "pipeline_id": 42,
                "commit_status": "committed",
                "snapshot_id": 15,
                "operations_performed": {
                    "sql_operations": 2,
                    "file_operations": 1
                },
                "commit_time": "2025-11-27T10:32:00Z",
                "rollback_available": True
            }
        }


class ExecutionLog(BaseModel):
    """Model for execution log entry"""
    step_id: int
    run_time: str
    is_successful: bool
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    exit_code: Optional[int] = None
    execution_time_ms: Optional[int] = None


class PipelineLogsResponse(BaseModel):
    """Response model for pipeline logs"""
    success: bool
    pipeline_id: int
    original_prompt: str
    execution_logs: List[ExecutionLog]
    repair_logs: List[RepairLog]
    final_pipeline: Optional[List[PipelineStep]] = None
    overall_status: str
    error: Optional[str] = None


# Export models
__all__ = [
    'PipelineCreateRequest',
    'PipelineRunRequest',
    'PipelineRepairRequest',
    'PipelineCommitRequest',
    'PipelineCreateResponse',
    'PipelineRunResponse',
    'PipelineRepairResponse',
    'PipelineCommitResponse',
    'PipelineLogsResponse',
    'PipelineStep',
    'ExecutionLog',
    'RepairLog',
    'ContextSummary'
]
