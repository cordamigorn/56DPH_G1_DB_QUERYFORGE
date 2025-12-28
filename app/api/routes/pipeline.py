"""
Pipeline API routes
"""
from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
import sqlite3
import json
import logging
from datetime import datetime

from app.models.schemas import (
    PipelineCreateRequest, PipelineCreateResponse,
    PipelineRunRequest, PipelineRunResponse,
    PipelineRepairRequest, PipelineRepairResponse,
    PipelineCommitRequest, PipelineCommitResponse,
    PipelineLogsResponse, PipelineStep, ExecutionLog, RepairLog, ContextSummary
)
from app.services.mcp import MCPContextManager
from app.services.llm import LLMPipelineService
from app.services.synthesizer import PipelineSynthesizer
from app.services.sandbox import SandboxRunner
from app.services.repair import RepairLoop
from app.services.commit import CommitService
from app.core.database import get_db_path

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/commit/{pipeline_id}", response_model=PipelineCommitResponse)
async def commit_pipeline(pipeline_id: int, request: PipelineCommitRequest = PipelineCommitRequest()):
    """
    Commit validated pipeline to production
    
    Args:
        pipeline_id: Pipeline ID to commit
        request: Commit configuration
        
    Returns:
        Commit result
    """
    try:
        # Use commit service
        commit_service = CommitService()
        
        # Validate first
        validation = commit_service.validate_for_commit(pipeline_id)
        
        if not validation.is_valid:
            return PipelineCommitResponse(
                success=False,
                pipeline_id=pipeline_id,
                commit_status="commit_failed",
                error=f"Validation failed: {', '.join(validation.errors)}"
            )
        
        # Commit pipeline
        result = commit_service.commit_pipeline(pipeline_id, request.force_commit)
        
        return PipelineCommitResponse(
            success=result.success,
            pipeline_id=result.pipeline_id,
            commit_status=result.commit_status,
            snapshot_id=result.snapshot_id,
            operations_performed=result.operations_performed,
            commit_time=result.commit_time,
            rollback_available=result.rollback_available,
            error=result.error
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline commit failed: {str(e)}"
        )


@router.get("/")
async def list_pipelines():
    """
    List all pipelines
    """
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Try to select with commit_status, fallback if column doesn't exist
        try:
            cursor.execute("""
                SELECT id, user_id, prompt_text, status, created_at, commit_status 
                FROM Pipelines 
                ORDER BY created_at DESC 
                LIMIT 50
            """)
        except sqlite3.OperationalError as e:
            # Column might not exist in old database, use basic columns
            logger.warning(f"Database schema outdated: {e}. Using basic columns.")
            cursor.execute("""
                SELECT id, user_id, prompt_text, status, created_at 
                FROM Pipelines 
                ORDER BY created_at DESC 
                LIMIT 50
            """)
        
        pipelines = cursor.fetchall()
        conn.close()
        
        # Convert to dict and add missing columns if needed
        pipeline_list = []
        for p in pipelines:
            p_dict = dict(p)
            # Add commit_status if missing
            if 'commit_status' not in p_dict:
                p_dict['commit_status'] = 'not_committed'
            pipeline_list.append(p_dict)
        
        return {
            "success": True,
            "pipelines": pipeline_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pipelines: {str(e)}"
        )


@router.post("/create", response_model=PipelineCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(request: PipelineCreateRequest):
    """
    Create a new pipeline from natural-language request
    
    Args:
        request: Pipeline creation request with user_id and prompt
        
    Returns:
        PipelineCreateResponse with generated pipeline
    """
    try:
        # Get MCP context
        mcp = MCPContextManager()
        context = mcp.get_full_context()
        
        # Generate pipeline using LLM
        llm = LLMPipelineService()
        result = await llm.generate_pipeline(
            user_prompt=request.prompt,
            user_id=request.user_id,
            mcp_context=context
        )
        
        if not result['success']:
            return PipelineCreateResponse(
                success=False,
                error=result.get('error', 'Pipeline generation failed'),
                error_type=result.get('error_type')
            )
        
        # Prepare draft steps
        draft_steps = [
            PipelineStep(
                step_number=step['step_number'],
                type=step['type'],
                content=step['content'],
                description=step.get('description')
            )
            for step in result['pipeline']
        ]
        
        # Prepare context summary
        context_summary = ContextSummary(
            tables_referenced=[],
            files_referenced=[],
            total_steps=len(draft_steps)
        )
        
        return PipelineCreateResponse(
            success=True,
            pipeline_id=result['pipeline_id'],
            status="pending",
            draft_pipeline=draft_steps,
            created_at=datetime.now().isoformat(),
            context_used=context_summary,
            warnings=result.get('warnings', [])
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline creation failed: {str(e)}"
        )


@router.post("/run/{pipeline_id}", response_model=PipelineRunResponse)
async def run_pipeline(pipeline_id: int, request: PipelineRunRequest = PipelineRunRequest()):
    """
    Execute pipeline in sandbox environment
    
    Args:
        pipeline_id: Pipeline ID to execute
        request: Run configuration
        
    Returns:
        Execution results
    """
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if pipeline exists
        cursor.execute("SELECT * FROM Pipelines WHERE id = ?", (pipeline_id,))
        pipeline = cursor.fetchone()
        if not pipeline:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline with id {pipeline_id} not found"
            )
        
        # Get pipeline steps
        cursor.execute("""
            SELECT * FROM Pipeline_Steps 
            WHERE pipeline_id = ? 
            ORDER BY step_number
        """, (pipeline_id,))
        steps = cursor.fetchall()
        conn.close()
        
        # Transform database rows to synthesizer format
        pipeline_steps = []
        for step in steps:
            step_dict = {
                'step_number': step['step_number'],
                'type': step['code_type'],  # Maps to 'type'
                'content': step['script_content']  # Maps to 'content'
            }
            # Add description if it exists in the row
            try:
                if 'description' in step.keys():
                    step_dict['description'] = step['description'] or ''
            except:
                pass
            pipeline_steps.append(step_dict)
        
        # Synthesize scripts
        synthesizer = PipelineSynthesizer()
        result = synthesizer.synthesize_pipeline(
            pipeline_id=pipeline_id,
            pipeline=pipeline_steps
        )
        
        # Check if synthesis was successful
        if not result['success']:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Pipeline synthesis failed: {result.get('error', 'Unknown error')}"
            )
        
        output_dir = result['output_directory']
        
        # Execute in sandbox
        runner = SandboxRunner()
        execution_result = runner.execute_pipeline(pipeline_id, output_dir)
        
        # Update pipeline status
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Map internal status to database-allowed values
        if execution_result.overall_success:
            new_status = "success"  # Changed from "sandbox_success"
        else:
            new_status = "failed"  # Changed from "sandbox_failed"
        
        cursor.execute("""
            UPDATE Pipelines 
            SET status = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (new_status, pipeline_id))
        conn.commit()
        conn.close()
        
        return PipelineRunResponse(
            success=execution_result.overall_success,
            pipeline_id=pipeline_id,
            status=new_status,
            execution_log={
                f"step_{r.step_number}": {
                    "type": r.step_type,
                    "exit_code": r.exit_code,
                    "stdout": r.stdout,
                    "stderr": r.stderr
                }
                for r in execution_result.step_results
            },
            overall_status=new_status,
            error=None if execution_result.overall_success else (
                execution_result.step_results[execution_result.failed_step - 1].stderr 
                if execution_result.failed_step and len(execution_result.step_results) >= execution_result.failed_step
                else "Pipeline execution failed"
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Pipeline execution error: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}"
        )


@router.post("/repair/{pipeline_id}", response_model=PipelineRepairResponse)
async def repair_pipeline(pipeline_id: int, request: PipelineRepairRequest = PipelineRepairRequest()):
    """
    Trigger automatic repair and retry
    
    Args:
        pipeline_id: Pipeline ID to repair
        request: Repair configuration
        
    Returns:
        Repair status
    """
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check if pipeline exists
        cursor.execute("SELECT * FROM Pipelines WHERE id = ?", (pipeline_id,))
        pipeline = cursor.fetchone()
        if not pipeline:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline with id {pipeline_id} not found"
            )
        
        # Check for failed execution
        cursor.execute("""
            SELECT * FROM Execution_Logs 
            WHERE pipeline_id = ? AND is_successful = 0 
            ORDER BY run_time DESC LIMIT 1
        """, (pipeline_id,))
        failed_execution = cursor.fetchone()
        
        if not failed_execution:
            conn.close()
            return PipelineRepairResponse(
                success=False,
                pipeline_id=pipeline_id,
                error="No failed execution found to repair"
            )
        
        conn.close()
        
        # Trigger repair loop
        repair_loop = RepairLoop(max_attempts=request.max_attempts)
        result = repair_loop.repair_and_retry(pipeline_id, failed_execution['id'])
        
        # Get repair attempts from database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM Repair_Logs 
            WHERE pipeline_id = ? 
            ORDER BY attempt_number
        """, (pipeline_id,))
        repair_logs = cursor.fetchall()
        conn.close()
        
        repair_attempts = [
            {
                "attempt_number": log['attempt_number'],
                "original_error": log['original_error'],
                "ai_fix_reason": log['ai_fix_reason'],
                "repair_successful": bool(log['repair_successful']),
                "repair_time": log['repair_time']
            }
            for log in repair_logs
        ]
        
        return PipelineRepairResponse(
            success=result.get('success', False),
            pipeline_id=pipeline_id,
            repair_attempts=repair_attempts,
            current_status=result.get('final_status', 'unknown'),
            final_execution_result=result.get('execution_result')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline repair failed: {str(e)}"
        )


@router.get("/{pipeline_id}/logs", response_model=PipelineLogsResponse)
async def get_pipeline_logs(pipeline_id: int, include_snapshots: bool = False):
    """
    Retrieve complete execution and repair logs
    
    Args:
        pipeline_id: Pipeline ID
        include_snapshots: Include schema snapshots in response
        
    Returns:
        Complete logs
    """
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get pipeline info
        cursor.execute("SELECT * FROM Pipelines WHERE id = ?", (pipeline_id,))
        pipeline = cursor.fetchone()
        
        if not pipeline:
            conn.close()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline with id {pipeline_id} not found"
            )
        
        # Get execution logs
        cursor.execute("""
            SELECT * FROM Execution_Logs 
            WHERE pipeline_id = ? 
            ORDER BY run_time
        """, (pipeline_id,))
        exec_logs = cursor.fetchall()
        
        execution_logs = [
            ExecutionLog(
                step_id=log['step_id'],
                run_time=log['run_time'],
                is_successful=bool(log['is_successful']),
                stdout=log['stdout'],
                stderr=log['stderr'],
                exit_code=log['exit_code'],
                execution_time_ms=log['execution_time_ms']
            )
            for log in exec_logs
        ]
        
        # Get repair logs
        cursor.execute("""
            SELECT * FROM Repair_Logs 
            WHERE pipeline_id = ? 
            ORDER BY attempt_number
        """, (pipeline_id,))
        rep_logs = cursor.fetchall()
        
        repair_logs = [
            RepairLog(
                attempt_number=log['attempt_number'],
                original_error=log['original_error'],
                ai_fix_reason=log['ai_fix_reason'],
                repair_successful=bool(log['repair_successful'])
            )
            for log in rep_logs
        ]
        
        # Get final pipeline steps
        cursor.execute("""
            SELECT * FROM Pipeline_Steps 
            WHERE pipeline_id = ? 
            ORDER BY step_number
        """, (pipeline_id,))
        steps = cursor.fetchall()
        
        final_pipeline = [
            PipelineStep(
                step_number=step['step_number'],
                type=step['code_type'],
                content=step['script_content']
            )
            for step in steps
        ]
        
        conn.close()
        
        return PipelineLogsResponse(
            success=True,
            pipeline_id=pipeline_id,
            original_prompt=pipeline['prompt_text'],
            execution_logs=execution_logs,
            repair_logs=repair_logs,
            final_pipeline=final_pipeline,
            overall_status=pipeline['status']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve logs: {str(e)}"
        )
