"""
Unit tests for Bash/SQL Synthesizer (Phase 3)
"""
import pytest
import os
import json
import tempfile
import shutil
from pathlib import Path

from app.services.synthesizer import (
    BashScriptSynthesizer,
    SQLScriptSynthesizer,
    PipelineSynthesizer
)


class TestBashScriptSynthesizer:
    """Test Bash script generation"""
    
    def test_synthesize_basic_script(self):
        """Test basic Bash script generation"""
        script = BashScriptSynthesizer.synthesize(
            step_number=1,
            content="echo 'Hello World'",
            description="Test echo command"
        )
        
        assert "#!/bin/bash" in script
        assert "set -e" in script
        assert "echo 'Hello World'" in script
        assert "Test echo command" in script
        assert "STEP_NUMBER=1" in script
    
    def test_synthesize_includes_logging(self):
        """Test script includes logging functions"""
        script = BashScriptSynthesizer.synthesize(
            step_number=2,
            content="ls -la"
        )
        
        assert "log_info" in script
        assert "log_error" in script
        assert "Starting execution" in script
    
    def test_synthesize_includes_error_handling(self):
        """Test script includes error handling"""
        script = BashScriptSynthesizer.synthesize(
            step_number=1,
            content="test command"
        )
        
        assert "set -e" in script
        assert "set -u" in script
        assert "set -o pipefail" in script
    
    def test_synthesize_includes_timing(self):
        """Test script includes execution timing"""
        script = BashScriptSynthesizer.synthesize(
            step_number=1,
            content="test"
        )
        
        assert "START_TIME" in script
        assert "END_TIME" in script
        assert "DURATION" in script


class TestSQLScriptSynthesizer:
    """Test SQL script generation"""
    
    def test_synthesize_basic_script(self):
        """Test basic SQL script generation"""
        script = SQLScriptSynthesizer.synthesize(
            step_number=1,
            content="SELECT * FROM orders",
            description="Query orders table"
        )
        
        assert "QueryForge Pipeline Step 1" in script
        assert "BEGIN TRANSACTION" in script
        assert "SELECT * FROM orders" in script
        assert "COMMIT" in script
        assert "Query orders table" in script
    
    def test_synthesize_includes_transaction(self):
        """Test script includes transaction wrapper"""
        script = SQLScriptSynthesizer.synthesize(
            step_number=2,
            content="INSERT INTO orders VALUES (1, 100)"
        )
        
        assert "BEGIN TRANSACTION" in script
        assert "COMMIT" in script
    
    def test_synthesize_includes_metadata(self):
        """Test script includes metadata comments"""
        script = SQLScriptSynthesizer.synthesize(
            step_number=1,
            content="SELECT 1"
        )
        
        assert "Generated:" in script
        assert ".mode list" in script
        assert ".headers on" in script
    
    def test_validate_syntax_balanced_transactions(self):
        """Test validation checks balanced transactions"""
        script = """
BEGIN TRANSACTION;
SELECT * FROM test;
COMMIT;
"""
        is_valid, error = SQLScriptSynthesizer.validate_syntax(script)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_syntax_unbalanced_transactions(self):
        """Test validation detects unbalanced transactions"""
        script = """
BEGIN TRANSACTION;
SELECT * FROM test;
"""
        is_valid, error = SQLScriptSynthesizer.validate_syntax(script)
        
        assert is_valid is False
        assert "Unbalanced" in error


class TestPipelineSynthesizer:
    """Test complete pipeline synthesis"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def test_synthesize_single_bash_step(self, temp_dir):
        """Test synthesizing single Bash step"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "echo test",
                "description": "Test step"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=1,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        assert result["pipeline_id"] == 1
        assert result["total_scripts"] == 1
        assert len(result["scripts"]) == 1
        
        # Check script file was created
        script_info = result["scripts"][0]
        assert os.path.exists(script_info["path"])
        assert script_info["filename"] == "step_1_bash.sh"
    
    def test_synthesize_single_sql_step(self, temp_dir):
        """Test synthesizing single SQL step"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "sql",
                "content": "SELECT 1",
                "description": "Test query"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=2,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        assert result["scripts"][0]["filename"] == "step_1_sql.sql"
    
    def test_synthesize_multiple_steps(self, temp_dir):
        """Test synthesizing multiple steps"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "cat data.csv",
                "description": "Read CSV"
            },
            {
                "step_number": 2,
                "type": "sql",
                "content": "CREATE TABLE test (id INT)",
                "description": "Create table"
            },
            {
                "step_number": 3,
                "type": "bash",
                "content": "echo done",
                "description": "Finish"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=3,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        assert result["total_scripts"] == 3
        assert len(result["scripts"]) == 3
        
        # Verify all scripts created
        filenames = [s["filename"] for s in result["scripts"]]
        assert "step_1_bash.sh" in filenames
        assert "step_2_sql.sql" in filenames
        assert "step_3_bash.sh" in filenames
    
    def test_synthesize_creates_manifest(self, temp_dir):
        """Test synthesis creates manifest file"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "echo test"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=4,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        assert "manifest_path" in result
        assert os.path.exists(result["manifest_path"])
        
        # Verify manifest content
        with open(result["manifest_path"], 'r') as f:
            manifest = json.load(f)
        
        assert manifest["pipeline_id"] == 4
        assert manifest["total_scripts"] == 1
        assert len(manifest["scripts"]) == 1
    
    def test_synthesize_creates_pipeline_directory(self, temp_dir):
        """Test synthesis creates pipeline-specific directory"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "test"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=5,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        assert "pipeline_5" in result["output_directory"]
        assert os.path.exists(result["output_directory"])
    
    def test_synthesize_script_content_correct(self, temp_dir):
        """Test synthesized script has correct content"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "echo 'specific test content'"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=6,
            pipeline=pipeline
        )
        
        script_path = result["scripts"][0]["path"]
        
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert "echo 'specific test content'" in content
        assert "#!/bin/bash" in content
    
    def test_synthesize_validates_scripts(self, temp_dir):
        """Test synthesis validates generated scripts"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "echo test"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=7,
            pipeline=pipeline
        )
        
        assert result["success"] is True
        # If validation enabled, scripts should pass
    
    def test_synthesize_handles_unknown_type(self, temp_dir):
        """Test synthesis handles unknown step type"""
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        
        pipeline = [
            {
                "step_number": 1,
                "type": "invalid",
                "content": "test"
            }
        ]
        
        result = synthesizer.synthesize_pipeline(
            pipeline_id=8,
            pipeline=pipeline
        )
        
        assert result["success"] is False
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
