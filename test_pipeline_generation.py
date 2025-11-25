"""
Test script for Phase 2 & 3 - Pipeline Generation and Synthesis
This script demonstrates how to use the implemented features
"""
import asyncio
import json
from app.services.llm import LLMPipelineService
from app.services.synthesizer import PipelineSynthesizer
from app.services.mcp import MCPContextManager
from app.core.database import init_database


async def test_pipeline_generation():
    """Test complete pipeline generation and synthesis"""
    
    print("=" * 80)
    print("QueryForge - Pipeline Generation Test")
    print("=" * 80)
    
    # Initialize database
    print("\n1. Initializing database...")
    try:
        init_database()
        print("   ✓ Database initialized")
    except Exception as e:
        print(f"   ✗ Database initialization failed: {e}")
        return
    
    # Get MCP context
    print("\n2. Getting MCP context (database + filesystem)...")
    try:
        mcp = MCPContextManager()
        context = await mcp.get_full_context_async()
        
        print(f"   ✓ Found {context['metadata']['database_table_count']} database tables")
        print(f"   ✓ Found {context['metadata']['filesystem_file_count']} files")
        
        # Show available resources
        print("\n   Available Tables:")
        for table in context['database']['tables']:
            print(f"      - {table['name']}")
        
        print("\n   Available Files:")
        for file in context['filesystem']['files']:
            print(f"      - {file['path']} ({file['type']})")
            
    except Exception as e:
        print(f"   ✗ MCP context extraction failed: {e}")
        return
    
    # Get user prompt
    print("\n" + "=" * 80)
    print("Enter your pipeline request in natural language")
    print("Examples:")
    print("  - 'Show me the contents of inventory.json'")
    print("  - 'List all products from the database'")
    print("  - 'Show me the contents of customers.csv'")
    print("=" * 80)
    
    user_prompt = input("\nYour request: ").strip()
    
    if not user_prompt:
        print("No prompt provided. Using default...")
        user_prompt = "Show me the contents of inventory.json"
    
    print(f"\nProcessing request: '{user_prompt}'")
    
    # Generate pipeline
    print("\n3. Generating pipeline with LLM...")
    try:
        llm_service = LLMPipelineService()
        gen_result = await llm_service.generate_pipeline(
            user_prompt=user_prompt,
            user_id=1,
            mcp_context=context
        )
        
        if not gen_result["success"]:
            print(f"   ✗ Pipeline generation failed!")
            print(f"   Error: {gen_result.get('error', 'Unknown error')}")
            if 'validation_errors' in gen_result:
                print(f"   Validation errors:")
                for err in gen_result['validation_errors']:
                    print(f"      - {err}")
            return
        
        print(f"   ✓ Pipeline generated successfully!")
        print(f"   Pipeline ID: {gen_result['pipeline_id']}")
        print(f"   Number of steps: {len(gen_result['pipeline'])}")
        print(f"   Generation time: {gen_result['elapsed_time']:.2f}s")
        
        # Show pipeline steps
        print("\n   Generated Pipeline Steps:")
        for step in gen_result['pipeline']:
            print(f"\n   Step {step['step_number']} ({step['type'].upper()}):")
            print(f"      {step['content']}")
            if 'description' in step:
                print(f"      Description: {step['description']}")
        
        if gen_result.get('warnings'):
            print("\n   ⚠ Warnings:")
            for warning in gen_result['warnings']:
                print(f"      - {warning}")
        
        pipeline_id = gen_result['pipeline_id']
        pipeline_steps = gen_result['pipeline']
        
    except Exception as e:
        print(f"   ✗ Pipeline generation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Synthesize scripts
    print("\n4. Synthesizing executable scripts...")
    try:
        synthesizer = PipelineSynthesizer()
        synth_result = synthesizer.synthesize_pipeline(
            pipeline_id=pipeline_id,
            pipeline=pipeline_steps
        )
        
        if not synth_result["success"]:
            print(f"   ✗ Script synthesis failed!")
            print(f"   Error: {synth_result.get('error', 'Unknown error')}")
            return
        
        print(f"   ✓ Scripts synthesized successfully!")
        print(f"   Output directory: {synth_result['output_directory']}")
        print(f"   Total scripts: {synth_result['total_scripts']}")
        
        print("\n   Generated Script Files:")
        for script in synth_result['scripts']:
            print(f"      - {script['filename']} ({script['size_bytes']} bytes)")
        
        print(f"\n   Manifest file: {synth_result['manifest_path']}")
        
        # Show script contents
        print("\n5. Script Contents:")
        for script in synth_result['scripts']:
            print(f"\n   --- {script['filename']} ---")
            try:
                with open(script['path'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Show first 20 lines
                    lines = content.split('\n')[:20]
                    for line in lines:
                        print(f"   {line}")
                    if len(content.split('\n')) > 20:
                        print(f"   ... ({len(content.split('\n')) - 20} more lines)")
            except Exception as e:
                print(f"   Error reading file: {e}")
        
        # Summary
        print("\n" + "=" * 80)
        print("SUCCESS! Pipeline Created and Scripts Generated")
        print("=" * 80)
        print(f"Pipeline ID: {pipeline_id}")
        print(f"Scripts location: {synth_result['output_directory']}")
        print("\nYou can find the generated scripts in the output directory.")
        print("Note: Scripts are generated but NOT executed yet (Phase 4 pending).")
        print("=" * 80)
        
    except Exception as e:
        print(f"   ✗ Script synthesis failed: {e}")
        import traceback
        traceback.print_exc()
        return


async def test_simple_example():
    """Run a simple pre-defined example"""
    
    print("\n" + "=" * 80)
    print("Running Simple Example: List inventory file")
    print("=" * 80)
    
    # Initialize database
    init_database()
    
    # Get context
    mcp = MCPContextManager()
    context = await mcp.get_full_context_async()
    
    # Generate pipeline
    llm_service = LLMPipelineService()
    result = await llm_service.generate_pipeline(
        user_prompt="Show me the contents of inventory.json using cat command",
        user_id=1,
        mcp_context=context
    )
    
    if result["success"]:
        print(f"✓ Pipeline generated with {len(result['pipeline'])} steps")
        
        # Synthesize
        synthesizer = PipelineSynthesizer()
        synth_result = synthesizer.synthesize_pipeline(
            pipeline_id=result['pipeline_id'],
            pipeline=result['pipeline']
        )
        
        if synth_result["success"]:
            print(f"✓ Scripts created in: {synth_result['output_directory']}")
    else:
        print(f"✗ Failed: {result.get('error')}")


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║         QueryForge - Phase 2 & 3 Test Script                  ║
    ║                                                                ║
    ║  This script tests:                                            ║
    ║  ✓ LLM Pipeline Generation (Phase 2)                          ║
    ║  ✓ Bash/SQL Script Synthesis (Phase 3)                        ║
    ║                                                                ║
    ║  Prerequisites:                                                ║
    ║  1. Set GEMINI_API_KEY in .env file                           ║
    ║  2. Ensure database is accessible                             ║
    ║  3. Ensure data/ directory exists with files                  ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    print("\nChoose an option:")
    print("1. Interactive mode (enter your own prompt)")
    print("2. Simple example (pre-defined prompt)")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    try:
        if choice == "2":
            asyncio.run(test_simple_example())
        else:
            asyncio.run(test_pipeline_generation())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
