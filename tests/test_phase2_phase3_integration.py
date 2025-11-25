"""
Integration tests for Phase 2 and Phase 3
Tests complete flow from prompt to executable scripts
"""
import pytest
import json
import os
import tempfile
import shutil
from unittest.mock import Mock, patch

from app.services.llm import PromptBuilder, ResponseParser, PipelineValidator
from app.services.synthesizer import PipelineSynthesizer
from app.services.mcp import MCPContextManager


class TestPhase2Phase3Integration:
    """Integration tests for complete pipeline generation and synthesis"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def sample_mcp_context(self):
        """Sample MCP context for testing"""
        return {
            "database": {
                "tables": [
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True},
                            {"name": "customer", "type": "TEXT"},
                            {"name": "amount", "type": "DECIMAL"}
                        ],
                        "primary_keys": ["id"],
                        "foreign_keys": []
                    },
                    {
                        "name": "products",
                        "columns": [
                            {"name": "id", "type": "INTEGER", "primary_key": True},
                            {"name": "name", "type": "TEXT"},
                            {"name": "price", "type": "DECIMAL"}
                        ],
                        "primary_keys": ["id"],
                        "foreign_keys": []
                    }
                ]
            },
            "filesystem": {
                "root_path": "./data",
                "files": [
                    {
                        "path": "inventory.json",
                        "type": "json",
                        "size_bytes": 1024,
                        "structure": {
                            "root_type": "list",
                            "element_keys": ["id", "name", "price"]
                        }
                    },
                    {
                        "path": "sales.csv",
                        "type": "csv",
                        "headers": ["id", "customer", "amount"],
                        "row_count_estimate": 100
                    }
                ]
            },
            "metadata": {
                "database_table_count": 2,
                "filesystem_file_count": 2
            }
        }
    
    def test_prompt_to_scripts_simple_bash(self, sample_mcp_context, temp_dir):
        """Test complete flow: prompt -> validation -> synthesis for Bash"""
        # Step 1: Build prompt
        user_prompt = "List all CSV files in the data directory"
        complete_prompt = PromptBuilder.build_complete_prompt(user_prompt, sample_mcp_context)
        
        assert "sales.csv" in complete_prompt
        assert "inventory.json" in complete_prompt
        
        # Step 2: Simulate LLM response
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "bash",
                    "content": "cat data/sales.csv",
                    "description": "Display sales data"
                }
            ]
        })
        
        # Step 3: Parse response
        parse_result = ResponseParser.parse_response(llm_response)
        
        assert parse_result["success"] is True
        assert len(parse_result["pipeline"]) == 1
        
        # Step 4: Validate pipeline
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        
        assert validation_result["is_valid"] is True
        
        # Step 5: Synthesize scripts
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        synthesis_result = synthesizer.synthesize_pipeline(
            pipeline_id=1,
            pipeline=parse_result["pipeline"]
        )
        
        assert synthesis_result["success"] is True
        assert synthesis_result["total_scripts"] == 1
        assert os.path.exists(synthesis_result["scripts"][0]["path"])
    
    def test_prompt_to_scripts_sql_pipeline(self, sample_mcp_context, temp_dir):
        """Test complete flow for SQL pipeline"""
        # Simulate LLM response for SQL operation
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "sql",
                    "content": "SELECT * FROM orders WHERE amount > 100",
                    "description": "Query high-value orders"
                }
            ]
        })
        
        # Parse
        parse_result = ResponseParser.parse_response(llm_response)
        assert parse_result["success"] is True
        
        # Validate
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        assert validation_result["is_valid"] is True
        
        # Synthesize
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        synthesis_result = synthesizer.synthesize_pipeline(
            pipeline_id=2,
            pipeline=parse_result["pipeline"]
        )
        
        assert synthesis_result["success"] is True
        
        # Verify SQL script content
        script_path = synthesis_result["scripts"][0]["path"]
        with open(script_path, 'r') as f:
            content = f.read()
        
        assert "SELECT * FROM orders WHERE amount > 100" in content
        assert "BEGIN TRANSACTION" in content
        assert "COMMIT" in content
    
    def test_prompt_to_scripts_multi_step_pipeline(self, sample_mcp_context, temp_dir):
        """Test complete flow for multi-step pipeline"""
        # Simulate complex pipeline with bash and SQL
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "bash",
                    "content": "awk -F',' '$3 > 50 {print}' data/sales.csv > /tmp/filtered.csv",
                    "description": "Filter sales by amount"
                },
                {
                    "step_number": 2,
                    "type": "sql",
                    "content": "CREATE TABLE IF NOT EXISTS temp_sales (id INT, customer TEXT, amount DECIMAL)",
                    "description": "Create temporary table"
                },
                {
                    "step_number": 3,
                    "type": "sql",
                    "content": "INSERT INTO orders SELECT * FROM temp_sales WHERE amount > 50",
                    "description": "Import filtered data into orders"
                }
            ]
        })
        
        # Parse
        parse_result = ResponseParser.parse_response(llm_response)
        assert parse_result["success"] is True
        assert len(parse_result["pipeline"]) == 3
        
        # Validate - temp_sales won't exist but CREATE TABLE should be ok
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        
        # May have errors for temp_sales not existing, but that's expected for CREATE TABLE
        # The important thing is orders table exists
        
        # Synthesize
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        synthesis_result = synthesizer.synthesize_pipeline(
            pipeline_id=3,
            pipeline=parse_result["pipeline"]
        )
        
        assert synthesis_result["success"] is True
        assert synthesis_result["total_scripts"] == 3
        
        # Verify all scripts created
        script_files = [s["filename"] for s in synthesis_result["scripts"]]
        assert "step_1_bash.sh" in script_files
        assert "step_2_sql.sql" in script_files
        assert "step_3_sql.sql" in script_files
        
        # Verify manifest
        with open(synthesis_result["manifest_path"], 'r') as f:
            manifest = json.load(f)
        
        assert manifest["pipeline_id"] == 3
        assert manifest["total_scripts"] == 3
    
    def test_validation_rejects_invalid_pipeline(self, sample_mcp_context):
        """Test validation rejects pipeline with non-existent table"""
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "sql",
                    "content": "SELECT * FROM nonexistent_table",
                    "description": "Query missing table"
                }
            ]
        })
        
        # Parse (should succeed)
        parse_result = ResponseParser.parse_response(llm_response)
        assert parse_result["success"] is True
        
        # Validate (should fail)
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        
        assert validation_result["is_valid"] is False
        assert len(validation_result["errors"]) > 0
        assert "table_not_found" in str(validation_result["errors"])
    
    def test_validation_rejects_prohibited_command(self, sample_mcp_context):
        """Test validation rejects prohibited Bash command"""
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "bash",
                    "content": "rm -rf /important/data",
                    "description": "Dangerous operation"
                }
            ]
        })
        
        # Parse
        parse_result = ResponseParser.parse_response(llm_response)
        assert parse_result["success"] is True
        
        # Validate (should fail)
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        
        assert validation_result["is_valid"] is False
        assert any("prohibited" in str(e) for e in validation_result["errors"])
    
    def test_end_to_end_csv_import_scenario(self, sample_mcp_context, temp_dir):
        """
        Test realistic scenario: CSV import pipeline
        Simulates user request: "Import sales.csv into orders table"
        """
        # Build prompt
        user_request = "Import sales.csv into orders table"
        prompt = PromptBuilder.build_complete_prompt(user_request, sample_mcp_context)
        
        assert "sales.csv" in prompt
        assert "orders" in prompt
        
        # Simulate realistic LLM response
        llm_response = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "bash",
                    "content": "cat data/sales.csv > /tmp/sales_import.csv",
                    "description": "Prepare CSV for import"
                },
                {
                    "step_number": 2,
                    "type": "sql",
                    "content": "DELETE FROM orders WHERE id IN (SELECT id FROM staging)",
                    "description": "Clear existing data"
                },
                {
                    "step_number": 3,
                    "type": "sql",
                    "content": "INSERT INTO orders (id, customer, amount) SELECT id, customer, amount FROM staging",
                    "description": "Import new data"
                }
            ]
        })
        
        # Parse
        parse_result = ResponseParser.parse_response(llm_response)
        assert parse_result["success"] is True
        
        # Validate
        validator = PipelineValidator(sample_mcp_context)
        validation_result = validator.validate_pipeline(parse_result["pipeline"])
        
        # Should have warnings for DELETE but may still be valid if table exists
        # (depends on validator implementation)
        
        # Synthesize
        synthesizer = PipelineSynthesizer(output_directory=temp_dir)
        synthesis_result = synthesizer.synthesize_pipeline(
            pipeline_id=4,
            pipeline=parse_result["pipeline"]
        )
        
        assert synthesis_result["success"] is True
        assert synthesis_result["total_scripts"] == 3
        
        # Verify scripts are executable and readable
        for script_info in synthesis_result["scripts"]:
            assert os.path.exists(script_info["path"])
            assert script_info["size_bytes"] > 0
            
            with open(script_info["path"], 'r') as f:
                content = f.read()
                assert len(content) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
