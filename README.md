# QueryForge

Automated Data Pipeline Generation System

## Overview

QueryForge is an LLM-powered system that converts natural-language requests into validated, executable hybrid Bash+SQL pipelines with automatic error detection and repair capabilities.

## Features

- Natural language to pipeline generation
- Database schema and filesystem introspection (MCP)
- Sandbox execution with safety constraints
- Automatic error detection and repair loop
- Safe production deployment with full traceability

## Setup

1. Create virtual environment:
```bash
python -m venv venv
```

2. Activate virtual environment:
```bash
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
.\venv\Scripts\activate.bat

# Linux/Mac
source venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create `.env` file with required configuration:
```
DATABASE_URL=sqlite:///./queryforge.db
GEMINI_API_KEY=your_api_key_here
DATA_DIRECTORY=./data
SANDBOX_DIRECTORY=./sandbox
MAX_REPAIR_ATTEMPTS=3
SANDBOX_TIMEOUT_SECONDS=10
```

5. Initialize database:
```bash
python -m app.core.database
```

6. Run the application:
```bash
uvicorn app.main:app --reload
```

## Development

Run tests:
```bash
pytest tests/
```

## Technology Stack

- FastAPI 0.104+
- SQLite 3.40+
- Google Gemini API
- Python 3.10+

## Project Structure

```
queryforge/
├── app/                    # Application source code
│   ├── api/               # API routes
│   ├── core/              # Core configuration
│   ├── models/            # Pydantic schemas
│   ├── services/          # Business logic
│   └── utils/             # Utilities
├── data/                  # Test data files
├── sandbox/               # Sandbox execution workspace
├── tests/                 # Test suite
└── requirements.txt       # Dependencies
```

## License

MIT
