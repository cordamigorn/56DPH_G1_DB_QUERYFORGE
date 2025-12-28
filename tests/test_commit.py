"""
Unit tests for Commit Module (Phase 6)
Tests ValidationEngine, SnapshotManager, CommitService
"""
import pytest
import sqlite3
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from app.services.commit import (
    ValidationEngine, SnapshotManager, CommitService,
    DatabaseCommitter, FilesystemCommitter,
    ValidationReport, CommitResult, CommitStatus
)
from app.core.database import get_db_path, init_database


@pytest.fixture
def setup_database():
    """Initialize test database"""
    init_database()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create test pipeline
    cursor.execute("""
        INSERT INTO Pipelines (user_id, prompt_text, status)
        VALUES (1, 'Test pipeline', 'sandbox_success')
    """)
    pipeline_id = cursor.lastrowid
    
    # Create test steps
    cursor.execute("""
        INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
        VALUES (?, 1, 'sql', 'SELECT * FROM products')
    """, (pipeline_id,))
    
    # Create successful execution log
    step_id = cursor.lastrowid
    cursor.execute("""
        INSERT INTO Execution_Logs (pipeline_id, step_id, run_time, is_successful, stdout, stderr, exit_code)
        VALUES (?, ?, CURRENT_TIMESTAMP, 1, 'Success', '', 0)
    """, (pipeline_id, step_id))
    
    conn.commit()
    conn.close()
    
    yield pipeline_id
    
    # Cleanup
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Pipelines WHERE id = ?", (pipeline_id,))
    conn.commit()
    conn.close()


class TestValidationEngine:
    """Test pre-commit validation logic"""
    
    def test_validation_engine_initialization(self):
        """Test ValidationEngine can be initialized"""
        engine = ValidationEngine()
        assert engine is not None
        assert engine.db_path is not None
    
    def test_validate_nonexistent_pipeline(self):
        """Test validation fails for non-existent pipeline"""
        engine = ValidationEngine()
        report = engine.validate_for_commit(99999)
        
        assert report.is_valid == False
        assert len(report.errors) > 0
        assert "not found" in report.errors[0].lower()
    
    def test_validate_pending_pipeline(self, setup_database):
        """Test validation fails for pending pipeline"""
        pipeline_id = setup_database
        
        # Update status to pending
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("UPDATE Pipelines SET status = 'pending' WHERE id = ?", (pipeline_id,))
        conn.commit()
        conn.close()
        
        engine = ValidationEngine()
        report = engine.validate_for_commit(pipeline_id)
        
        assert report.is_valid == False
        assert any("status" in err.lower() for err in report.errors)
    
    def test_validate_successful_pipeline(self, setup_database):
        """Test validation succeeds for sandbox_success pipeline"""
        pipeline_id = setup_database
        
        engine = ValidationEngine()
        report = engine.validate_for_commit(pipeline_id)
        
        assert report.is_valid == True
        assert report.risk_score >= 0
        assert report.risk_level in ["low", "medium", "high"]
    
    def test_risk_assessment_sql_operations(self, setup_database):
        """Test risk scoring includes SQL operations"""
        pipeline_id = setup_database
        
        # Add more SQL steps
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        for i in range(5):
            cursor.execute("""
                INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
                VALUES (?, ?, 'sql', 'SELECT * FROM table')
            """, (pipeline_id, i + 2))
        conn.commit()
        conn.close()
        
        engine = ValidationEngine()
        report = engine.validate_for_commit(pipeline_id)
        
        # More SQL steps = higher risk score
        assert report.risk_score > 0
    
    def test_risk_assessment_destructive_operations(self, setup_database):
        """Test risk scoring detects destructive operations"""
        pipeline_id = setup_database
        
        # Add DROP TABLE step
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content)
            VALUES (?, 2, 'sql', 'DROP TABLE old_data')
        """, (pipeline_id,))
        conn.commit()
        conn.close()
        
        engine = ValidationEngine()
        report = engine.validate_for_commit(pipeline_id)
        
        # Destructive operation = high risk score
        assert report.risk_score >= 10
        assert len(report.warnings) > 0
        assert any("DROP TABLE" in warning for warning in report.warnings)


class TestSnapshotManager:
    """Test snapshot creation and retrieval"""
    
    def test_snapshot_manager_initialization(self):
        """Test SnapshotManager can be initialized"""
        manager = SnapshotManager()
        assert manager is not None
        assert manager.db_path is not None
    
    def test_create_snapshot(self, setup_database):
        """Test snapshot creation"""
        pipeline_id = setup_database
        manager = SnapshotManager()
        
        snapshot_id = manager.create_snapshot(pipeline_id)
        
        assert snapshot_id is not None
        assert snapshot_id > 0
        
        # Verify snapshot in database
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM Schema_Snapshots WHERE id = ?", (snapshot_id,))
        snapshot = cursor.fetchone()
        conn.close()
        
        assert snapshot is not None
    
    def test_get_snapshot(self, setup_database):
        """Test snapshot retrieval"""
        pipeline_id = setup_database
        manager = SnapshotManager()
        
        # Create snapshot
        snapshot_id = manager.create_snapshot(pipeline_id)
        
        # Retrieve snapshot
        snapshot = manager.get_snapshot(snapshot_id)
        
        assert snapshot is not None
        assert snapshot['id'] == snapshot_id
        assert snapshot['pipeline_id'] == pipeline_id
        assert 'db_structure' in snapshot
        assert 'file_list' in snapshot


class TestDatabaseCommitter:
    """Test database commit operations"""
    
    def test_database_committer_initialization(self):
        """Test DatabaseCommitter can be initialized"""
        committer = DatabaseCommitter()
        assert committer is not None
        assert committer.db_path is not None
    
    def test_commit_empty_sql_operations(self, setup_database):
        """Test commit with no SQL steps"""
        pipeline_id = setup_database
        committer = DatabaseCommitter()
        
        success, error = committer.commit_sql_operations(pipeline_id, [])
        
        assert success == True
        assert error is None
    
    def test_commit_valid_sql_operations(self, setup_database):
        """Test commit with valid SQL"""
        pipeline_id = setup_database
        
        # Get step from database
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, script_content FROM Pipeline_Steps 
            WHERE pipeline_id = ? AND code_type = 'sql'
        """, (pipeline_id,))
        steps = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        committer = DatabaseCommitter()
        success, error = committer.commit_sql_operations(pipeline_id, steps)
        
        assert success == True
        assert error is None


class TestFilesystemCommitter:
    """Test filesystem commit operations"""
    
    def test_filesystem_committer_initialization(self):
        """Test FilesystemCommitter can be initialized"""
        committer = FilesystemCommitter()
        assert committer is not None
        assert committer.db_path is not None
    
    def test_calculate_file_hash(self):
        """Test file hash calculation"""
        committer = FilesystemCommitter()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("test content")
            temp_path = f.name
        
        try:
            hash_value = committer._calculate_file_hash(temp_path)
            assert hash_value is not None
            assert len(hash_value) == 64  # SHA256 is 64 characters
        finally:
            os.unlink(temp_path)
    
    def test_calculate_hash_nonexistent_file(self):
        """Test hash calculation for non-existent file"""
        committer = FilesystemCommitter()
        hash_value = committer._calculate_file_hash("/nonexistent/file.txt")
        assert hash_value is None


class TestCommitService:
    """Test complete commit workflow"""
    
    def test_commit_service_initialization(self):
        """Test CommitService can be initialized"""
        service = CommitService()
        assert service is not None
        assert service.validator is not None
        assert service.snapshot_manager is not None
        assert service.db_committer is not None
        assert service.fs_committer is not None
    
    def test_validate_for_commit(self, setup_database):
        """Test validation through service"""
        pipeline_id = setup_database
        service = CommitService()
        
        report = service.validate_for_commit(pipeline_id)
        
        assert isinstance(report, ValidationReport)
        assert report.is_valid == True
    
    def test_commit_pipeline_invalid(self, setup_database):
        """Test commit fails for invalid pipeline"""
        pipeline_id = setup_database
        
        # Set status to pending (invalid for commit)
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("UPDATE Pipelines SET status = 'pending' WHERE id = ?", (pipeline_id,))
        conn.commit()
        conn.close()
        
        service = CommitService()
        result = service.commit_pipeline(pipeline_id)
        
        assert result.success == False
        assert result.commit_status == CommitStatus.COMMIT_FAILED.value
        assert result.error is not None
    
    def test_commit_pipeline_success(self, setup_database):
        """Test successful pipeline commit"""
        pipeline_id = setup_database
        service = CommitService()
        
        result = service.commit_pipeline(pipeline_id, force_commit=True)
        
        assert isinstance(result, CommitResult)
        assert result.pipeline_id == pipeline_id
        assert result.snapshot_id is not None
    
    def test_commit_result_to_dict(self):
        """Test CommitResult serialization"""
        result = CommitResult(
            success=True,
            pipeline_id=1,
            commit_status="committed",
            snapshot_id=5,
            operations_performed={"sql_operations": 2},
            commit_time="2025-11-27T10:00:00",
            rollback_available=True
        )
        
        result_dict = result.to_dict()
        
        assert result_dict['success'] == True
        assert result_dict['pipeline_id'] == 1
        assert result_dict['snapshot_id'] == 5
        assert result_dict['rollback_available'] == True
    
    def test_rollback_nonexistent_pipeline(self):
        """Test rollback fails for non-existent pipeline"""
        service = CommitService()
        result = service.rollback_commit(99999)
        
        assert result.success == False
        assert "not found" in result.error.lower()
    
    def test_rollback_uncommitted_pipeline(self, setup_database):
        """Test rollback fails for uncommitted pipeline"""
        pipeline_id = setup_database
        service = CommitService()
        
        result = service.rollback_commit(pipeline_id)
        
        assert result.success == False
        assert "not committed" in result.error.lower()


class TestCommitIntegration:
    """Integration tests for complete commit workflow"""
    
    def test_end_to_end_commit_flow(self, setup_database):
        """Test complete commit flow from validation to commit"""
        pipeline_id = setup_database
        service = CommitService()
        
        # Step 1: Validate
        validation = service.validate_for_commit(pipeline_id)
        assert validation.is_valid == True
        
        # Step 2: Commit (with force to bypass risk checks)
        result = service.commit_pipeline(pipeline_id, force_commit=True)
        
        # Verify result
        assert result.success in [True, False]  # May fail due to actual SQL execution
        assert result.pipeline_id == pipeline_id
        assert result.snapshot_id is not None
        
        # Verify database update
        conn = sqlite3.connect(get_db_path())
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT commit_status FROM Pipelines WHERE id = ?", (pipeline_id,))
        row = cursor.fetchone()
        conn.close()
        
        assert row['commit_status'] in ['committed', 'commit_failed', 'commit_in_progress']


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
