"""
Basit test - API key olmadan çalışan demo
"""
import asyncio
import json
from app.services.llm import PromptBuilder, ResponseParser, PipelineValidator
from app.services.synthesizer import PipelineSynthesizer
from app.services.mcp import MCPContextManager


async def demo_without_api():
    """API key olmadan özellikleri test et"""
    
    print("\n" + "="*80)
    print("QueryForge Demo - API Key Gerektirmeyen Test")
    print("="*80)
    
    # 1. MCP Context Test
    print("\n1️⃣  MCP Context Manager Testi")
    print("-" * 40)
    
    mcp = MCPContextManager()
    context = await mcp.get_full_context_async()
    
    print(f"✓ Veritabanı tabloları: {context['metadata']['database_table_count']}")
    print(f"✓ Dosya sistemi dosyaları: {context['metadata']['filesystem_file_count']}")
    
    print("\nMevcut Tablolar:")
    for table in context['database']['tables']:
        cols = ", ".join([f"{c['name']} ({c['type']})" for c in table['columns'][:3]])
        print(f"  • {table['name']}: {cols}...")
    
    print("\nMevcut Dosyalar:")
    for file in context['filesystem']['files']:
        print(f"  • {file['path']} ({file['type']})")
    
    # 2. Prompt Builder Test
    print("\n2️⃣  Prompt Builder Testi")
    print("-" * 40)
    
    user_request = "inventory.json dosyasını products tablosuna aktar"
    prompt = PromptBuilder.build_complete_prompt(user_request, context)
    
    print(f"✓ Kullanıcı isteği: '{user_request}'")
    print(f"✓ Oluşturulan prompt uzunluğu: {len(prompt)} karakter")
    print(f"\nPrompt içeriği (ilk 300 karakter):")
    print(prompt[:300] + "...")
    
    # 3. Response Parser Test (simüle edilmiş LLM yanıtı)
    print("\n3️⃣  Response Parser Testi")
    print("-" * 40)
    
    # Simüle edilmiş LLM yanıtı
    simulated_response = json.dumps({
        "pipeline": [
            {
                "step_number": 1,
                "type": "bash",
                "content": "cat data/inventory.json",
                "description": "inventory.json dosyasını göster"
            },
            {
                "step_number": 2,
                "type": "sql",
                "content": "SELECT * FROM Pipelines LIMIT 5",
                "description": "Pipelines tablosundan ilk 5 kaydı getir"
            }
        ]
    })
    
    parse_result = ResponseParser.parse_response(simulated_response)
    
    if parse_result["success"]:
        print(f"✓ Parsing başarılı!")
        print(f"✓ {len(parse_result['pipeline'])} adım bulundu")
        
        for step in parse_result['pipeline']:
            print(f"\n  Adım {step['step_number']} ({step['type'].upper()}):")
            print(f"    {step['content']}")
    else:
        print(f"✗ Parsing hatası: {parse_result['error']}")
    
    # 4. Pipeline Validator Test
    print("\n4️⃣  Pipeline Validator Testi")
    print("-" * 40)
    
    validator = PipelineValidator(context)
    validation_result = validator.validate_pipeline(parse_result['pipeline'])
    
    if validation_result["is_valid"]:
        print("✓ Pipeline geçerli!")
    else:
        print("⚠ Pipeline hataları bulundu:")
        for error in validation_result["errors"]:
            print(f"  • {error['message']}")
    
    if validation_result.get("warnings"):
        print("\n⚠ Uyarılar:")
        for warning in validation_result["warnings"]:
            print(f"  • {warning['message']}")
    
    # 5. Synthesizer Test
    print("\n5️⃣  Script Synthesizer Testi")
    print("-" * 40)
    
    synthesizer = PipelineSynthesizer(output_directory="./test_output")
    synth_result = synthesizer.synthesize_pipeline(
        pipeline_id=999,
        pipeline=parse_result['pipeline']
    )
    
    if synth_result["success"]:
        print(f"✓ Script'ler oluşturuldu!")
        print(f"✓ Çıktı dizini: {synth_result['output_directory']}")
        print(f"✓ Toplam script: {synth_result['total_scripts']}")
        
        print("\nOluşturulan dosyalar:")
        for script in synth_result['scripts']:
            print(f"  • {script['filename']} ({script['size_bytes']} byte)")
            
            # İlk script'in içeriğini göster
            if script['step_number'] == 1:
                print(f"\n  {script['filename']} içeriği:")
                with open(script['path'], 'r', encoding='utf-8') as f:
                    lines = f.readlines()[:15]
                    for line in lines:
                        print(f"    {line.rstrip()}")
                    print(f"    ... (toplam {len(f.readlines()) + 15} satır)")
    else:
        print(f"✗ Synthesis hatası: {synth_result['error']}")
    
    # Özet
    print("\n" + "="*80)
    print("✅ DEMO TAMAMLANDI!")
    print("="*80)
    print("\nTest edilen özellikler:")
    print("  ✓ MCP Context Manager - Veritabanı ve dosya sistemi analizi")
    print("  ✓ Prompt Builder - Gemini için prompt oluşturma")
    print("  ✓ Response Parser - LLM yanıtlarını parse etme")
    print("  ✓ Pipeline Validator - Pipeline'ı doğrulama")
    print("  ✓ Script Synthesizer - Bash ve SQL script'leri oluşturma")
    
    print("\nNot: Gerçek LLM API çağrısı yapmadık (API key gerekmedi)")
    print("      Gerçek API ile test için .env dosyasına GEMINI_API_KEY ekleyin")
    print("="*80)


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║              QueryForge - Basit Demo                          ║
    ║                                                                ║
    ║  Bu demo API key gerektirmeden özellikleri test eder          ║
    ║  Simüle edilmiş LLM yanıtları kullanılır                     ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        asyncio.run(demo_without_api())
    except Exception as e:
        print(f"\n✗ Hata: {e}")
        import traceback
        traceback.print_exc()
