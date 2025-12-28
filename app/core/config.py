"""
Configuration management for QueryForge application
"""
import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Database configuration
    DATABASE_URL: str = Field(
        default="sqlite:///./queryforge.db",
        description="SQLite database file path"
    )
    
    # Gemini API configuration
    GEMINI_API_KEY: str = Field(
        default="",
        description="Google Gemini API authentication key"
    )
    
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model version to use"
    )
    
    GEMINI_TIMEOUT_SECONDS: int = Field(
        default=3,
        description="Maximum wait time for Gemini API response in seconds"
    )
    
    GEMINI_MAX_RETRIES: int = Field(
        default=2,
        description="Number of retry attempts for Gemini API failures"
    )
    
    GEMINI_RETRY_DELAY_SECONDS: float = Field(
        default=0.5,
        description="Delay between retry attempts in seconds"
    )
    
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(
        default=8192,
        description="Maximum tokens allowed in Gemini responses"
    )
    
    # Directory paths
    DATA_DIRECTORY: str = Field(
        default="./data",
        description="Root path for data files"
    )
    
    SANDBOX_DIRECTORY: str = Field(
        default="./sandbox",
        description="Isolated execution workspace"
    )
    
    SYNTHESIZER_OUTPUT_DIR: str = Field(
        default="./sandbox/pipelines",
        description="Directory for synthesized pipeline scripts"
    )
    
    SCRIPT_FILE_PERMISSIONS: str = Field(
        default="0755",
        description="File permissions for generated scripts (octal format)"
    )
    
    ENABLE_SYNTAX_VALIDATION: bool = Field(
        default=True,
        description="Enable syntax validation for generated scripts"
    )
    
    # Pipeline execution configuration
    MAX_REPAIR_ATTEMPTS: int = Field(
        default=3,
        description="Maximum number of repair attempts per pipeline"
    )
    
    SANDBOX_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Timeout in seconds for each pipeline step execution"
    )
    
    # Allowed bash commands (whitelist)
    ALLOWED_BASH_COMMANDS: List[str] = Field(
        default=["awk", "sed", "cp", "mv", "rm", "curl", "cat", "grep", "cut", "sort", "uniq", "head", "tail", "wc", "echo", "[", "test", "set"],
        description="Whitelisted shell commands for sandbox execution"
    )
    
    # Application settings
    APP_NAME: str = Field(
        default="QueryForge",
        description="Application name"
    )
    
    APP_VERSION: str = Field(
        default="0.1.0",
        description="Application version"
    )
    
    DEBUG: bool = Field(
        default=False,
        description="Debug mode flag"
    )
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get application settings instance
    
    Returns:
        Settings: Application configuration
    """
    return settings


def validate_configuration() -> bool:
    """
    Validate that all required configuration parameters are set
    
    Returns:
        bool: True if configuration is valid, raises exception otherwise
        
    Raises:
        ValueError: If required configuration is missing
    """
    # Check for required Gemini API key
    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is required. Please set it in .env file or environment variables."
        )
    
    # Validate directories exist or can be created
    for directory in [settings.DATA_DIRECTORY, settings.SANDBOX_DIRECTORY]:
        os.makedirs(directory, exist_ok=True)
    
    # Validate numeric settings
    if settings.MAX_REPAIR_ATTEMPTS < 1 or settings.MAX_REPAIR_ATTEMPTS > 10:
        raise ValueError("MAX_REPAIR_ATTEMPTS must be between 1 and 10")
    
    if settings.SANDBOX_TIMEOUT_SECONDS < 1:
        raise ValueError("SANDBOX_TIMEOUT_SECONDS must be at least 1 second")
    
    return True
