"""
Integration tests for Phase 4 (Sandbox) and Phase 5 (Repair Loop)
Tests complete workflow from execution to error detection to repair
"""
import os
import pytest
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path
from unittest.mock import Mock, patch
from datetime import datetime

from app.services.sandbox import SandboxRunner, ExecutionResult
from app.services.repair import ErrorAnalyzer, RepairModule, RepairLoop, ErrorCategory
from app.services.synthesizer import PipelineSynthesizer
from app.core.database import init_database, get_db_path


@pytest.fixture
def setup_test_environment():
    """Setup complete test environment with database and directories"""
    # Create temporary directories
    test_dir = tempfile.mkdtemp()
    data_dir = os.path.join(test_dir, 'data')
    sandbox_dir = os.path.join(test_dir, 'sandbox')
    scripts_dir = os.path.join(test_dir, 'scripts')
    
    os.makedirs(data_dir)
    os.makedirs(sandbox_dir)
    os.makedirs(scripts_dir)
    
    # Create test data file
    test_csv = os.path.join(data_dir, 'test_data.csv')
    with open(test_csv, 'w') as f:
        f.write('id,name,value\n1,Item1,100\n2,Item2,200\n')
    
    # Setup database
    original_db_url = os.environ.get('DATABASE_URL')
    test_db = os.path.join(test_dir, 'test.db')
    os.environ['DATABASE_URL'] = f'sqlite:///{test_db}'
    
    # Update settings
    from app.core import config
    config.settings = config.Settings()
    config.settings.DATA_DIRECTORY = data_dir
    config.settings.SANDBOX_DIRECTORY = sandbox_dir
    config.settings.SYNTHESIZER_OUTPUT_DIR = scripts_dir
    
    # Initialize database
    init_database()
    
    yield {
        'test_dir': test_dir,
        'data_dir': data_dir,
        'sandbox_dir': sandbox_dir,
        'scripts_dir': scripts_dir,
        'test_db': test_db
    }
    
    # Cleanup
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    if original_db_url:
        os.environ['DATABASE_URL'] = original_db_url
    else:
        os.environ.pop('DATABASE_URL', None)
    
    config.settings = config.Settings()


@pytest.fixture
def create_failing_pipeline(setup_test_environment):
    """Create a pipeline that will fail on execution"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert pipeline
    cursor.execute("""
        INSERT INTO Pipelines (user_id, prompt_text, status)
        VALUES (1, 'Process missing file', 'pending')
    """)
    pipeline_id = cursor.lastrowid
    
    # Insert failing step (references non-existent file)
    cursor.execute("""
        INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
        VALUES (?, 1, 'bash', 'cat data/nonexistent_file.csv')
    """, (pipeline_id,))
    step_id = cursor.lastrowid
    
    # Insert schema snapshot
    schema_data = {
        "tables": [
            {
                "name": "products",
                "columns": [
                    {"name": "id", "type": "INTEGER"},
                    {"name": "name", "type": "TEXT"}
                ]
            }
        ]
    }
    file_data = ["data/test_data.csv"]
    
    cursor.execute("""
        INSERT INTO Schema_Snapshots (pipeline_id, db_structure, file_list)
        VALUES (?, ?, ?)
    """, (pipeline_id, json.dumps(schema_data), json.dumps(file_data)))
    
    conn.commit()
    conn.close()
    
    return {
        'pipeline_id': pipeline_id,
        'step_id': step_id
    }


class TestSandboxToRepairWorkflow:
    """Test complete workflow from sandbox execution to repair"""
    
    def test_failed_execution_creates_log(self, setup_test_environment, create_failing_pipeline):
        """Test that failed execution creates proper log entry"""
        env = setup_test_environment
        pipeline_data = create_failing_pipeline
        
        # Synthesize scripts
        synthesizer = PipelineSynthesizer(output_directory=env['scripts_dir'])
        
        pipeline_steps = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "cat data/nonexistent_file.csv",
                "description": "Read non-existent file"
            }
        ]
        
        synth_result = synthesizer.synthesize_pipeline(
            pipeline_id=pipeline_data['pipeline_id'],
            pipeline=pipeline_steps
        )
        
        assert synth_result['success'] is True
        
        # Execute in sandbox
        runner = SandboxRunner(
            sandbox_base_path=env['sandbox_dir'],
            timeout_seconds=5
        )
        
        report = runner.execute_pipeline(
            pipeline_id=pipeline_data['pipeline_id'],
            script_directory=synth_result['output_directory']
        )
        
        # Verify execution failed
        assert report.overall_success is False
        assert report.failed_step == 1
        
        # Verify execution log was created
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM Execution_Logs 
            WHERE pipeline_id = ? AND is_successful = 0
        """, (pipeline_data['pipeline_id'],))
        
        failed_log = cursor.fetchone()
        conn.close()
        
        assert failed_log is not None
        assert failed_log[6] != ''  # stderr should have error message
    
    def test_error_analyzer_detects_file_not_found(self, setup_test_environment, create_failing_pipeline):
        """Test error analyzer correctly identifies file not found errors"""
        env = setup_test_environment
        pipeline_data = create_failing_pipeline
        
        # Create execution log manually
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Execution_Logs (
                pipeline_id, step_id, run_time, is_successful,
                stdout, stderr, exit_code, execution_time_ms
            ) VALUES (?, ?, ?, 0, '', 'cat: data/nonexistent_file.csv: No such file or directory', 1, 100)
        """, (
            pipeline_data['pipeline_id'],
            pipeline_data['step_id'],
            datetime.now().isoformat()
        ))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Analyze error
        analyzer = ErrorAnalyzer()
        error_report = analyzer.analyze_execution_failure(log_id)
        
        assert error_report is not None
        assert error_report.category == ErrorCategory.FILE_NOT_FOUND
        assert error_report.pipeline_id == pipeline_data['pipeline_id']
        assert 'No such file' in error_report.error_message
    
    def test_context_extraction_for_repair(self, setup_test_environment, create_failing_pipeline):
        """Test that repair context includes all necessary information"""
        pipeline_data = create_failing_pipeline
        
        # Create execution log
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Execution_Logs (
                pipeline_id, step_id, run_time, is_successful,
                stdout, stderr, exit_code, execution_time_ms
            ) VALUES (?, ?, ?, 0, '', 'File not found', 1, 100)
        """, (
            pipeline_data['pipeline_id'],
            pipeline_data['step_id'],
            datetime.now().isoformat()
        ))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Extract context
        analyzer = ErrorAnalyzer()
        error_report = analyzer.analyze_execution_failure(log_id)
        context = analyzer.extract_relevant_context(
            error_report.pipeline_id,
            error_report.step_id
        )
        
        assert context is not None
        assert context.pipeline_prompt == 'Process missing file'
        assert isinstance(context.database_schema, dict)
        assert 'tables' in context.database_schema
        assert isinstance(context.file_list, list)
        assert len(context.file_list) > 0
        assert 'test_data.csv' in str(context.file_list)
    
    @patch('app.services.repair.GeminiClient')
    def test_repair_module_generates_fix(
        self,
        mock_client_class,
        setup_test_environment,
        create_failing_pipeline
    ):
        """Test repair module generates appropriate fix"""
        # Mock Gemini response
        mock_client = Mock()
        mock_client.generate_content.return_value = {
            'success': True,
            'response': json.dumps({
                "fix_reason": "Corrected file path to existing file",
                "patched_code": "cat data/test_data.csv"
            })
        }
        mock_client_class.return_value = mock_client
        
        pipeline_data = create_failing_pipeline
        
        # Create error report
        from app.services.repair import ErrorReport, ContextSnapshot
        
        error_report = ErrorReport(
            execution_log_id=1,
            pipeline_id=pipeline_data['pipeline_id'],
            step_id=pipeline_data['step_id'],
            step_number=1,
            step_type='bash',
            original_content='cat data/nonexistent_file.csv',
            error_message='No such file or directory',
            exit_code=1,
            category=ErrorCategory.FILE_NOT_FOUND
        )
        
        context = ContextSnapshot(
            database_schema={'tables': []},
            file_list=['data/test_data.csv'],
            previous_steps=[],
            pipeline_prompt='Process missing file'
        )
        
        # Generate fix
        repair_module = RepairModule()
        fix_result = repair_module.generate_fix(error_report, context)
        
        assert fix_result['success'] is True
        assert 'patched_code' in fix_result
        assert 'test_data.csv' in fix_result['patched_code']
        assert 'fix_reason' in fix_result
    
    @patch('app.services.repair.GeminiClient')
    def test_repair_loop_with_valid_fix(
        self,
        mock_client_class,
        setup_test_environment,
        create_failing_pipeline
    ):
        """Test complete repair loop with valid fix"""
        # Mock Gemini response
        mock_client = Mock()
        mock_client.generate_content.return_value = {
            'success': True,
            'response': json.dumps({
                "fix_reason": "Fixed file path",
                "patched_code": "cat data/test_data.csv"
            })
        }
        mock_client_class.return_value = mock_client
        
        pipeline_data = create_failing_pipeline
        
        # Create execution log
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Execution_Logs (
                pipeline_id, step_id, run_time, is_successful,
                stdout, stderr, exit_code, execution_time_ms
            ) VALUES (?, ?, ?, 0, '', 'No such file or directory', 1, 100)
        """, (
            pipeline_data['pipeline_id'],
            pipeline_data['step_id'],
            datetime.now().isoformat()
        ))
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Execute repair loop
        repair_loop = RepairLoop()
        result = repair_loop.repair_and_retry(
            pipeline_id=pipeline_data['pipeline_id'],
            execution_log_id=log_id
        )
        
        assert result['success'] is True
        assert result['attempts'] == 1
        assert 'patched_code' in result
        
        # Verify repair log was created
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM Repair_Logs WHERE pipeline_id = ?
        """, (pipeline_data['pipeline_id'],))
        
        repair_log = cursor.fetchone()
        conn.close()
        
        assert repair_log is not None
        assert repair_log[2] == 1  # attempt_number
        assert 'Fixed file path' in repair_log[4]  # ai_fix_reason
    
    def test_max_repair_attempts_enforcement(self, setup_test_environment, create_failing_pipeline):
        """Test that repair loop respects maximum attempts limit"""
        pipeline_data = create_failing_pipeline
        
        # Add 3 failed repair attempts
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for attempt in range(1, 4):
            cursor.execute("""
                INSERT INTO Repair_Logs (
                    pipeline_id, attempt_number, original_error,
                    ai_fix_reason, patched_code, repair_successful
                ) VALUES (?, ?, 'Error', 'Attempted fix', 'code', 0)
            """, (pipeline_data['pipeline_id'], attempt))
        
        # Create execution log
        cursor.execute("""
            INSERT INTO Execution_Logs (
                pipeline_id, step_id, run_time, is_successful,
                stdout, stderr, exit_code, execution_time_ms
            ) VALUES (?, ?, ?, 0, '', 'Still failing', 1, 100)
        """, (
            pipeline_data['pipeline_id'],
            pipeline_data['step_id'],
            datetime.now().isoformat()
        ))
        log_id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        
        # Try repair again
        repair_loop = RepairLoop()
        result = repair_loop.repair_and_retry(
            pipeline_id=pipeline_data['pipeline_id'],
            execution_log_id=log_id
        )
        
        assert result['success'] is False
        assert 'Maximum repair attempts' in result['error']
        
        # Verify pipeline is marked as failed
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT status FROM Pipelines WHERE id = ?",
            (pipeline_data['pipeline_id'],)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'failed'
    
    @patch('app.services.repair.GeminiClient')
    def test_duplicate_fix_detection(
        self,
        mock_client_class,
        setup_test_environment,
        create_failing_pipeline
    ):
        """Test that duplicate fixes are detected and rejected"""
        # Mock Gemini to return same fix twice
        mock_client = Mock()
        mock_client.generate_content.return_value = {
            'success': True,
            'response': json.dumps({
                "fix_reason": "Same fix",
                "patched_code": "cat data/test_data.csv"
            })
        }
        mock_client_class.return_value = mock_client
        
        pipeline_data = create_failing_pipeline
        
        from app.services.repair import ErrorReport, ContextSnapshot
        
        error_report = ErrorReport(
            execution_log_id=1,
            pipeline_id=pipeline_data['pipeline_id'],
            step_id=pipeline_data['step_id'],
            step_number=1,
            step_type='bash',
            original_content='cat data/nonexistent.csv',
            error_message='No such file',
            exit_code=1,
            category=ErrorCategory.FILE_NOT_FOUND
        )
        
        context = ContextSnapshot(
            database_schema={'tables': []},
            file_list=['data/test_data.csv'],
            previous_steps=[],
            pipeline_prompt='Test'
        )
        
        repair_module = RepairModule()
        
        # First fix should succeed
        fix1 = repair_module.generate_fix(error_report, context)
        assert fix1['success'] is True
        
        # Second identical fix should be rejected
        fix2 = repair_module.generate_fix(error_report, context)
        assert fix2['success'] is False
        assert 'identical fix' in fix2['error'].lower()


class TestEndToEndWorkflow:
    """Test complete end-to-end workflows"""
    
    @patch('app.services.repair.GeminiClient')
    def test_complete_failure_detection_and_repair_workflow(
        self,
        mock_client_class,
        setup_test_environment,
        create_failing_pipeline
    ):
        """Test complete workflow: execute -> fail -> analyze -> repair"""
        # Mock Gemini
        mock_client = Mock()
        mock_client.generate_content.return_value = {
            'success': True,
            'response': json.dumps({
                "fix_reason": "Corrected to existing file",
                "patched_code": "cat data/test_data.csv"
            })
        }
        mock_client_class.return_value = mock_client
        
        env = setup_test_environment
        pipeline_data = create_failing_pipeline
        
        # Step 1: Synthesize pipeline
        synthesizer = PipelineSynthesizer(output_directory=env['scripts_dir'])
        pipeline_steps = [{
            "step_number": 1,
            "type": "bash",
            "content": "cat data/nonexistent_file.csv"
        }]
        
        synth_result = synthesizer.synthesize_pipeline(
            pipeline_id=pipeline_data['pipeline_id'],
            pipeline=pipeline_steps
        )
        assert synth_result['success'] is True
        
        # Step 2: Execute and fail
        runner = SandboxRunner(sandbox_base_path=env['sandbox_dir'])
        report = runner.execute_pipeline(
            pipeline_id=pipeline_data['pipeline_id'],
            script_directory=synth_result['output_directory']
        )
        
        assert report.overall_success is False
        
        # Step 3: Get execution log ID
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id FROM Execution_Logs 
            WHERE pipeline_id = ? AND is_successful = 0
            ORDER BY run_time DESC LIMIT 1
        """, (pipeline_data['pipeline_id'],))
        
        log_id = cursor.fetchone()[0]
        conn.close()
        
        # Step 4: Repair
        repair_loop = RepairLoop()
        repair_result = repair_loop.repair_and_retry(
            pipeline_id=pipeline_data['pipeline_id'],
            execution_log_id=log_id
        )
        
        assert repair_result['success'] is True
        assert repair_result['attempts'] == 1
        
        # Step 5: Verify repair was logged
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM Repair_Logs WHERE pipeline_id = ?
        """, (pipeline_data['pipeline_id'],))
        
        repair_count = cursor.fetchone()[0]
        conn.close()
        
        assert repair_count == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
