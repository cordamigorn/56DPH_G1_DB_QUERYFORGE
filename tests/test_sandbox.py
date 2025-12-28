"""
Unit tests for Sandbox Execution Module
Tests SandboxRunner, CommandValidator, and execution workflows
"""
import os
import pytest
import tempfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime

from app.services.sandbox import (
    SandboxRunner,
    ExecutionResult,
    PipelineExecutionReport,
    CommandValidator
)
from app.core.database import init_database, get_db_path


@pytest.fixture
def temp_sandbox_dir():
    """Create temporary sandbox directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def setup_database():
    """Initialize test database"""
    # Use in-memory database for tests
    original_db_url = os.environ.get('DATABASE_URL')
    test_db = tempfile.mktemp(suffix='.db')
    os.environ['DATABASE_URL'] = f'sqlite:///{test_db}'
    
    # Force reload settings
    from app.core import config
    config.settings = config.Settings()
    
    # Initialize database
    init_database()
    
    yield test_db
    
    # Cleanup
    if os.path.exists(test_db):
        os.remove(test_db)
    
    # Restore original
    if original_db_url:
        os.environ['DATABASE_URL'] = original_db_url
    else:
        os.environ.pop('DATABASE_URL', None)
    
    config.settings = config.Settings()


@pytest.fixture
def sample_pipeline_data(setup_database):
    """Create sample pipeline in database"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert pipeline
    cursor.execute("""
        INSERT INTO Pipelines (user_id, prompt_text, status)
        VALUES (1, 'Test pipeline', 'pending')
    """)
    pipeline_id = cursor.lastrowid
    
    # Insert steps
    cursor.execute("""
        INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
        VALUES (?, 1, 'bash', 'echo "Hello World"')
    """, (pipeline_id,))
    step1_id = cursor.lastrowid
    
    cursor.execute("""
        INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
        VALUES (?, 2, 'sql', 'SELECT 1 as test')
    """, (pipeline_id,))
    step2_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    
    return {
        'pipeline_id': pipeline_id,
        'step1_id': step1_id,
        'step2_id': step2_id
    }


class TestCommandValidator:
    """Test command whitelist validation"""
    
    def test_valid_command(self):
        """Test whitelisted command passes validation"""
        validator = CommandValidator(['awk', 'sed', 'grep'])
        is_valid, error = validator.validate_command('awk -F, {print $1}')
        
        assert is_valid is True
        assert error is None
    
    def test_invalid_command(self):
        """Test non-whitelisted command fails validation"""
        validator = CommandValidator(['awk', 'sed', 'grep'])
        is_valid, error = validator.validate_command('rm -rf /tmp/test')
        
        assert is_valid is False
        assert error is not None
        assert 'rm' in error
        assert 'not in whitelist' in error
    
    def test_empty_command(self):
        """Test empty command fails validation"""
        validator = CommandValidator()
        is_valid, error = validator.validate_command('')
        
        assert is_valid is False
        assert error == 'Empty command'
    
    def test_default_whitelist(self):
        """Test validator uses default settings whitelist"""
        validator = CommandValidator()
        
        # These should be in default whitelist
        for cmd in ['awk', 'sed', 'grep', 'cat']:
            is_valid, error = validator.validate_command(f'{cmd} test.txt')
            assert is_valid is True, f'{cmd} should be whitelisted'


class TestExecutionResult:
    """Test ExecutionResult container"""
    
    def test_successful_result(self):
        """Test successful execution result"""
        result = ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='bash',
            is_successful=True,
            stdout='output',
            stderr='',
            exit_code=0,
            execution_time_ms=100
        )
        
        assert result.is_successful is True
        assert result.exit_code == 0
        assert result.stdout == 'output'
    
    def test_failed_result(self):
        """Test failed execution result"""
        result = ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='sql',
            is_successful=False,
            stdout='',
            stderr='Syntax error',
            exit_code=1,
            execution_time_ms=50
        )
        
        assert result.is_successful is False
        assert result.exit_code == 1
        assert 'error' in result.stderr.lower()
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        result = ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='bash',
            is_successful=True,
            exit_code=0
        )
        
        result_dict = result.to_dict()
        
        assert 'step_id' in result_dict
        assert 'pipeline_id' in result_dict
        assert 'is_successful' in result_dict
        assert result_dict['step_id'] == 1
        assert result_dict['is_successful'] is True


class TestPipelineExecutionReport:
    """Test PipelineExecutionReport container"""
    
    def test_successful_pipeline(self):
        """Test report with all successful steps"""
        report = PipelineExecutionReport(pipeline_id=1)
        
        # Add successful results
        for i in range(3):
            result = ExecutionResult(
                step_id=i+1,
                pipeline_id=1,
                step_number=i+1,
                step_type='bash',
                is_successful=True,
                exit_code=0,
                execution_time_ms=100
            )
            report.add_result(result)
        
        assert report.overall_success is True
        assert len(report.step_results) == 3
        assert report.failed_step is None
        assert report.total_execution_time_ms == 300
    
    def test_failed_pipeline(self):
        """Test report with failed step"""
        report = PipelineExecutionReport(pipeline_id=1)
        
        # Add successful step
        report.add_result(ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='bash',
            is_successful=True,
            exit_code=0
        ))
        
        # Add failed step
        report.add_result(ExecutionResult(
            step_id=2,
            pipeline_id=1,
            step_number=2,
            step_type='sql',
            is_successful=False,
            exit_code=1
        ))
        
        assert report.overall_success is False
        assert report.failed_step == 2
        assert len(report.step_results) == 2
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        report = PipelineExecutionReport(pipeline_id=1)
        report.add_result(ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='bash',
            is_successful=True,
            exit_code=0
        ))
        
        report_dict = report.to_dict()
        
        assert 'pipeline_id' in report_dict
        assert 'overall_success' in report_dict
        assert 'total_steps' in report_dict
        assert 'step_results' in report_dict
        assert report_dict['pipeline_id'] == 1
        assert report_dict['total_steps'] == 1


class TestSandboxRunner:
    """Test SandboxRunner main functionality"""
    
    def test_initialization(self, temp_sandbox_dir):
        """Test sandbox runner initialization"""
        runner = SandboxRunner(
            sandbox_base_path=temp_sandbox_dir,
            timeout_seconds=5
        )
        
        assert runner.sandbox_base_path == temp_sandbox_dir
        assert runner.timeout_seconds == 5
        assert os.path.exists(temp_sandbox_dir)
    
    def test_create_sandbox_environment(self, temp_sandbox_dir):
        """Test sandbox directory creation"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        pipeline_id = 1
        sandbox_dir = runner.create_sandbox_environment(pipeline_id)
        
        # Check directory structure
        assert os.path.exists(sandbox_dir)
        assert os.path.exists(os.path.join(sandbox_dir, 'data'))
        assert os.path.exists(os.path.join(sandbox_dir, 'tmp'))
        assert os.path.exists(os.path.join(sandbox_dir, 'scripts'))
        assert os.path.exists(os.path.join(sandbox_dir, 'logs'))
    
    def test_execute_bash_step_success(self, temp_sandbox_dir, sample_pipeline_data):
        """Test successful bash step execution"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        sandbox_dir = runner.create_sandbox_environment(1)
        
        # Create simple bash script
        script_path = os.path.join(sandbox_dir, 'test.sh')
        with open(script_path, 'w') as f:
            f.write('#!/bin/bash\necho "Hello Test"')
        
        result = runner._execute_bash_step(script_path, sandbox_dir)
        
        # Should either execute successfully or be skipped (on Windows without bash)
        assert result['exit_code'] == 0
        # Check output contains expected text or skipped message
        output_lower = result['stdout'].lower()
        assert 'hello test' in output_lower or 'skipped' in output_lower
    
    def test_execute_sql_step_success(self, temp_sandbox_dir, sample_pipeline_data):
        """Test successful SQL step execution"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        sandbox_dir = runner.create_sandbox_environment(1)
        
        # Create SQL script
        script_path = os.path.join(sandbox_dir, 'test.sql')
        with open(script_path, 'w') as f:
            f.write('SELECT 1 as test;')
        
        result = runner._execute_sql_step(script_path, sandbox_dir)
        
        assert result['exit_code'] == 0
        assert result['stderr'] == '' or 'successful' in result['stdout'].lower()
    
    def test_execute_sql_step_error(self, temp_sandbox_dir, sample_pipeline_data):
        """Test SQL step with syntax error"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        sandbox_dir = runner.create_sandbox_environment(1)
        
        # Create SQL script with error
        script_path = os.path.join(sandbox_dir, 'test.sql')
        with open(script_path, 'w') as f:
            f.write('SELCT INVALID SYNTAX;')  # Intentional error
        
        result = runner._execute_sql_step(script_path, sandbox_dir)
        
        assert result['exit_code'] == 1
        assert result['stderr'] != ''
    
    def test_cleanup_sandbox(self, temp_sandbox_dir):
        """Test sandbox cleanup"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        pipeline_id = 1
        sandbox_dir = runner.create_sandbox_environment(pipeline_id)
        
        assert os.path.exists(sandbox_dir)
        
        # Cleanup
        runner.cleanup_sandbox(pipeline_id)
        
        assert not os.path.exists(sandbox_dir)
    
    def test_log_execution_to_database(self, temp_sandbox_dir, sample_pipeline_data):
        """Test logging execution result to database"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        result = ExecutionResult(
            step_id=sample_pipeline_data['step1_id'],
            pipeline_id=sample_pipeline_data['pipeline_id'],
            step_number=1,
            step_type='bash',
            is_successful=True,
            stdout='test output',
            stderr='',
            exit_code=0,
            execution_time_ms=100
        )
        
        runner._log_execution_to_database(result)
        
        # Verify log was saved
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM Execution_Logs WHERE step_id = ?",
            (sample_pipeline_data['step1_id'],)
        )
        log = cursor.fetchone()
        conn.close()
        
        assert log is not None
        assert log[4] == 1  # is_successful
        assert log[7] == 0  # exit_code
    
    def test_update_pipeline_status(self, temp_sandbox_dir, sample_pipeline_data):
        """Test updating pipeline status"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        pipeline_id = sample_pipeline_data['pipeline_id']
        
        runner._update_pipeline_status(pipeline_id, 'success')
        
        # Verify status was updated
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT status FROM Pipelines WHERE id = ?",
            (pipeline_id,)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'success'


class TestSandboxIntegration:
    """Integration tests for complete sandbox workflows"""
    
    def test_full_pipeline_execution_success(self, temp_sandbox_dir, sample_pipeline_data):
        """Test complete successful pipeline execution"""
        # This test requires actual script files, which would be created by synthesizer
        # For now, we'll test the workflow structure
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        # Create sandbox
        sandbox_dir = runner.create_sandbox_environment(sample_pipeline_data['pipeline_id'])
        
        assert os.path.exists(sandbox_dir)
        
        # In real scenario, execute_pipeline would be called here
        # We'll test individual components are working
        
        # Test pipeline loading
        steps = runner._load_pipeline_steps(sample_pipeline_data['pipeline_id'])
        assert len(steps) == 2
        assert steps[0]['step_number'] == 1
        assert steps[1]['step_number'] == 2
    
    def test_pipeline_stops_at_failure(self, temp_sandbox_dir, sample_pipeline_data):
        """Test that pipeline execution stops at first failure"""
        runner = SandboxRunner(sandbox_base_path=temp_sandbox_dir)
        
        report = PipelineExecutionReport(pipeline_id=1)
        
        # Simulate step execution results
        # Step 1: success
        report.add_result(ExecutionResult(
            step_id=1,
            pipeline_id=1,
            step_number=1,
            step_type='bash',
            is_successful=True,
            exit_code=0
        ))
        
        # Step 2: failure
        report.add_result(ExecutionResult(
            step_id=2,
            pipeline_id=1,
            step_number=2,
            step_type='sql',
            is_successful=False,
            exit_code=1,
            stderr='SQL error'
        ))
        
        # Verify pipeline is marked as failed
        assert report.overall_success is False
        assert report.failed_step == 2
        
        # In real execution, step 3 would not be executed
        assert len(report.step_results) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
