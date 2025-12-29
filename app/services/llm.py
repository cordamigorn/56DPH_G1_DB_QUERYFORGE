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

import google.genai as genai

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
        retry_delay_seconds: Optional[float] = None,
        max_output_tokens: Optional[int] = None
    ):
        """
        Initialize Gemini API client
        
        Args:
            api_key: Gemini API key (uses settings if None)
            model_name: Model to use (uses settings if None)
            timeout_seconds: Request timeout (uses settings if None)
            max_retries: Maximum retry attempts (uses settings if None)
            retry_delay_seconds: Delay between retries (uses settings if None)
            max_output_tokens: Maximum tokens to allow in responses
        """
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL
        self.timeout_seconds = timeout_seconds or settings.GEMINI_TIMEOUT_SECONDS
        self.max_retries = max_retries or settings.GEMINI_MAX_RETRIES
        self.retry_delay_seconds = retry_delay_seconds or settings.GEMINI_RETRY_DELAY_SECONDS
        self.max_output_tokens = max_output_tokens or settings.GEMINI_MAX_OUTPUT_TOKENS
        
        # Validate API key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required. Set it in .env file.")
        
        # Initialize Gemini API client
        self.client = genai.Client(api_key=self.api_key)
        
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
            
            # Generate content using new API
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    'temperature': 0.1,  # Low temperature for consistent output
                    'top_p': 0.95,
                    'top_k': 40,
                    'max_output_tokens': self.max_output_tokens,
                }
            )
            
            elapsed_time = time.time() - start_time
            
            # Extract response text from new API format
            if hasattr(response, 'text'):
                response_text = response.text.strip()
            elif hasattr(response, 'candidates') and response.candidates:
                # Fallback to old format if needed
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    text_parts = [
                        getattr(part, "text", "")
                        for part in candidate.content.parts
                        if hasattr(part, "text")
                    ]
                    response_text = "".join(text_parts).strip()
                else:
                    raise ValueError("Gemini returned no content parts")
            else:
                raise ValueError("Gemini returned no content")
            
            if not response_text:
                raise ValueError("Empty response text from Gemini API")
            
            logger.info(f"Gemini API response received in {elapsed_time:.2f}s")
            
            return {
                "success": True,
                "response": response_text,
                "elapsed_time": elapsed_time
            }
            
        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)
            
            logger.error(f"Gemini API error ({error_type}): {error_message}")
            
            # Determine if we should retry
            should_retry = self._should_retry(error_type, retry_count, error_message)
            
            if should_retry:
                logger.info(f"Retrying after {self.retry_delay_seconds}s delay...")
                time.sleep(self.retry_delay_seconds)
                return self.generate_content(prompt, retry_count + 1)
            
            return {
                "success": False,
                "error": error_message,
                "error_type": error_type
            }
    
    def _should_retry(self, error_type: str, retry_count: int, error_message: str = "") -> bool:
        """
        Determine if request should be retried
        
        Args:
            error_type: Type of error encountered
            retry_count: Current retry count
            error_message: Error message text for additional checks
            
        Returns:
            True if should retry, False otherwise
        """
        # Don't retry if max retries reached
        if retry_count >= self.max_retries:
            logger.info(f"Max retries ({self.max_retries}) reached, not retrying")
            return False
        
        # Don't retry on model-blocked responses (safety/blocklist/no content)
        blocked_markers = [
            "safety",
            "blocked",
            "blocklist",
            "prohibited",
            "sensitive_information",
            "recitation"
        ]
        if any(marker in error_message.lower() for marker in blocked_markers):
            logger.info(f"Non-retryable model response error: {error_message}")
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
    
    def _format_finish_reason(self, finish_reason: Any) -> str:
        """
        Convert numeric finish_reason to a human-readable label
        """
        reason_map = {
            0: "unspecified",
            1: "stop",
            2: "max_tokens",
            3: "safety",
            4: "recitation",
            5: "other",
            6: "blocklist",
            7: "prohibited_content",
            8: "sensitive_information",
            9: "malformed_function_call"
        }
        return reason_map.get(finish_reason, str(finish_reason))


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
        csv_previews = {}  # Store CSV previews separately for detailed context
        json_previews = {}  # Store JSON previews separately
        
        for file in files:
            file_path = file.get("path", "unknown")
            file_type = file.get("type", "unknown")
            
            if file_type == "csv" and "headers" in file:
                headers = ", ".join(file.get("headers", []))
                row_count = file.get("row_count_estimate", 0)
                file_descriptions.append(f"- {file_path} (CSV with {row_count} rows, columns: {headers})")
                
                # Store preview data if available
                if "preview" in file:
                    csv_previews[file_path] = file.get("preview", [])
                    
            elif file_type == "json":
                structure = file.get("structure", {})
                root_type = structure.get("root_type", "unknown")
                
                if root_type == "list":
                    array_length = structure.get("array_length", 0)
                    element_keys = structure.get("element_keys", [])
                    fields = ", ".join(element_keys)
                    file_descriptions.append(f"- {file_path} (JSON array with {array_length} items, fields: {fields})")
                    
                    # Store preview if available
                    if "preview" in file:
                        json_previews[file_path] = {
                            "type": "array",
                            "data": file.get("preview", []),
                            "total_items": file.get("total_items", 0),
                            "preview_count": file.get("preview_count", 0)
                        }
                elif root_type == "dict":
                    keys = structure.get("keys", [])
                    file_descriptions.append(f"- {file_path} (JSON object with keys: {', '.join(keys)})")
                    
                    if "preview" in file:
                        json_previews[file_path] = {
                            "type": "dict",
                            "data": file.get("preview", {})
                        }
                else:
                    file_descriptions.append(f"- {file_path} (JSON)")
            else:
                file_descriptions.append(f"- {file_path} ({file_type})")
        
        files_text = "\n".join(file_descriptions) if file_descriptions else "No files available"
        
        # Build CSV preview section if we have any
        csv_preview_text = ""
        if csv_previews:
            preview_sections = []
            for csv_path, preview_rows in csv_previews.items():
                preview_count = len(preview_rows)
                preview_sections.append(f"\n**CSV FILE DATA - {csv_path}:**")
                preview_sections.append(f"Total rows to import: {preview_count}")
                preview_sections.append(f"\n**YOU MUST GENERATE INSERT STATEMENTS FOR ALL {preview_count} ROWS BELOW:**\n")
                
                # Show ALL rows, not just first few
                for i, row in enumerate(preview_rows, 1):
                    # Show row as dict format
                    row_str = ", ".join([f"{k}={v}" for k, v in row.items()])
                    preview_sections.append(f"  Row {i}: {row_str}")
                
                preview_sections.append(f"\n**IMPORTANT: All {preview_count} rows above MUST be included in your INSERT statements!**")
            
            csv_preview_text = "\n".join(preview_sections)
        
        # Build JSON preview section if we have any
        json_preview_text = ""
        if json_previews:
            preview_sections = []
            for json_path, json_info in json_previews.items():
                json_type = json_info.get("type")
                
                if json_type == "array":
                    data = json_info.get("data", [])
                    total_items = json_info.get("total_items", len(data))
                    preview_count = json_info.get("preview_count", len(data))
                    
                    preview_sections.append(f"\n**JSON FILE DATA - {json_path}:**")
                    preview_sections.append(f"Total items: {total_items}")
                    preview_sections.append(f"\n**YOU MUST USE THE EXACT DATA FROM ALL {preview_count} ITEMS BELOW:**\n")
                    
                    # Show ALL items
                    import json as json_lib
                    for i, item in enumerate(data, 1):
                        # Format each field safely to avoid string interpolation issues
                        fields = []
                        for key, value in item.items():
                            # Properly escape and format values
                            if isinstance(value, str):
                                fields.append(f"{key}: '{value}'")
                            else:
                                fields.append(f"{key}: {value}")
                        item_str = "{" + ", ".join(fields) + "}"
                        preview_sections.append(f"  Item {i}: {item_str}")
                    
                    preview_sections.append(f"\n**IMPORTANT: All {preview_count} items above MUST be used with their EXACT field values!**")
                    preview_sections.append(f"**DO NOT invent product names, categories, or prices - use ONLY the data shown above!**")
                    
                elif json_type == "dict":
                    data = json_info.get("data", {})
                    preview_sections.append(f"\n**JSON FILE DATA - {json_path}:**")
                    import json as json_lib
                    preview_sections.append(json_lib.dumps(data, indent=2, ensure_ascii=False))
            
            json_preview_text = "\n".join(preview_sections)
        
        # Get allowed Bash commands
        allowed_commands = settings.ALLOWED_BASH_COMMANDS
        commands_text = ", ".join(allowed_commands)
        
        system_prompt = f"""You are an expert data pipeline generator. Your task is to create executable Bash and SQL pipeline steps from natural language requests.

**IMPORTANT DATABASE INFORMATION:**
- Database Type: SQLite (NOT MySQL, NOT PostgreSQL)
- SQLite does NOT support: LOAD DATA INFILE, LOAD DATA LOCAL INFILE, or similar MySQL commands
- **CRITICAL FOR WINDOWS**: Do NOT use sqlite3 CLI command in bash - SQL steps are executed via Python
- For CSV import: Generate SQL INSERT statements directly in a SQL step
- Use standard SQLite SQL syntax only

**BEST PRACTICE FOR CSV IMPORT:**
- **MANDATORY**: Use ALL rows from CSV file previews below - generate INSERT for EVERY SINGLE ROW!
- **CRITICAL**: The preview shows the COMPLETE file contents - use ALL of them, not just first few!
- **DO NOT** generate only 5 sample rows - this is WRONG!
- **DO NOT** invent or create random sample data - use EXACT data from preview!
- Count the rows in preview and generate exactly that many INSERT statements
- Match the exact values from the CSV file preview
- Use BEGIN TRANSACTION; and COMMIT; for better performance
- Format: INSERT INTO table (col1, col2) VALUES (val1, val2);
- Quote string values with single quotes, escape internal quotes by doubling them

**BEST PRACTICE FOR JSON IMPORT:**
- **MANDATORY**: Use ALL items from JSON file previews below - use EXACT field values!
- **CRITICAL**: JSON files contain actual data - DO NOT invent product names, categories, or any other data!
- **DO NOT** create sample/fake data like "Laptop", "Mouse" - use ONLY the fields present in JSON!
- Match JSON field names EXACTLY to database columns
- If JSON fields don't match table columns, you must handle the mismatch (e.g., only insert matching fields)
- Use BEGIN TRANSACTION; and COMMIT; for better performance

AVAILABLE RESOURCES:

Database Tables:
{tables_text}

Available Files:
{files_text}
{csv_preview_text}
{json_preview_text}

CONSTRAINTS:
1. ONLY reference tables and files listed above
2. For bash steps, ONLY use these commands: {commands_text}
3. **NEVER use sqlite3 command** - SQL steps are executed directly via Python
4. Generate steps in proper execution order
5. Follow SQLite SQL syntax (NOT MySQL syntax)
6. **CRITICAL**: SQL step content must be actual SQL code, NOT file paths
   - Valid: "INSERT INTO Sales VALUES (1, 'John', 100);"
   - Invalid: "/tmp/file.sql" or "sqlite3 db < file.sql"
7. For CSV data loading:
   - **CRITICAL**: Use EXACT data from CSV preview above - generate INSERT for EVERY row shown
   - DO NOT invent or generate random sample data
   - Match column values exactly as shown in the preview
   - Generate multiple INSERT statements in one SQL step
   - Use transactions (BEGIN/COMMIT) for performance
   - **IMPORTANT**: Before INSERT, check if table exists - use CREATE TABLE IF NOT EXISTS
   - **IMPORTANT**: Handle duplicate keys - use INSERT OR IGNORE or INSERT OR REPLACE when appropriate
8. Include proper error handling in bash steps
9. **CRITICAL - FIELD MATCHING**: ALWAYS match field names between JSON files and database tables EXACTLY
   - **NEVER invent data** for fields not present in JSON/CSV
   - If JSON has `stock_level` but table needs `stock_quantity`, use the JSON value for the matching semantic field
   - If JSON is missing required table columns (e.g., no `product_name` in JSON), **SKIP INSERT completely** or use UPDATE instead
   - **DO NOT** create fake product names like "Laptop", "Mouse" when they don't exist in source data
   - **DO NOT** INSERT if required NOT NULL fields are missing - use UPDATE to modify existing rows instead
   - Only insert columns that have actual data in the source file
   - Example: If JSON only has {{product_id, stock_level}}, only INSERT those fields (or their semantic equivalents)
   - **BEST PRACTICE**: If table already has data and JSON lacks required fields, use UPDATE instead of INSERT

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
- Do NOT include markdown code blocks or explanatory text
- Do NOT reference non-existent tables or files
- Do NOT try to insert JSON fields into non-matching table columns
- **CRITICAL**: Your entire response MUST be ONLY the JSON object above, nothing else
- Do NOT add any text before or after the JSON
- Return ONLY valid JSON, no markdown formatting"""
        
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
                logger.error("Failed to extract JSON from LLM response")
                logger.debug(f"Raw response (first 500 chars): {response_text[:500]}")
                return {
                    "success": False,
                    "error": "No valid JSON found in response",
                    "raw_response": response_text[:1000]  # Limit to first 1000 chars
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
        
        # Try direct JSON parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object using bracket matching
        # Look for outermost { ... } pair
        start_idx = text.find('{')
        if start_idx == -1:
            logger.warning("No opening brace found in response")
            return None
        
        # Match brackets to find the complete JSON
        bracket_count = 0
        in_string = False
        escape_next = False
        end_idx = -1
        
        for i in range(start_idx, len(text)):
            char = text[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    bracket_count += 1
                elif char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        end_idx = i + 1
                        break
        
        if end_idx == -1:
            logger.warning("Could not find matching closing brace")
            return None
        
        json_str = text[start_idx:end_idx]
        
        try:
            data = json.loads(json_str)
            if "pipeline" in data:
                logger.info("Successfully extracted JSON with 'pipeline' key")
                return data
            else:
                logger.warning("Extracted JSON but no 'pipeline' key found")
                return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse extracted JSON: {e}")
            logger.debug(f"Attempted to parse: {json_str[:200]}...")
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
            table.get("name").lower()  # Convert to lowercase for case-insensitive matching
            for table in self.database.get("tables", [])
            if table.get("name")
        )
        
        # Build detailed table schema map
        self.table_schemas = {}
        for table in self.database.get("tables", []):
            table_name = table.get("name")
            if table_name:
                # Store with lowercase key for case-insensitive lookup
                self.table_schemas[table_name.lower()] = {
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
        
        # Track tables created within this pipeline
        created_tables = set()
        
        for step in pipeline:
            step_number = step.get("step_number", 0)
            step_type = step.get("type", "")
            content = step.get("content", "")
            
            if step_type == "bash":
                bash_errors, bash_warnings = self._validate_bash_step(step_number, content)
                errors.extend(bash_errors)
                warnings.extend(bash_warnings)
            
            elif step_type == "sql":
                # Extract tables created in this step before validation
                create_pattern = r'\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)'
                for match in re.finditer(create_pattern, content.upper()):
                    created_tables.add(match.group(1).lower())  # Store lowercase for case-insensitive matching
                
                sql_errors, sql_warnings = self._validate_sql_step(step_number, content, created_tables)
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
        
        # Skip shell control structures from whitelist validation
        control_keywords = {"if", "then", "fi", "else", "elif", "do", "done", "while", "for", "{", "}"}
        if primary_command in control_keywords:
            # Still allow file reference checks below
            primary_is_control = True
        else:
            primary_is_control = False
        
        # Check if this is a variable assignment (VAR=value pattern)
        is_variable_assignment = '=' in primary_command and not primary_command.startswith('-')
        
        # Extract actual commands from the content for validation
        # This handles: variable assignments, command substitutions, pipes, etc.
        commands_to_validate = self._extract_commands_from_bash(content)
        
        # Check if commands are whitelisted - BUT ONLY WARN, DON'T ERROR
        if not primary_is_control and not is_variable_assignment:
            for cmd in commands_to_validate:
                if cmd not in self.allowed_commands and cmd not in control_keywords:
                    # Blacklist dangerous commands - these should be ERRORS
                    dangerous_commands = {'rm', 'rmdir', 'dd', 'mkfs', 'fdisk', 'format', 
                                         'shutdown', 'reboot', 'halt', 'poweroff', 'init',
                                         'kill', 'killall', 'pkill', 'wget', 'curl'}
                    
                    if cmd in dangerous_commands:
                        warnings.append({
                            "step_number": step_number,
                            "warning_type": "dangerous_command",
                            "message": f"Potentially dangerous command '{cmd}' detected (allowed in sandbox)"
                        })
                    else:
                        # Non-whitelisted but not dangerous - just log as info
                        logger.info(f"Step {step_number}: Non-whitelisted command '{cmd}' (allowed)")
                    break  # Only report first violation to avoid spam
        
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
    
    def _validate_sql_step(self, step_number: int, content: str, created_tables: set = None) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate SQL step
        
        Args:
            step_number: Step number
            content: SQL content
            created_tables: Set of tables created in previous steps within same pipeline
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        if created_tables is None:
            created_tables = set()
        
        content_upper = content.upper()
        
        # Extract table references
        table_refs = self._extract_table_references(content)
        for table_ref in table_refs:
            # Convert to lowercase for case-insensitive comparison
            table_ref_lower = table_ref.lower()
            # Allow if table exists in schema OR was created in this pipeline
            if table_ref_lower not in self.table_names and table_ref_lower not in created_tables:
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
        # More precise SQL patterns with word boundaries
        patterns = [
            r'\bFROM\s+(\w+)',
            r'\bJOIN\s+(\w+)',
            r'\bINSERT\s+INTO\s+(\w+)',
            r'\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)',
            r'\bUPDATE\s+(\w+)',
            r'\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(\w+)',
        ]
        
        table_refs = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            table_refs.extend(matches)
        
        # Filter out common SQL keywords and English words that aren't table names
        sql_keywords = {
            'select', 'from', 'where', 'and', 'or', 'not', 'in', 'is', 'as',
            'on', 'by', 'order', 'group', 'having', 'limit', 'offset',
            'the', 'a', 'an', 'to', 'of', 'for', 'with', 'into', 'table',
            'values', 'set', 'if', 'exists', 'null', 'true', 'false'
        }
        
        # Convert to lowercase and filter
        filtered_refs = []
        for ref in table_refs:
            ref_lower = ref.lower()
            if ref_lower not in sql_keywords:
                filtered_refs.append(ref_lower)
        
        # Filter out common function calls that are not real tables
        function_like = {
            "read_json",
            "read_csv",
            "read_parquet",
            "generate_series",
            "values"
        }
        
        final_refs = []
        for ref in filtered_refs:
            if ref.lower() not in function_like:
                final_refs.append(ref)
        
        return list(set(final_refs))
    
    def _extract_commands_from_bash(self, content: str) -> List[str]:
        """
        Extract all actual commands from bash content, handling:
        - Variable assignments (VAR=value)
        - Command substitutions $(cmd) and `cmd`
        - Pipes (cmd1 | cmd2)
        - Compound commands (cmd1; cmd2; cmd3)
        
        Args:
            content: Bash command content
            
        Returns:
            List of base commands found
        """
        commands = []
        
        # Remove quoted strings first to avoid parsing their contents
        content_no_quotes = re.sub(r'"[^"]*"', '', content)
        content_no_quotes = re.sub(r"'[^']*'", '', content_no_quotes)
        
        # Remove variable assignments (everything before = on each line/statement)
        # Pattern: WORD=... -> extract what comes after =
        content_cleaned = re.sub(r'\b\w+=[^\s;|&]+', '', content_no_quotes)
        
        # Extract commands from command substitutions $(...)  
        cmd_sub_pattern = r'\$\(([^)]+)\)'
        for match in re.finditer(cmd_sub_pattern, content):
            sub_content = match.group(1)
            # Recursively extract from substitution
            commands.extend(self._extract_simple_commands(sub_content))
        
        # Extract commands from backtick substitutions `...`
        backtick_pattern = r'`([^`]+)`'
        for match in re.finditer(backtick_pattern, content):
            sub_content = match.group(1)
            commands.extend(self._extract_simple_commands(sub_content))
        
        # Extract simple commands from cleaned content
        commands.extend(self._extract_simple_commands(content_cleaned))
        
        # Also check the original first token if not a variable assignment
        tokens = content.strip().split()
        if tokens and '=' not in tokens[0]:
            first_token = tokens[0]
            # Clean quotes from first token
            first_token = re.sub(r'["\']', '', first_token)
            if first_token:
                commands.append(first_token)
        
        # Filter out empty strings, quotes, and special characters
        commands = [cmd for cmd in commands if cmd and cmd not in ['"', "'", '', ' ']]
        
        return list(set(commands))
    
    def _extract_simple_commands(self, content: str) -> List[str]:
        """
        Extract simple command names from bash content
        
        Args:
            content: Bash content
            
        Returns:
            List of command names
        """
        commands = []
        
        # Remove quoted strings to avoid parsing their contents
        content_cleaned = re.sub(r'"[^"]*"', '', content)
        content_cleaned = re.sub(r"'[^']*'", '', content_cleaned)
        
        # Remove shebangs (#!/bin/bash, etc.)
        content_cleaned = re.sub(r'^#!.*$', '', content_cleaned, flags=re.MULTILINE)
        
        # Remove redirections (e.g., 2>/dev/null, >&2, etc.)
        content_cleaned = re.sub(r'\d*>[>&]?\S*', '', content_cleaned)
        content_cleaned = re.sub(r'<\S*', '', content_cleaned)
        
        # Split by common separators: pipes, semicolons, &&, ||
        parts = re.split(r'[|;&]+', content_cleaned)
        
        for part in parts:
            tokens = part.strip().split()
            if tokens:
                # First token is the command
                cmd = tokens[0]
                # Skip comments
                if cmd.startswith('#'):
                    continue
                # Clean up any redirections, quotes, or special chars
                cmd = re.sub(r'[<>()\[\]{}"\'/]', '', cmd)
                # Filter out empty strings, flags, single characters, and non-alphanumeric
                if cmd and not cmd.startswith('-') and len(cmd) > 1 and cmd.replace('_', '').isalnum():
                    commands.append(cmd)
        
        return commands


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
                error_details = validation_result.get("errors", [])
                logger.error(f"Pipeline validation failed with {len(error_details)} errors")
                for err in error_details:
                    logger.error(f"  - Step {err.get('step_number', '?')}: {err.get('message', '')}")
                
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
