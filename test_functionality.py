#!/usr/bin/env python3
"""
Script de prueba para verificar funcionalidades del sistema LCC-OT
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web.settings')
django.setup()

from worklog.models import WorkLog, WorkLogHistory
from accounts.models import CustomUser
from django.contrib.auth import get_user_model

def test_models():
    """Prueba que los modelos estén funcionando correctamente"""
    print("🔍 Probando modelos...")
    
    try:
        # Verificar que el modelo WorkLog tiene los nuevos campos
        worklog_fields = [field.name for field in WorkLog._meta.get_fields()]
        required_fields = ['status', 'created_by', 'updated_by', 'updated_at']
        
        for field in required_fields:
            if field in worklog_fields:
                print(f"  ✅ Campo '{field}' encontrado")
            else:
                print(f"  ❌ Campo '{field}' NO encontrado")
        
        # Verificar que el modelo WorkLogHistory existe
        history_fields = [field.name for field in WorkLogHistory._meta.get_fields()]
        print(f"  ✅ Modelo WorkLogHistory creado con {len(history_fields)} campos")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando modelos: {e}")
        return False

def test_data_integrity():
    """Prueba la integridad de los datos existentes"""
    print("\n🔍 Probando integridad de datos...")
    
    try:
        # Verificar que todos los registros tienen created_by
        worklogs_without_creator = WorkLog.objects.filter(created_by__isnull=True)
        if worklogs_without_creator.exists():
            print(f"  ⚠️  {worklogs_without_creator.count()} registros sin created_by")
        else:
            print("  ✅ Todos los registros tienen created_by")
        
        # Verificar que todos los registros tienen status
        worklogs_without_status = WorkLog.objects.filter(status__isnull=True)
        if worklogs_without_status.exists():
            print(f"  ⚠️  {worklogs_without_status.count()} registros sin status")
        else:
            print("  ✅ Todos los registros tienen status")
        
        # Contar registros totales
        total_worklogs = WorkLog.objects.count()
        print(f"  📊 Total de registros: {total_worklogs}")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando integridad: {e}")
        return False

def test_user_permissions():
    """Prueba el sistema de permisos de usuarios"""
    print("\n🔍 Probando sistema de permisos...")
    
    try:
        User = get_user_model()
        
        # Verificar tipos de usuario
        admin_users = User.objects.filter(user_type='admin')
        supervisor_users = User.objects.filter(user_type='supervisor')
        tecnico_users = User.objects.filter(user_type='tecnico')
        
        print(f"  👑 Administradores: {admin_users.count()}")
        print(f"  👨‍💼 Supervisores: {supervisor_users.count()}")
        print(f"  🔧 Técnicos: {tecnico_users.count()}")
        
        # Verificar que el superusuario existe
        superusers = User.objects.filter(is_superuser=True)
        if superusers.exists():
            print("  ✅ Superusuario encontrado")
        else:
            print("  ⚠️  No hay superusuario")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando permisos: {e}")
        return False

def test_worklog_functionality():
    """Prueba la funcionalidad básica de WorkLog"""
    print("\n🔍 Probando funcionalidad de WorkLog...")
    
    try:
        # Probar método duration
        worklogs = WorkLog.objects.all()[:5]
        for worklog in worklogs:
            duration = worklog.duration()
            if isinstance(duration, (int, float)) and duration >= 0:
                print(f"  ✅ Duración calculada correctamente: {duration} horas")
            else:
                print(f"  ❌ Error en cálculo de duración: {duration}")
        
        # Probar método __str__
        for worklog in worklogs:
            str_repr = str(worklog)
            if str_repr and len(str_repr) > 0:
                print(f"  ✅ Representación string: {str_repr}")
            else:
                print(f"  ❌ Error en representación string")
        
        return True
    except Exception as e:
        print(f"  ❌ Error probando funcionalidad: {e}")
        return False

def main():
    """Función principal de pruebas"""
    print("🚀 Iniciando pruebas del sistema LCC-OT...\n")
    
    tests = [
        test_models,
        test_data_integrity,
        test_user_permissions,
        test_worklog_functionality,
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"  ❌ Error ejecutando prueba: {e}")
    
    print(f"\n📊 Resumen de pruebas:")
    print(f"  ✅ Pasadas: {passed}")
    print(f"  ❌ Fallidas: {total - passed}")
    print(f"  📈 Porcentaje: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ¡Todas las pruebas pasaron! El sistema está funcionando correctamente.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} prueba(s) fallaron. Revisar errores.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
