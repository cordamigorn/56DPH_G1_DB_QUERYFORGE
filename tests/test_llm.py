"""
Unit tests for LLM Pipeline Generator (Phase 2)
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from app.services.llm import (
    GeminiClient,
    PromptBuilder,
    ResponseParser,
    PipelineValidator
)


class TestPromptBuilder:
    """Test prompt construction"""
    
    def test_build_system_prompt_with_tables(self):
        """Test system prompt includes database tables"""
        mcp_context = {
            "database": {
                "tables": [
                    {
                        "name": "orders",
                        "columns": [
                            {"name": "id", "type": "INTEGER"},
                            {"name": "amount", "type": "DECIMAL"}
                        ]
                    }
                ]
            },
            "filesystem": {"files": []}
        }
        
        prompt = PromptBuilder.build_system_prompt(mcp_context)
        
        assert "orders" in prompt
        assert "id (INTEGER)" in prompt
        assert "amount (DECIMAL)" in prompt
    
    def test_build_system_prompt_with_files(self):
        """Test system prompt includes filesystem files"""
        mcp_context = {
            "database": {"tables": []},
            "filesystem": {
                "files": [
                    {
                        "path": "data/sales.csv",
                        "type": "csv",
                        "headers": ["id", "customer", "amount"]
                    }
                ]
            }
        }
        
        prompt = PromptBuilder.build_system_prompt(mcp_context)
        
        assert "data/sales.csv" in prompt
        assert "CSV with columns" in prompt
    
    def test_build_user_prompt(self):
        """Test user prompt formatting"""
        user_request = "Import sales data"
        
        prompt = PromptBuilder.build_user_prompt(user_request)
        
        assert "Import sales data" in prompt
        assert "Task:" in prompt
    
    def test_build_complete_prompt(self):
        """Test complete prompt combines system and user"""
        mcp_context = {
            "database": {"tables": []},
            "filesystem": {"files": []}
        }
        user_request = "Test task"
        
        prompt = PromptBuilder.build_complete_prompt(user_request, mcp_context)
        
        assert "Test task" in prompt
        assert "expert data pipeline generator" in prompt


class TestResponseParser:
    """Test response parsing"""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON response"""
        response_text = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "bash",
                    "content": "echo test",
                    "description": "Test step"
                }
            ]
        })
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is True
        assert len(result["pipeline"]) == 1
        assert result["pipeline"][0]["step_number"] == 1
    
    def test_parse_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown"""
        response_text = """```json
{
  "pipeline": [
    {
      "step_number": 1,
      "type": "sql",
      "content": "SELECT * FROM orders"
    }
  ]
}
```"""
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is True
        assert len(result["pipeline"]) == 1
    
    def test_parse_missing_pipeline_key(self):
        """Test parsing JSON without pipeline key"""
        response_text = json.dumps({"data": []})
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is False
        assert "Missing 'pipeline' key" in str(result.get("validation_errors", []))
    
    def test_parse_empty_pipeline(self):
        """Test parsing empty pipeline array"""
        response_text = json.dumps({"pipeline": []})
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is False
        assert "empty" in str(result.get("validation_errors", [])).lower()
    
    def test_parse_invalid_step_type(self):
        """Test parsing step with invalid type"""
        response_text = json.dumps({
            "pipeline": [
                {
                    "step_number": 1,
                    "type": "invalid",
                    "content": "test"
                }
            ]
        })
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is False
    
    def test_parse_missing_step_fields(self):
        """Test parsing step with missing required fields"""
        response_text = json.dumps({
            "pipeline": [
                {
                    "step_number": 1
                    # Missing type and content
                }
            ]
        })
        
        result = ResponseParser.parse_response(response_text)
        
        assert result["success"] is False


class TestPipelineValidator:
    """Test pipeline validation"""
    
    def test_validate_bash_allowed_command(self):
        """Test validation passes for allowed Bash command"""
        mcp_context = {
            "database": {"tables": []},
            "filesystem": {"files": []}
        }
        
        validator = PipelineValidator(mcp_context)
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "awk -F',' '{print}' file.csv"
            }
        ]
        
        result = validator.validate_pipeline(pipeline)
        
        assert result["is_valid"] is True
        assert len(result["errors"]) == 0
    
    def test_validate_bash_prohibited_command(self):
        """Test validation fails for prohibited Bash command"""
        mcp_context = {
            "database": {"tables": []},
            "filesystem": {"files": []}
        }
        
        validator = PipelineValidator(mcp_context)
        pipeline = [
            {
                "step_number": 1,
                "type": "bash",
                "content": "rm -rf /"
            }
        ]
        
        result = validator.validate_pipeline(pipeline)
        
        assert result["is_valid"] is False
        assert len(result["errors"]) > 0
        assert "prohibited" in result["errors"][0]["error_type"]
    
    def test_validate_sql_existing_table(self):
        """Test SQL validation passes for existing table"""
        mcp_context = {
            "database": {
                "tables": [
                    {"name": "orders", "columns": []}
                ]
            },
            "filesystem": {"files": []}
        }
        
        validator = PipelineValidator(mcp_context)
        pipeline = [
            {
                "step_number": 1,
                "type": "sql",
                "content": "SELECT * FROM orders"
            }
        ]
        
        result = validator.validate_pipeline(pipeline)
        
        assert result["is_valid"] is True
    
    def test_validate_sql_nonexistent_table(self):
        """Test SQL validation fails for nonexistent table"""
        mcp_context = {
            "database": {"tables": []},
            "filesystem": {"files": []}
        }
        
        validator = PipelineValidator(mcp_context)
        pipeline = [
            {
                "step_number": 1,
                "type": "sql",
                "content": "SELECT * FROM nonexistent"
            }
        ]
        
        result = validator.validate_pipeline(pipeline)
        
        assert result["is_valid"] is False
        assert any("table_not_found" in str(e) for e in result["errors"])
    
    def test_validate_destructive_sql_warning(self):
        """Test destructive SQL operations generate warnings"""
        mcp_context = {
            "database": {
                "tables": [{"name": "orders", "columns": []}]
            },
            "filesystem": {"files": []}
        }
        
        validator = PipelineValidator(mcp_context)
        pipeline = [
            {
                "step_number": 1,
                "type": "sql",
                "content": "DROP TABLE orders"
            }
        ]
        
        result = validator.validate_pipeline(pipeline)
        
        # Should have warnings but might still be valid
        assert len(result["warnings"]) > 0
        assert any("destructive" in str(w) for w in result["warnings"])


class TestGeminiClient:
    """Test Gemini API client (mocked)"""
    
    @patch('app.services.llm.genai.GenerativeModel')
    @patch('app.services.llm.genai.configure')
    def test_client_initialization(self, mock_configure, mock_model):
        """Test client initializes with API key"""
        with patch('app.services.llm.settings.GEMINI_API_KEY', 'test_key'):
            client = GeminiClient()
            
            mock_configure.assert_called_once_with(api_key='test_key')
            assert client.api_key == 'test_key'
    
    @patch('app.services.llm.genai.GenerativeModel')
    @patch('app.services.llm.genai.configure')
    def test_generate_content_success(self, mock_configure, mock_model_class):
        """Test successful content generation"""
        # Mock response
        mock_response = Mock()
        mock_response.text = '{"pipeline": []}'
        
        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_model
        
        with patch('app.services.llm.settings.GEMINI_API_KEY', 'test_key'):
            client = GeminiClient()
            result = client.generate_content("test prompt")
            
            assert result["success"] is True
            assert "response" in result
    
    def test_client_requires_api_key(self):
        """Test client raises error without API key"""
        with patch('app.services.llm.settings.GEMINI_API_KEY', ''):
            with pytest.raises(ValueError, match="GEMINI_API_KEY is required"):
                GeminiClient()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
