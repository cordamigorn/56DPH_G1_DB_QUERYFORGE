"""
Unit tests for Error Detection & Repair Loop Module
Tests ErrorAnalyzer, RepairModule, and RepairLoop functionality
"""
import os
import pytest
import tempfile
import sqlite3
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.repair import (
    ErrorAnalyzer,
    RepairModule,
    RepairLoop,
    ErrorReport,
    ErrorCategory,
    ContextSnapshot
)
from app.core.database import init_database, get_db_path


@pytest.fixture
def setup_database():
    """Initialize test database"""
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
    
    if original_db_url:
        os.environ['DATABASE_URL'] = original_db_url
    else:
        os.environ.pop('DATABASE_URL', None)
    
    config.settings = config.Settings()


@pytest.fixture
def sample_failed_execution(setup_database):
    """Create sample failed execution in database"""
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert pipeline
    cursor.execute("""
        INSERT INTO Pipelines (user_id, prompt_text, status)
        VALUES (1, 'Import data from file', 'failed')
    """)
    pipeline_id = cursor.lastrowid
    
    # Insert step
    cursor.execute("""
        INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
        VALUES (?, 1, 'bash', 'cat nonexistent.csv')
    """, (pipeline_id,))
    step_id = cursor.lastrowid
    
    # Insert failed execution log
    cursor.execute("""
        INSERT INTO Execution_Logs (
            pipeline_id, step_id, run_time, is_successful,
            stdout, stderr, exit_code, execution_time_ms
        ) VALUES (?, ?, ?, 0, '', 'cat: nonexistent.csv: No such file or directory', 1, 50)
    """, (pipeline_id, step_id, datetime.now().isoformat()))
    log_id = cursor.lastrowid
    
    # Insert schema snapshot
    schema_data = {
        "tables": [
            {"name": "products", "columns": [{"name": "id", "type": "INTEGER"}]}
        ]
    }
    file_data = ["data/inventory.json", "data/products.csv"]
    
    cursor.execute("""
        INSERT INTO Schema_Snapshots (pipeline_id, db_structure, file_list)
        VALUES (?, ?, ?)
    """, (pipeline_id, json.dumps(schema_data), json.dumps(file_data)))
    
    conn.commit()
    conn.close()
    
    return {
        'pipeline_id': pipeline_id,
        'step_id': step_id,
        'log_id': log_id
    }


class TestErrorCategory:
    """Test error classification enum"""
    
    def test_error_categories_exist(self):
        """Test all expected error categories are defined"""
        assert hasattr(ErrorCategory, 'FILE_NOT_FOUND')
        assert hasattr(ErrorCategory, 'TABLE_MISSING')
        assert hasattr(ErrorCategory, 'SYNTAX_ERROR')
        assert hasattr(ErrorCategory, 'PERMISSION_DENIED')
        assert hasattr(ErrorCategory, 'TIMEOUT')
        assert hasattr(ErrorCategory, 'DATA_VALIDATION')
        assert hasattr(ErrorCategory, 'UNKNOWN')
    
    def test_error_category_values(self):
        """Test error category values are strings"""
        assert ErrorCategory.FILE_NOT_FOUND.value == 'file_not_found'
        assert ErrorCategory.TABLE_MISSING.value == 'table_missing'
        assert ErrorCategory.SYNTAX_ERROR.value == 'syntax_error'


class TestErrorReport:
    """Test ErrorReport container"""
    
    def test_error_report_creation(self):
        """Test creating error report"""
        report = ErrorReport(
            execution_log_id=1,
            pipeline_id=1,
            step_id=1,
            step_number=1,
            step_type='bash',
            original_content='cat missing.txt',
            error_message='No such file',
            exit_code=1,
            category=ErrorCategory.FILE_NOT_FOUND
        )
        
        assert report.execution_log_id == 1
        assert report.category == ErrorCategory.FILE_NOT_FOUND
        assert 'No such file' in report.error_message
    
    def test_error_report_to_dict(self):
        """Test conversion to dictionary"""
        report = ErrorReport(
            execution_log_id=1,
            pipeline_id=1,
            step_id=1,
            step_number=1,
            step_type='sql',
            original_content='SELECT * FROM missing',
            error_message='Table not found',
            exit_code=1,
            category=ErrorCategory.TABLE_MISSING
        )
        
        report_dict = report.to_dict()
        
        assert 'execution_log_id' in report_dict
        assert 'category' in report_dict
        assert report_dict['category'] == 'table_missing'
        assert report_dict['step_type'] == 'sql'


class TestContextSnapshot:
    """Test ContextSnapshot container"""
    
    def test_context_snapshot_creation(self):
        """Test creating context snapshot"""
        snapshot = ContextSnapshot(
            database_schema={'tables': []},
            file_list=['file1.csv', 'file2.json'],
            previous_steps=[],
            pipeline_prompt='Test task'
        )
        
        assert snapshot.database_schema == {'tables': []}
        assert len(snapshot.file_list) == 2
        assert snapshot.pipeline_prompt == 'Test task'
    
    def test_context_snapshot_to_dict(self):
        """Test conversion to dictionary"""
        snapshot = ContextSnapshot(
            database_schema={'tables': [{'name': 'test'}]},
            file_list=['data.csv'],
            previous_steps=[{'step': 1}],
            pipeline_prompt='Import data'
        )
        
        snapshot_dict = snapshot.to_dict()
        
        assert 'database_schema' in snapshot_dict
        assert 'file_list' in snapshot_dict
        assert 'previous_steps' in snapshot_dict
        assert 'pipeline_prompt' in snapshot_dict


class TestErrorAnalyzer:
    """Test ErrorAnalyzer functionality"""
    
    def test_initialization(self):
        """Test error analyzer initialization"""
        analyzer = ErrorAnalyzer()
        assert analyzer is not None
    
    def test_classify_file_not_found(self):
        """Test file not found error classification"""
        analyzer = ErrorAnalyzer()
        
        errors = [
            "No such file or directory",
            "cannot open file.txt",
            "file not found",
            "does not exist"
        ]
        
        for error in errors:
            category = analyzer.classify_error_type(error)
            assert category == ErrorCategory.FILE_NOT_FOUND, f"Failed for: {error}"
    
    def test_classify_table_missing(self):
        """Test table missing error classification"""
        analyzer = ErrorAnalyzer()
        
        errors = [
            "table does not exist",
            "no such table: products",
            "unknown table 'items'"
        ]
        
        for error in errors:
            category = analyzer.classify_error_type(error)
            assert category == ErrorCategory.TABLE_MISSING, f"Failed for: {error}"
    
    def test_classify_syntax_error(self):
        """Test syntax error classification"""
        analyzer = ErrorAnalyzer()
        
        errors = [
            "syntax error near 'SELECT'",
            "unexpected token",
            "parse error",
            "invalid syntax"
        ]
        
        for error in errors:
            category = analyzer.classify_error_type(error)
            assert category == ErrorCategory.SYNTAX_ERROR, f"Failed for: {error}"
    
    def test_classify_timeout(self):
        """Test timeout error classification"""
        analyzer = ErrorAnalyzer()
        
        errors = [
            "execution timeout",
            "operation timed out",
            "time limit exceeded"
        ]
        
        for error in errors:
            category = analyzer.classify_error_type(error)
            assert category == ErrorCategory.TIMEOUT, f"Failed for: {error}"
    
    def test_classify_unknown(self):
        """Test unknown error classification"""
        analyzer = ErrorAnalyzer()
        
        category = analyzer.classify_error_type("Some random error")
        assert category == ErrorCategory.UNKNOWN
    
    def test_analyze_execution_failure(self, sample_failed_execution):
        """Test analyzing execution failure from database"""
        analyzer = ErrorAnalyzer()
        
        report = analyzer.analyze_execution_failure(
            sample_failed_execution['log_id']
        )
        
        assert report is not None
        assert report.pipeline_id == sample_failed_execution['pipeline_id']
        assert report.step_id == sample_failed_execution['step_id']
        assert report.category == ErrorCategory.FILE_NOT_FOUND
        assert 'No such file' in report.error_message
    
    def test_analyze_nonexistent_log(self, setup_database):
        """Test analyzing nonexistent log returns None"""
        analyzer = ErrorAnalyzer()
        
        report = analyzer.analyze_execution_failure(99999)
        
        assert report is None
    
    def test_extract_relevant_context(self, sample_failed_execution):
        """Test extracting context for repair"""
        analyzer = ErrorAnalyzer()
        
        context = analyzer.extract_relevant_context(
            sample_failed_execution['pipeline_id'],
            sample_failed_execution['step_id']
        )
        
        assert context is not None
        assert context.pipeline_prompt == 'Import data from file'
        assert isinstance(context.database_schema, dict)
        assert isinstance(context.file_list, list)
        assert len(context.file_list) > 0


class TestRepairModule:
    """Test RepairModule functionality"""
    
    def test_initialization(self):
        """Test repair module initialization"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            assert module is not None
            assert module.repair_history == {}
    
    def test_validate_fix_bash_valid(self):
        """Test validating valid bash fix"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            is_valid, error = module.validate_fix('cat data.csv', 'bash')
            assert is_valid is True
            assert error is None
    
    def test_validate_fix_bash_invalid_command(self):
        """Test validating bash fix with prohibited command"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            is_valid, error = module.validate_fix('rm -rf /', 'bash')
            assert is_valid is False
            assert 'Prohibited command' in error
    
    def test_validate_fix_empty_code(self):
        """Test validating empty fix"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            is_valid, error = module.validate_fix('', 'bash')
            assert is_valid is False
            assert 'empty' in error.lower()
    
    def test_validate_fix_sql_destructive(self):
        """Test validating SQL fix with destructive operation"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            is_valid, error = module.validate_fix('DROP TABLE products', 'sql')
            assert is_valid is False
            assert 'Destructive' in error
    
    def test_is_duplicate_fix(self):
        """Test duplicate fix detection"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            pipeline_id = 1
            code = 'cat data.csv'
            
            # First time should not be duplicate
            assert module._is_duplicate_fix(pipeline_id, code) is False
            
            # Record the fix
            module._record_fix(pipeline_id, code)
            
            # Second time should be duplicate
            assert module._is_duplicate_fix(pipeline_id, code) is True
    
    def test_parse_repair_response_valid(self):
        """Test parsing valid repair response"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            response = '''{
                "fix_reason": "File path was incorrect",
                "patched_code": "cat data/correct.csv"
            }'''
            
            result = module._parse_repair_response(response)
            
            assert result['success'] is True
            assert 'patched_code' in result
            assert 'fix_reason' in result
            assert result['patched_code'] == 'cat data/correct.csv'
    
    def test_parse_repair_response_with_markdown(self):
        """Test parsing response with markdown code blocks"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            response = '''```json
            {
                "fix_reason": "Fixed path",
                "patched_code": "cat data.csv"
            }
            ```'''
            
            result = module._parse_repair_response(response)
            
            assert result['success'] is True
    
    def test_parse_repair_response_invalid_json(self):
        """Test parsing invalid JSON response"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            response = 'This is not JSON'
            
            result = module._parse_repair_response(response)
            
            assert result['success'] is False
            assert 'error' in result
    
    def test_parse_repair_response_missing_fields(self):
        """Test parsing response missing required fields"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            response = '{"fix_reason": "test"}'
            
            result = module._parse_repair_response(response)
            
            assert result['success'] is False
    
    def test_apply_fix(self, sample_failed_execution):
        """Test applying fix to database"""
        with patch('app.services.repair.GeminiClient'):
            module = RepairModule()
            
            new_code = 'cat data/inventory.csv'
            
            success = module.apply_fix(
                sample_failed_execution['pipeline_id'],
                sample_failed_execution['step_id'],
                new_code
            )
            
            assert success is True
            
            # Verify fix was applied
            db_path = get_db_path()
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT script_content FROM Pipeline_Steps WHERE id = ?",
                (sample_failed_execution['step_id'],)
            )
            content = cursor.fetchone()[0]
            conn.close()
            
            assert content == new_code
    
    @patch('app.services.repair.GeminiClient')
    def test_generate_fix_success(self, mock_client_class, sample_failed_execution):
        """Test successful fix generation"""
        # Mock Gemini client
        mock_client = Mock()
        mock_client.generate_content.return_value = {
            'success': True,
            'response': '{"fix_reason": "Fixed file path", "patched_code": "cat data/inventory.csv"}'
        }
        mock_client_class.return_value = mock_client
        
        module = RepairModule()
        
        error_report = ErrorReport(
            execution_log_id=1,
            pipeline_id=sample_failed_execution['pipeline_id'],
            step_id=sample_failed_execution['step_id'],
            step_number=1,
            step_type='bash',
            original_content='cat nonexistent.csv',
            error_message='No such file',
            exit_code=1,
            category=ErrorCategory.FILE_NOT_FOUND
        )
        
        context = ContextSnapshot(
            database_schema={'tables': []},
            file_list=['data/inventory.csv'],
            previous_steps=[],
            pipeline_prompt='Import data'
        )
        
        result = module.generate_fix(error_report, context)
        
        assert result['success'] is True
        assert 'patched_code' in result
        assert 'fix_reason' in result


class TestRepairLoop:
    """Test RepairLoop orchestration"""
    
    def test_initialization(self):
        """Test repair loop initialization"""
        loop = RepairLoop()
        assert loop is not None
        assert loop.max_attempts == 3  # Default from settings
    
    def test_get_repair_attempt_count(self, sample_failed_execution):
        """Test getting repair attempt count"""
        loop = RepairLoop()
        
        count = loop._get_repair_attempt_count(
            sample_failed_execution['pipeline_id']
        )
        
        assert count == 0  # No repairs yet
        
        # Add a repair log
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO Repair_Logs (
                pipeline_id, attempt_number, original_error,
                ai_fix_reason, patched_code, repair_successful
            ) VALUES (?, 1, 'Test error', 'Test fix', 'test code', 1)
        """, (sample_failed_execution['pipeline_id'],))
        
        conn.commit()
        conn.close()
        
        count = loop._get_repair_attempt_count(
            sample_failed_execution['pipeline_id']
        )
        
        assert count == 1
    
    def test_log_repair_attempt(self, sample_failed_execution):
        """Test logging repair attempt"""
        loop = RepairLoop()
        
        loop._log_repair_attempt(
            pipeline_id=sample_failed_execution['pipeline_id'],
            attempt_number=1,
            original_error='File not found',
            ai_fix_reason='Corrected file path',
            patched_code='cat data.csv',
            repair_successful=True
        )
        
        # Verify log was saved
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM Repair_Logs WHERE pipeline_id = ?",
            (sample_failed_execution['pipeline_id'],)
        )
        log = cursor.fetchone()
        conn.close()
        
        assert log is not None
        assert log[2] == 1  # attempt_number
        assert log[7] == 1  # repair_successful (column index 7, not 6)
    
    def test_mark_pipeline_failed(self, sample_failed_execution):
        """Test marking pipeline as failed"""
        loop = RepairLoop()
        
        loop._mark_pipeline_failed(sample_failed_execution['pipeline_id'])
        
        # Verify status
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT status FROM Pipelines WHERE id = ?",
            (sample_failed_execution['pipeline_id'],)
        )
        status = cursor.fetchone()[0]
        conn.close()
        
        assert status == 'failed'
    
    @patch('app.services.repair.RepairModule')
    @patch('app.services.repair.ErrorAnalyzer')
    def test_repair_and_retry_max_attempts_reached(
        self,
        mock_analyzer_class,
        mock_repair_class,
        sample_failed_execution
    ):
        """Test repair loop when max attempts already reached"""
        # Add 3 repair attempts to database
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        for i in range(1, 4):
            cursor.execute("""
                INSERT INTO Repair_Logs (
                    pipeline_id, attempt_number, original_error,
                    ai_fix_reason, patched_code, repair_successful
                ) VALUES (?, ?, 'Error', 'Fix', 'code', 0)
            """, (sample_failed_execution['pipeline_id'], i))
        
        conn.commit()
        conn.close()
        
        loop = RepairLoop()
        
        result = loop.repair_and_retry(
            sample_failed_execution['pipeline_id'],
            sample_failed_execution['log_id']
        )
        
        assert result['success'] is False
        assert 'Maximum repair attempts' in result['error']


class TestRepairIntegration:
    """Integration tests for repair workflow"""
    
    def test_end_to_end_error_analysis(self, sample_failed_execution):
        """Test complete error analysis workflow"""
        analyzer = ErrorAnalyzer()
        
        # Analyze error
        error_report = analyzer.analyze_execution_failure(
            sample_failed_execution['log_id']
        )
        
        assert error_report is not None
        assert error_report.category == ErrorCategory.FILE_NOT_FOUND
        
        # Extract context
        context = analyzer.extract_relevant_context(
            error_report.pipeline_id,
            error_report.step_id
        )
        
        assert context is not None
        assert len(context.file_list) > 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
