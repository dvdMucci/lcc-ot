#!/usr/bin/env python3
"""
Script de prueba para las validaciones de seguridad del bot
"""
import os
import sys
import tempfile
import time

# Agregar el directorio web al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'web'))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
import django
django.setup()

from bot_security import (
    validate_text, validate_audio_file, validate_audio_duration,
    sanitize_text, get_file_info, log_security_event
)

def test_text_validation():
    """Prueba las validaciones de texto"""
    print("🧪 Probando validaciones de texto...")
    
    # Casos de prueba
    test_cases = [
        # (texto, debería_pasar, descripción)
        ("Hola mundo", True, "Texto normal"),
        ("", False, "Texto vacío"),
        ("A" * 3000, False, "Texto muy largo"),
        ("rm -rf /", False, "Comando malicioso"),
        ("https://malicious.com", False, "URL maliciosa"),
        ("<script>alert('xss')</script>", False, "Script XSS"),
        ("SELECT * FROM users", False, "SQL injection"),
        ("select * from users", False, "SQL injection lowercase"),
        ("🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉", False, "Demasiados emojis"),
        ("palabra palabra palabra palabra palabra", False, "Repetición excesiva"),
        ("Texto normal con acentos: áéíóú", True, "Texto con acentos"),
        ("Número: 123", True, "Texto con números"),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for text, should_pass, description in test_cases:
        is_valid, error = validate_text(text)
        if is_valid == should_pass:
            status = "✅" if is_valid else "❌"
            print(f"  {status} {description}: {text[:50]}...")
            passed += 1
        else:
            print(f"  ❌ {description}: Esperado {should_pass}, obtenido {is_valid}")
            print(f"     Error: {error}")
    
    print(f"📊 Texto: {passed}/{total} pruebas pasaron\n")
    return passed == total

def test_audio_validation():
    """Prueba las validaciones de audio"""
    print("🎵 Probando validaciones de audio...")
    
    # Crear archivos de prueba
    with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as f:
        # Simular archivo OGG válido
        f.write(b'OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00')
        valid_ogg = f.name
    
    with tempfile.NamedTemporaryFile(suffix='.exe', delete=False) as f:
        # Simular archivo ejecutable
        f.write(b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00')
        invalid_exe = f.name
    
    with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
        # Archivo de texto
        f.write(b'This is not an audio file')
        invalid_txt = f.name
    
    test_cases = [
        # (archivo, tamaño, debería_pasar, descripción)
        (valid_ogg, 1024, True, "Archivo OGG válido"),
        (invalid_exe, 1024, False, "Archivo ejecutable"),
        (invalid_txt, 1024, False, "Archivo de texto"),
        ("archivo_inexistente.ogg", 1024, False, "Archivo inexistente"),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for file_path, size, should_pass, description in test_cases:
        is_valid, error = validate_audio_file(file_path, size)
        if is_valid == should_pass:
            status = "✅" if is_valid else "❌"
            print(f"  {status} {description}")
            passed += 1
        else:
            print(f"  ❌ {description}: Esperado {should_pass}, obtenido {is_valid}")
            print(f"     Error: {error}")
    
    # Limpiar archivos temporales
    for file_path in [valid_ogg, invalid_exe, invalid_txt]:
        try:
            os.unlink(file_path)
        except:
            pass
    
    print(f"📊 Audio: {passed}/{total} pruebas pasaron\n")
    return passed == total

def test_duration_validation():
    """Prueba las validaciones de duración"""
    print("⏱️ Probando validaciones de duración...")
    
    test_cases = [
        # (duración, debería_pasar, descripción)
        (30, True, "Duración normal"),
        (600, True, "Duración máxima (10 min)"),
        (601, False, "Duración excede límite"),
        (0, False, "Duración cero"),
        (-1, False, "Duración negativa"),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for duration, should_pass, description in test_cases:
        is_valid, error = validate_audio_duration(duration)
        if is_valid == should_pass:
            status = "✅" if is_valid else "❌"
            print(f"  {status} {description}: {duration}s")
            passed += 1
        else:
            print(f"  ❌ {description}: Esperado {should_pass}, obtenido {is_valid}")
            print(f"     Error: {error}")
    
    print(f"📊 Duración: {passed}/{total} pruebas pasaron\n")
    return passed == total

def test_text_sanitization():
    """Prueba la sanitización de texto"""
    print("🧹 Probando sanitización de texto...")
    
    test_cases = [
        # (texto_original, texto_esperado, descripción)
        ("Hola mundo", "Hola mundo", "Texto normal"),
        ("https://malicious.com", "[URL_REMOVIDA]", "URL removida"),
        ("rm -rf /", "[COMANDO_REMOVIDO] /", "Comando removido"),
        ("Texto con\x00caracteres\x01de\x02control", "Texto concaracteresdecontrol", "Caracteres de control removidos"),
        ("A" * 3000, "A" * 2000 + "...", "Texto truncado"),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for original, expected, description in test_cases:
        sanitized = sanitize_text(original)
        if sanitized == expected:
            print(f"  ✅ {description}")
            passed += 1
        else:
            print(f"  ❌ {description}")
            print(f"     Original: {original[:50]}...")
            print(f"     Esperado: {expected}")
            print(f"     Obtenido: {sanitized}")
    
    print(f"📊 Sanitización: {passed}/{total} pruebas pasaron\n")
    return passed == total

def test_logging():
    """Prueba el sistema de logging"""
    print("📝 Probando sistema de logging...")
    
    try:
        log_security_event("test_event", {
            "test_data": "valor",
            "timestamp": time.time()
        }, user_id=12345)
        print("  ✅ Logging funcionando")
        return True
    except Exception as e:
        print(f"  ❌ Error en logging: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🔒 Iniciando pruebas de seguridad del bot...\n")
    
    tests = [
        test_text_validation,
        test_audio_validation,
        test_duration_validation,
        test_text_sanitization,
        test_logging,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Error en prueba {test.__name__}: {e}")
    
    print("=" * 50)
    print(f"📊 RESULTADO FINAL: {passed}/{total} pruebas pasaron")
    
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron! El sistema de seguridad está funcionando correctamente.")
        return 0
    else:
        print("⚠️ Algunas pruebas fallaron. Revisar las validaciones de seguridad.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
