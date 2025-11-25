"""
LLM Pipeline Generator
Handles pipeline generation using Google Gemini API
"""
import json
import re
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

import google.generativeai as genai

from app.core.config import settings
from app.services.mcp import MCPContextManager

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini API client with retry logic and timeout handling
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay_seconds: Optional[float] = None
    ):
        """
        Initialize Gemini API client
        
        Args:
            api_key: Gemini API key (uses settings if None)
            model_name: Model to use (uses settings if None)
            timeout_seconds: Request timeout (uses settings if None)
            max_retries: Maximum retry attempts (uses settings if None)
            retry_delay_seconds: Delay between retries (uses settings if None)
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.timeout_seconds = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.GEMINI_MAX_RETRIES
        self.retry_delay_seconds = retry_delay_seconds or settings.GEMINI_RETRY_DELAY_SECONDS
        
        # Validate API key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in .env file.")
        
        # Configure Gemini API
        genai.configure(api_key=self.api_key)
        
        # Initialize model
        self.model = genai.GenerativeModel(self.model_name)
        
        logger.info(f"Gemini client initialized with model: {self.model_name}")
    
    def generate_content(
        self,
        prompt: str,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Generate content using Gemini API with retry logic
        
        Args:
            prompt: Complete prompt to send to API
            retry_count: Current retry attempt (internal use)
            
        Returns:
            Dictionary with success status and response/error
            
        Response structure:
            {
                "success": bool,
                "response": str (if success),
                "error": str (if failure),
                "error_type": str (if failure)
            }
        """
        try:
            start_time = time.time()
            
            logger.info(f"Sending request to Gemini API (attempt {retry_count + 1}/{self.max_retries + 1})")
            
            # Safety settings - disable blocking
            safety_settings = [
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                }
            ]
            
            # Generate content with timeout
            response = self.model.generate_content(
                prompt,
                generation_config={
                    'temperature': 0.1,  # Low temperature for consistent output
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': 2048,
                },
                safety_settings=safety_settings
            )
            
            elapsed_time = time.time() - start_time
            
            # Check if response is valid
            if not response or not hasattr(response, 'text'):
                # Check for safety blocking
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                        if finish_reason == 2:  # SAFETY
                            raise ValueError(
                                "Response blocked by safety filters. "
                                "Try rephrasing your request or use a different prompt."
                            )
                        elif finish_reason == 3:  # RECITATION
                            raise ValueError(
                                "Response blocked due to recitation. "
                                "Try a more specific or different request."
                            )
                raise ValueError("Empty or invalid response from Gemini API")
            
            if not response.text:
                raise ValueError("Empty response text from Gemini API")
            
            logger.info(f"Gemini API response received in {elapsed_time:.2f}s")
            
            return {
                "success": True,
                "response": response.text,
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            logger.error(f"Gemini API error ({error_type}): {error_message}")
            
            # Determine if we should retry
            should_retry = self._should_retry(error_type, retry_count)
            
            if should_retry:
                logger.info(f"Retrying after {self.retry_delay_seconds}s delay...")
                time.sleep(self.retry_delay_seconds)
                return self.generate_content(prompt, retry_count + 1)
            
            return {
                "success": False,
                "error": error_message,
                "error_type": error_type
            }
    
    def _should_retry(self, error_type: str, retry_count: int) -> bool:
        """
        Determine if request should be retried
        
        Args:
            error_type: Type of error encountered
            retry_count: Current retry count
            
        Returns:
            True if should retry, False otherwise
        """
        # Don't retry if max retries reached
        if retry_count >= self.max_retries:
            logger.info(f"Max retries ({self.max_retries}) reached, not retrying")
            return False
        
        # Retry on network/transient errors
        retryable_errors = [
            'ConnectionError',
            'Timeout',
            'ServiceUnavailable',
            'InternalServerError',
            'RateLimitError'
        ]
        
        # Don't retry on authentication/permission errors
        non_retryable_errors = [
            'AuthenticationError',
            'PermissionDenied',
            'InvalidArgument'
        ]
        
        if any(err in error_type for err in non_retryable_errors):
            logger.info(f"Non-retryable error type: {error_type}")
            return False
        
        if any(err in error_type for err in retryable_errors):
            logger.info(f"Retryable error type: {error_type}")
            return True
        
        # Default: retry for unknown errors
        logger.info(f"Unknown error type: {error_type}, will retry")
        return True


class PromptBuilder:
    """
    Constructs optimized prompts for Gemini API
    """
    
    @staticmethod
    def build_system_prompt(mcp_context: Dict[str, Any]) -> str:
        """
        Build system prompt with MCP context
        
        Args:
            mcp_context: Complete MCP metadata
            
        Returns:
            System prompt string
        """
        # Extract database information
        tables = mcp_context.get("database", {}).get("tables", [])
        table_descriptions = []
        
        for table in tables:
            table_name = table.get("name", "unknown")
            columns = table.get("columns", [])
            column_desc = ", ".join([
                f"{col['name']} ({col['type']})" 
                for col in columns
            ])
            table_descriptions.append(f"- {table_name}: {column_desc}")
        
        tables_text = "\n".join(table_descriptions) if table_descriptions else "No tables available"
        
        # Extract filesystem information
        files = mcp_context.get("filesystem", {}).get("files", [])
        file_descriptions = []
        
        for file in files:
            file_path = file.get("path", "unknown")
            file_type = file.get("type", "unknown")
            
            if file_type == "csv" and "headers" in file:
                headers = ", ".join(file.get("headers", []))
                file_descriptions.append(f"- {file_path} (CSV with columns: {headers})")
            elif file_type == "json" and "preview" in file:
                # Extract JSON structure from preview
                preview = file.get("preview", "")
                try:
                    import json
                    data = json.loads(preview)
                    if isinstance(data, list) and len(data) > 0:
                        fields = ", ".join(data[0].keys())
                        file_descriptions.append(f"- {file_path} (JSON array with fields: {fields})")
                    else:
                        file_descriptions.append(f"- {file_path} (JSON)")
                except:
                    file_descriptions.append(f"- {file_path} (JSON)")
            elif file_type == "json" and "structure" in file:
                structure = file.get("structure", {})
                file_descriptions.append(f"- {file_path} (JSON: {structure.get('root_type', 'object')})")
            else:
                file_descriptions.append(f"- {file_path} ({file_type})")
        
        files_text = "\n".join(file_descriptions) if file_descriptions else "No files available"
        
        # Get allowed Bash commands
        allowed_commands = settings.ALLOWED_BASH_COMMANDS
        commands_text = ", ".join(allowed_commands)
        
        system_prompt = f"""You are an expert data pipeline generator. Your task is to create executable Bash and SQL pipeline steps from natural language requests.

AVAILABLE RESOURCES:

Database Tables:
{tables_text}

Available Files:
{files_text}

CONSTRAINTS:
1. ONLY reference tables and files listed above
2. ONLY use these Bash commands: {commands_text}
3. Generate steps in proper execution order
4. Use /tmp directory for intermediate files
5. Follow SQL best practices
6. Include proper error handling
7. **CRITICAL**: ALWAYS match field names between JSON files and database tables EXACTLY
   - If JSON fields don't match table columns, suggest creating a new table OR using UPDATE to modify only matching fields
   - Pay attention to field name differences (e.g., 'stock_level' vs 'stock_quantity')
   - Ensure all required table columns have values or defaults

OUTPUT FORMAT (strict JSON):
{{
  "pipeline": [
    {{
      "step_number": 1,
      "type": "bash",
      "content": "exact bash command",
      "description": "what this step does"
    }},
    {{
      "step_number": 2,
      "type": "sql",
      "content": "exact SQL statement",
      "description": "what this step does"
    }}
  ]
}}

RULES:
- step_number must be sequential starting from 1
- type must be either "bash" or "sql"
- content must be valid, executable code
- Do NOT include markdown code blocks
- Do NOT reference non-existent tables or files
- Do NOT try to insert JSON fields into non-matching table columns
- Return ONLY valid JSON"""
        
        return system_prompt
    
    @staticmethod
    def build_user_prompt(user_request: str) -> str:
        """
        Build user prompt from request
        
        Args:
            user_request: Natural language task description
            
        Returns:
            User prompt string
        """
        return f"""Task: {user_request}

Generate a pipeline to complete this task."""
    
    @staticmethod
    def build_complete_prompt(
        user_request: str,
        mcp_context: Dict[str, Any]
    ) -> str:
        """
        Build complete prompt combining system and user prompts
        
        Args:
            user_request: Natural language task description
            mcp_context: Complete MCP metadata
            
        Returns:
            Complete prompt string
        """
        system_prompt = PromptBuilder.build_system_prompt(mcp_context)
        user_prompt = PromptBuilder.build_user_prompt(user_request)
        
        return f"{system_prompt}\n\n{user_prompt}"


class ResponseParser:
    """
    Parses and validates Gemini API responses
    """
    
    @staticmethod
    def parse_response(response_text: str) -> Dict[str, Any]:
        """
        Parse Gemini response and extract pipeline JSON
        
        Args:
            response_text: Raw response from Gemini API
            
        Returns:
            Dictionary with parsing result
            
        Response structure:
            {
                "success": bool,
                "pipeline": list (if success),
                "error": str (if failure)
            }
        """
        try:
            # Try to extract JSON from response
            json_data = ResponseParser._extract_json(response_text)
            
            if not json_data:
                return {
                    "success": False,
                    "error": "No valid JSON found in response",
                    "raw_response": response_text
                }
            
            # Validate structure
            validation_result = ResponseParser._validate_structure(json_data)
            
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": "JSON structure validation failed",
                    "validation_errors": validation_result["errors"]
                }
            
            return {
                "success": True,
                "pipeline": json_data.get("pipeline", [])
            }
            
        except Exception as e:
            logger.error(f"Response parsing error: {e}")
            return {
                "success": False,
                "error": f"Parsing exception: {str(e)}"
            }
    
    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from text (handles markdown code blocks)
        
        Args:
            text: Text potentially containing JSON
            
        Returns:
            Parsed JSON dictionary or None
        """
        # Remove markdown code blocks if present
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        # Try direct JSON parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object in text
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if "pipeline" in data:
                    return data
            except json.JSONDecodeError:
                continue
        
        return None
    
    @staticmethod
    def _validate_structure(json_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate JSON structure against schema
        
        Args:
            json_data: Parsed JSON data
            
        Returns:
            Validation result with errors if any
        """
        errors = []
        
        # Check for pipeline key
        if "pipeline" not in json_data:
            errors.append("Missing 'pipeline' key in JSON")
            return {"is_valid": False, "errors": errors}
        
        pipeline = json_data["pipeline"]
        
        # Check pipeline is array
        if not isinstance(pipeline, list):
            errors.append("'pipeline' must be an array")
            return {"is_valid": False, "errors": errors}
        
        # Check pipeline not empty
        if len(pipeline) == 0:
            errors.append("'pipeline' array is empty")
            return {"is_valid": False, "errors": errors}
        
        # Validate each step
        for idx, step in enumerate(pipeline):
            step_errors = ResponseParser._validate_step(step, idx)
            errors.extend(step_errors)
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def _validate_step(step: Dict[str, Any], index: int) -> List[str]:
        """
        Validate individual pipeline step
        
        Args:
            step: Step dictionary
            index: Step index in pipeline
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Check required fields
        required_fields = ["step_number", "type", "content"]
        for field in required_fields:
            if field not in step:
                errors.append(f"Step {index}: Missing required field '{field}'")
        
        # Validate step_number
        if "step_number" in step:
            if not isinstance(step["step_number"], int):
                errors.append(f"Step {index}: 'step_number' must be an integer")
            elif step["step_number"] != index + 1:
                errors.append(f"Step {index}: 'step_number' should be {index + 1}, got {step['step_number']}")
        
        # Validate type
        if "type" in step:
            if step["type"] not in ["bash", "sql"]:
                errors.append(f"Step {index}: 'type' must be 'bash' or 'sql', got '{step['type']}'")
        
        # Validate content
        if "content" in step:
            if not isinstance(step["content"], str) or not step["content"].strip():
                errors.append(f"Step {index}: 'content' must be a non-empty string")
        
        return errors


class PipelineValidator:
    """
    Validates generated pipelines against MCP context and safety rules
    """
    
    def __init__(self, mcp_context: Dict[str, Any]):
        """
        Initialize pipeline validator
        
        Args:
            mcp_context: Complete MCP metadata for validation
        """
        self.mcp_context = mcp_context
        self.database = mcp_context.get("database", {})
        self.filesystem = mcp_context.get("filesystem", {})
        
        # Build lookup structures for fast validation
        self.table_names = set(
            table.get("name") 
            for table in self.database.get("tables", [])
        )
        
        # Build detailed table schema map
        self.table_schemas = {}
        for table in self.database.get("tables", []):
            table_name = table.get("name")
            if table_name:
                self.table_schemas[table_name] = {
                    "columns": {col.get("name"): col for col in table.get("columns", [])},
                    "column_names": set(col.get("name") for col in table.get("columns", []))
                }
        
        self.file_paths = set(
            file.get("path") 
            for file in self.filesystem.get("files", [])
        )
        
        # Build file content schema map for JSON files
        self.file_schemas = {}
        for file in self.filesystem.get("files", []):
            file_path = file.get("path")
            if file_path and file_path.endswith(".json"):
                # Extract fields from preview if available
                preview = file.get("preview", "")
                if preview:
                    try:
                        import json
                        data = json.loads(preview)
                        if isinstance(data, list) and len(data) > 0:
                            # Get fields from first object
                            fields = set(data[0].keys())
                            self.file_schemas[file_path] = {
                                "fields": fields,
                                "is_array": True
                            }
                    except:
                        pass
        
        self.allowed_commands = set(settings.ALLOWED_BASH_COMMANDS)
        
        logger.info(f"Validator initialized with {len(self.table_names)} tables, "
                   f"{len(self.file_paths)} files, {len(self.allowed_commands)} allowed commands")
    
    def validate_pipeline(self, pipeline: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate complete pipeline
        
        Args:
            pipeline: List of pipeline steps
            
        Returns:
            Validation result
            
        Response structure:
            {
                "is_valid": bool,
                "errors": list of error dicts,
                "warnings": list of warning dicts
            }
        """
        errors = []
        warnings = []
        
        for step in pipeline:
            step_number = step.get("step_number", 0)
            step_type = step.get("type", "")
            content = step.get("content", "")
            
            if step_type == "bash":
                bash_errors, bash_warnings = self._validate_bash_step(step_number, content)
                errors.extend(bash_errors)
                warnings.extend(bash_warnings)
            
            elif step_type == "sql":
                sql_errors, sql_warnings = self._validate_sql_step(step_number, content)
                errors.extend(sql_errors)
                warnings.extend(sql_warnings)
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_bash_step(self, step_number: int, content: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate Bash step
        
        Args:
            step_number: Step number
            content: Bash command content
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Extract command (first word)
        tokens = content.strip().split()
        if not tokens:
            errors.append({
                "step_number": step_number,
                "error_type": "empty_command",
                "message": "Bash step has empty content"
            })
            return errors, warnings
        
        primary_command = tokens[0]
        
        # Check if command is whitelisted
        if primary_command not in self.allowed_commands:
            errors.append({
                "step_number": step_number,
                "error_type": "prohibited_command",
                "message": f"Command '{primary_command}' is not in whitelist",
                "allowed_commands": list(self.allowed_commands)
            })
        
        # Check for file references
        file_refs = self._extract_file_references(content)
        for file_ref in file_refs:
            # Skip /tmp and absolute system paths
            if file_ref.startswith("/tmp") or file_ref.startswith("C:\\") or file_ref.startswith("/"):
                continue
            
            # Check if file exists in MCP context
            if file_ref not in self.file_paths:
                # Normalize path separators for comparison
                normalized_ref = file_ref.replace("\\", "/")
                if normalized_ref not in self.file_paths:
                    warnings.append({
                        "step_number": step_number,
                        "warning_type": "file_not_found",
                        "message": f"File '{file_ref}' not found in filesystem context",
                        "available_files": list(self.file_paths)[:5]  # Show first 5 files
                    })
        
        return errors, warnings
    
    def _validate_sql_step(self, step_number: int, content: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate SQL step
        
        Args:
            step_number: Step number
            content: SQL content
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        content_upper = content.upper()
        
        # Extract table references
        table_refs = self._extract_table_references(content)
        for table_ref in table_refs:
            if table_ref not in self.table_names:
                errors.append({
                    "step_number": step_number,
                    "error_type": "table_not_found",
                    "message": f"Table '{table_ref}' not found in database schema",
                    "available_tables": list(self.table_names)
                })
        
        # Check for destructive operations
        destructive_patterns = [
            (r'\bDROP\s+TABLE\b', "DROP TABLE"),
            (r'\bTRUNCATE\s+TABLE\b', "TRUNCATE TABLE"),
            (r'\bDELETE\s+FROM\s+\w+\s*(?!WHERE)', "DELETE without WHERE"),
        ]
        
        for pattern, operation in destructive_patterns:
            if re.search(pattern, content_upper):
                warnings.append({
                    "step_number": step_number,
                    "warning_type": "destructive_operation",
                    "message": f"Destructive operation detected: {operation}"
                })
        
        # Validate schema compatibility for INSERT/UPDATE with file references
        schema_errors, schema_warnings = self._validate_schema_compatibility(step_number, content)
        errors.extend(schema_errors)
        warnings.extend(schema_warnings)
        
        return errors, warnings
    
    def _validate_schema_compatibility(self, step_number: int, content: str) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate schema compatibility between JSON files and database tables
        
        Args:
            step_number: Step number
            content: SQL content
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        content_upper = content.upper()
        
        # Check for INSERT or UPDATE operations
        if 'INSERT' not in content_upper and 'UPDATE' not in content_upper:
            return errors, warnings
        
        # Extract target table from INSERT INTO or UPDATE statements
        target_table = None
        insert_match = re.search(r'INSERT\s+INTO\s+(\w+)', content_upper)
        if insert_match:
            target_table = insert_match.group(1).lower()
        else:
            update_match = re.search(r'UPDATE\s+(\w+)', content_upper)
            if update_match:
                target_table = update_match.group(1).lower()
        
        if not target_table or target_table not in self.table_schemas:
            return errors, warnings
        
        # Extract referenced JSON files
        file_refs = self._extract_file_references(content)
        json_files = [f for f in file_refs if f.endswith('.json')]
        
        if not json_files:
            return errors, warnings
        
        # Validate each JSON file against target table schema
        for json_file in json_files:
            if json_file not in self.file_schemas:
                warnings.append({
                    "step_number": step_number,
                    "warning_type": "schema_unknown",
                    "message": f"Cannot validate schema for '{json_file}' - file structure unknown"
                })
                continue
            
            json_schema = self.file_schemas[json_file]
            table_schema = self.table_schemas[target_table]
            
            json_fields = json_schema.get("fields", set())
            table_columns = table_schema.get("column_names", set())
            
            # Check for field mismatches
            missing_in_table = json_fields - table_columns
            missing_in_json = table_columns - json_fields
            
            if missing_in_table:
                errors.append({
                    "step_number": step_number,
                    "error_type": "schema_mismatch",
                    "message": f"Schema mismatch: JSON file '{json_file}' has fields that don't exist in table '{target_table}'",
                    "json_fields": list(json_fields),
                    "table_columns": list(table_columns),
                    "extra_in_json": list(missing_in_table),
                    "missing_from_json": list(missing_in_json),
                    "suggestion": f"Consider creating a new table matching the JSON structure, or use UPDATE to modify only matching fields"
                })
            
            if missing_in_json and not missing_in_table:
                warnings.append({
                    "step_number": step_number,
                    "warning_type": "incomplete_data",
                    "message": f"JSON file '{json_file}' is missing some columns from table '{target_table}'",
                    "missing_columns": list(missing_in_json),
                    "suggestion": "These columns will be NULL or require DEFAULT values"
                })
        
        return errors, warnings
    
    def _extract_file_references(self, content: str) -> List[str]:
        """
        Extract file path references from Bash command
        
        Args:
            content: Bash command content
            
        Returns:
            List of file paths found
        """
        # Simple pattern to match common file paths
        file_patterns = [
            r'[\w./\\-]+\.csv',
            r'[\w./\\-]+\.json',
            r'[\w./\\-]+\.txt',
            r'[\w./\\-]+\.log',
        ]
        
        file_refs = []
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            file_refs.extend(matches)
        
        return list(set(file_refs))
    
    def _extract_table_references(self, content: str) -> List[str]:
        """
        Extract table name references from SQL
        
        Args:
            content: SQL content
            
        Returns:
            List of table names found
        """
        # Common SQL patterns that reference tables
        patterns = [
            r'FROM\s+(\w+)',
            r'JOIN\s+(\w+)',
            r'INTO\s+(\w+)',
            r'TABLE\s+(\w+)',
            r'UPDATE\s+(\w+)',
        ]
        
        table_refs = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            table_refs.extend(matches)
        
        return list(set(table_refs))


class LLMPipelineService:
    """
    Main service orchestrating LLM pipeline generation workflow
    """
    
    def __init__(self):
        """
        Initialize LLM pipeline service
        """
        self.gemini_client = GeminiClient()
        self.mcp_manager = MCPContextManager()
        
        logger.info("LLM Pipeline Service initialized")
    
    async def generate_pipeline(
        self,
        user_prompt: str,
        user_id: int,
        mcp_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate pipeline from user prompt
        
        Args:
            user_prompt: Natural language task description
            user_id: User identifier
            mcp_context: Optional MCP context (fetched if None)
            
        Returns:
            Dictionary with generation result
            
        Response structure:
            {
                "success": bool,
                "pipeline_id": int (if success),
                "pipeline": list (if success),
                "error": str (if failure),
                "error_type": str (if failure)
            }
        """
        try:
            start_time = time.time()
            
            # Step 1: Get MCP context
            if mcp_context is None:
                logger.info("Fetching MCP context")
                mcp_context = await self.mcp_manager.get_full_context_async()
            
            # Step 2: Build prompt
            logger.info("Building prompt for Gemini API")
            complete_prompt = PromptBuilder.build_complete_prompt(
                user_prompt,
                mcp_context
            )
            
            # Step 3: Call Gemini API
            logger.info("Calling Gemini API")
            api_response = self.gemini_client.generate_content(complete_prompt)
            
            if not api_response["success"]:
                return {
                    "success": False,
                    "error": api_response.get("error", "API call failed"),
                    "error_type": api_response.get("error_type", "api_error")
                }
            
            # Step 4: Parse response
            logger.info("Parsing API response")
            parse_result = ResponseParser.parse_response(api_response["response"])
            
            if not parse_result["success"]:
                return {
                    "success": False,
                    "error": parse_result.get("error", "Response parsing failed"),
                    "error_type": "parse_error",
                    "validation_errors": parse_result.get("validation_errors")
                }
            
            pipeline = parse_result["pipeline"]
            
            # Step 5: Validate pipeline
            logger.info("Validating pipeline")
            validator = PipelineValidator(mcp_context)
            validation_result = validator.validate_pipeline(pipeline)
            
            if not validation_result["is_valid"]:
                return {
                    "success": False,
                    "error": "Pipeline validation failed",
                    "error_type": "validation_error",
                    "validation_errors": validation_result["errors"],
                    "warnings": validation_result.get("warnings", [])
                }
            
            # Step 6: Save to database
            logger.info("Saving pipeline to database")
            pipeline_id = await self._save_pipeline_to_database(
                user_id,
                user_prompt,
                pipeline,
                mcp_context
            )
            
            elapsed_time = time.time() - start_time
            logger.info(f"Pipeline generated successfully in {elapsed_time:.2f}s")
            
            return {
                "success": True,
                "pipeline_id": pipeline_id,
                "pipeline": pipeline,
                "warnings": validation_result.get("warnings", []),
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            logger.error(f"Pipeline generation error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "error_type": "internal_error"
            }
    
    async def _save_pipeline_to_database(
        self,
        user_id: int,
        prompt_text: str,
        pipeline: List[Dict[str, Any]],
        mcp_context: Dict[str, Any]
    ) -> int:
        """
        Save pipeline to database
        
        Args:
            user_id: User identifier
            prompt_text: Original user prompt
            pipeline: Generated pipeline steps
            mcp_context: MCP context used for generation
            
        Returns:
            Pipeline ID
        """
        from app.core.database import get_db
        
        async with get_db() as db:
            # Insert pipeline record
            cursor = await db.execute(
                """
                INSERT INTO Pipelines (user_id, prompt_text, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    prompt_text,
                    'pending',
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                )
            )
            
            pipeline_id = cursor.lastrowid
            
            # Insert pipeline steps
            for step in pipeline:
                await db.execute(
                    """
                    INSERT INTO Pipeline_Steps (pipeline_id, step_number, code_type, script_content, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        pipeline_id,
                        step["step_number"],
                        step["type"],
                        step["content"],
                        datetime.now().isoformat()
                    )
                )
            
            # Insert schema snapshot
            await db.execute(
                """
                INSERT INTO Schema_Snapshots (pipeline_id, db_structure, file_list, snapshot_time)
                VALUES (?, ?, ?, ?)
                """,
                (
                    pipeline_id,
                    json.dumps(mcp_context.get("database", {})),
                    json.dumps(mcp_context.get("filesystem", {})),
                    datetime.now().isoformat()
                )
            )
            
            await db.commit()
            
            logger.info(f"Pipeline {pipeline_id} saved with {len(pipeline)} steps")
            
            return pipeline_id


# Export classes
__all__ = [
    'GeminiClient',
    'PromptBuilder',
    'ResponseParser',
    'PipelineValidator',
    'LLMPipelineService'
]
