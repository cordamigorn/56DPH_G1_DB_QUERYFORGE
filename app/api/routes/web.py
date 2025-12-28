"""
Web UI routes for QueryForge
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import os
from pathlib import Path

router = APIRouter()

# Get template directory - go up from web.py to app/ directory, then to templates/
# web.py is at app/api/routes/web.py, so parent.parent.parent gets us to app/
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def read_template(filename: str) -> str:
    """Read HTML template file"""
    filepath = TEMPLATE_DIR / filename
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


@router.get("/", response_class=HTMLResponse)
async def home_page():
    """Serve home page"""
    return read_template("home.html")


@router.get("/pipeline/{pipeline_id}/view", response_class=HTMLResponse)
async def pipeline_detail_page(pipeline_id: int):
    """Serve pipeline detail page"""
    # For now, return a simple page that uses the API
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pipeline #{pipeline_id} - QueryForge</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 10px;
                box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                padding: 40px;
            }}
            
            h1 {{
                color: #333;
                margin-bottom: 20px;
            }}
            
            .back-link {{
                display: inline-block;
                color: #667eea;
                text-decoration: none;
                margin-bottom: 20px;
                font-weight: 600;
            }}
            
            .back-link:hover {{
                text-decoration: underline;
            }}
            
            .info-section {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            
            .info-section strong {{
                color: #333;
            }}
            
            .steps-section {{
                margin-top: 30px;
            }}
            
            .step {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 15px;
                border-left: 4px solid #667eea;
            }}
            
            .step-header {{
                font-weight: 600;
                color: #333;
                margin-bottom: 10px;
            }}
            
            .step-content {{
                font-family: 'Courier New', monospace;
                background: white;
                padding: 10px;
                border-radius: 3px;
                overflow-x: auto;
                white-space: pre-wrap;
            }}
            
            .btn {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
                font-weight: 600;
                cursor: pointer;
                margin-right: 10px;
                text-decoration: none;
                display: inline-block;
            }}
            
            .btn:hover {{
                transform: translateY(-2px);
            }}
            
            .btn-secondary {{
                background: #6c757d;
            }}
            
            .btn-success {{
                background: #28a745;
            }}
            
            .btn-danger {{
                background: #dc3545;
            }}
            
            .status-badge {{
                display: inline-block;
                padding: 6px 15px;
                border-radius: 12px;
                font-size: 0.9em;
                font-weight: 600;
            }}
            
            .status-pending {{
                background: #e0e0e0;
                color: #666;
            }}
            
            .status-sandbox_success, .status-success {{
                background: #d4edda;
                color: #155724;
            }}
            
            .status-sandbox_failed, .status-failed {{
                background: #f8d7da;
                color: #721c24;
            }}
            
            .status-committed {{
                background: #d1ecf1;
                color: #0c5460;
            }}
            
            .loading {{
                text-align: center;
                padding: 40px;
                color: #666;
            }}
            
            .spinner {{
                display: inline-block;
                width: 40px;
                height: 40px;
                border: 4px solid rgba(102, 126, 234, .3);
                border-radius: 50%;
                border-top-color: #667eea;
                animation: spin 1s ease-in-out infinite;
            }}
            
            @keyframes spin {{
                to {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/web/" class="back-link">← Back to Home</a>
            
            <h1>Pipeline #{pipeline_id}</h1>
            
            <div id="content">
                <div class="loading">
                    <div class="spinner"></div>
                    <p>Loading pipeline details...</p>
                </div>
            </div>
        </div>
        
        <script>
            const pipelineId = {pipeline_id};
            
            async function loadPipeline() {{
                try {{
                    const response = await fetch(`/pipeline/${{pipelineId}}/logs`);
                    const data = await response.json();
                    
                    if (data.success) {{
                        const content = document.getElementById('content');
                        content.innerHTML = `
                            <div class="info-section">
                                <p><strong>Prompt:</strong> ${{data.original_prompt}}</p>
                                <p><strong>Status:</strong> <span class="status-badge status-${{data.overall_status}}">${{data.overall_status}}</span></p>
                                <p><strong>Execution Logs:</strong> ${{data.execution_logs.length}}</p>
                                <p><strong>Repair Attempts:</strong> ${{data.repair_logs.length}}</p>
                            </div>
                            
                            <div style="margin-top: 20px;">
                                <button class="btn" onclick="runPipeline()">▶ Run in Sandbox</button>
                                <button class="btn btn-secondary" onclick="repairPipeline()">🔧 Repair</button>
                                <button class="btn btn-success" onclick="commitPipeline()">✓ Commit to Production</button>
                                <button class="btn btn-danger" onclick="viewLogs()">📋 View Full Logs</button>
                            </div>
                            
                            <div class="steps-section">
                                <h2>Pipeline Steps</h2>
                                ${{data.final_pipeline.map((step, idx) => `
                                    <div class="step">
                                        <div class="step-header">Step ${{step.step_number}}: [${{step.type}}]</div>
                                        <div class="step-content">${{step.content}}</div>
                                    </div>
                                `).join('')}}
                            </div>
                        `;
                    }} else {{
                        document.getElementById('content').innerHTML = `
                            <div class="info-section" style="background: #f8d7da; border: 2px solid #f5c6cb;">
                                <strong>Error:</strong> ${{data.error || 'Failed to load pipeline'}}
                            </div>
                        `;
                    }}
                }} catch (error) {{
                    document.getElementById('content').innerHTML = `
                        <div class="info-section" style="background: #f8d7da; border: 2px solid #f5c6cb;">
                            <strong>Error:</strong> ${{error.message}}
                        </div>
                    `;
                }}
            }}
            
            async function runPipeline() {{
                if (!confirm('Run this pipeline in sandbox environment?')) return;
                
                try {{
                    const response = await fetch(`/pipeline/run/${{pipelineId}}`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ run_mode: 'sandbox' }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        alert('✓ Pipeline executed successfully!');
                        location.reload();
                    }} else {{
                        alert('✗ Execution failed: ' + (data.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('✗ Error: ' + error.message);
                }}
            }}
            
            async function repairPipeline() {{
                if (!confirm('Attempt automatic repair of this pipeline?')) return;
                
                try {{
                    const response = await fetch(`/pipeline/repair/${{pipelineId}}`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ max_attempts: 3, auto_retry: true }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        alert(`✓ Repair completed! Status: ${{data.current_status}}`);
                        location.reload();
                    }} else {{
                        alert('✗ Repair failed: ' + (data.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('✗ Error: ' + error.message);
                }}
            }}
            
            async function commitPipeline() {{
                if (!confirm('Commit this pipeline to production? This will apply all changes to the real database and filesystem.')) return;
                
                try {{
                    const response = await fetch(`/pipeline/commit/${{pipelineId}}`, {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ force_commit: false, create_backup: true }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        alert(`✓ Pipeline committed successfully! Snapshot ID: ${{data.snapshot_id}}`);
                        location.reload();
                    }} else {{
                        alert('✗ Commit failed: ' + (data.error || 'Unknown error'));
                    }}
                }} catch (error) {{
                    alert('✗ Error: ' + error.message);
                }}
            }}
            
            function viewLogs() {{
                // Open logs in new tab (could be enhanced with a modal)
                window.open(`/pipeline/${{pipelineId}}/logs`, '_blank');
            }}
            
            // Load pipeline on page load
            loadPipeline();
        </script>
    </body>
    </html>
    """
