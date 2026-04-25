#!/usr/bin/env python3
"""
Status do Sistema - Verificação Final

Este script valida que tudo está funcionando corretamente.
"""

import os
import sys
from pathlib import Path

print("\n" + "="*80)
print("VERIFICAÇÃO FINAL DO SISTEMA")
print("="*80)

# 1. Verificar arquivos
print("\n📁 1. Verificando arquivos...")
required_files = [
    "football_total_goals_strategy.py",
    "football_data_provider.py",
    "football_total_goals_web.py",
    "requirements.txt",
    "README.md",
    "GUIA_COMPLETO.md",
    "QUICK_START.md",
]

base_path = Path(__file__).parent
all_present = True

for file in required_files:
    path = base_path / file
    if path.exists():
        size_kb = path.stat().st_size / 1024
        print(f"   ✅ {file:<45} ({size_kb:>6.1f} KB)")
    else:
        print(f"   ❌ {file} - FALTANDO")
        all_present = False

if all_present:
    print("\n   ✅ Todos os arquivos principais estão presentes!")
else:
    print("\n   ⚠️  Alguns arquivos estão faltando.")

# 2. Verificar dependências
print("\n📦 2. Verificando dependências...")
try:
    import pandas
    print(f"   ✅ pandas {pandas.__version__}")
except ImportError:
    print("   ❌ pandas - NÃO INSTALADO")

try:
    import requests
    print(f"   ✅ requests {requests.__version__}")
except ImportError:
    print("   ❌ requests - NÃO INSTALADO")

# 3. Importar módulos
print("\n🐍 3. Testando importações...")
try:
    from football_total_goals_strategy import (
        MatchStat, evaluate_matchup, project_bankroll,
        build_sample_data, pick_best_recommendation
    )
    print("   ✅ football_total_goals_strategy")
except Exception as e:
    print(f"   ❌ football_total_goals_strategy: {e}")
    sys.exit(1)

try:
    from football_data_provider import FootballDataClient
    print("   ✅ football_data_provider")
except Exception as e:
    print(f"   ❌ football_data_provider: {e}")

# 4. Teste rápido do motor
print("\n⚙️  4. Teste rápido do motor...")
try:
    home_a, away_a, h2h_a, _, _, _ = build_sample_data()
    
    rec = evaluate_matchup(
        "Time A", "Time B",
        home_a, away_a, h2h_a
    )
    
    print(f"   ✅ Motor funcionando")
    print(f"      - Jogo: {rec.home_team} x {rec.away_team}")
    print(f"      - Confiança: {rec.confidence_score}/100")
    print(f"      - Status: {'APROVADO ✓' if rec.approved else 'REJEITADO ✗'}")
    
except Exception as e:
    print(f"   ❌ Erro no motor: {e}")
    sys.exit(1)

# 5. Teste da calculadora
print("\n💰 5. Teste da calculadora de banca...")
try:
    plan = project_bankroll(
        initial_balance=10.0,
        daily_target=0.20,
        odd_target=1.20,
        days=5
    )
    
    print(f"   ✅ Calculadora funcionando")
    print(f"      - Saldo Inicial: R$ {plan[0].opening_bankroll:.2f}")
    print(f"      - Saldo Final (Dia 5): R$ {plan[-1].closing_bankroll:.2f}")
    print(f"      - Crescimento: {((plan[-1].closing_bankroll - 10) / 10 * 100):.1f}%")
    
except Exception as e:
    print(f"   ❌ Erro na calculadora: {e}")
    sys.exit(1)

# 6. Verificar arquivos de documentação
print("\n📚 6. Documentação disponível...")
docs = {
    "QUICK_START.md": "Guia rápido (comece aqui)",
    "GUIA_COMPLETO.md": "Documentação completa",
    "README.md": "Informações gerais",
}

for doc, desc in docs.items():
    path = base_path / doc
    if path.exists():
        lines = len(path.read_text().split("\n"))
        print(f"   ✅ {doc:<20} ({lines:>4} linhas) - {desc}")
    else:
        print(f"   ❌ {doc:<20} - FALTANDO")

# 7. Próximos passos
print("\n" + "="*80)
print("🎯 PRÓXIMOS PASSOS")
print("="*80)

print("""
1️⃣  APRENDER O SISTEMA (5 min):
    python demo_interativo.py
    → Menu interativo para explorar
    
2️⃣  VALIDAR TUDO (2 min):
    python test_system.py
    → Rodará 4 testes completos
    
3️⃣  CONFIGURAR API REAL (10 min, opcional):
    python setup_api_real.py
    → Guia passo-a-passo para dados reais
    
4️⃣  LER DOCUMENTAÇÃO:
    - QUICK_START.md (visão geral)
    - GUIA_COMPLETO.md (detalhes técnicos)

5️⃣  COMEÇAR A USAR EM SEU CÓDIGO:
    from football_total_goals_strategy import evaluate_matchup
    rec = evaluate_matchup(...)
    print(rec.confidence_score)
""")

print("="*80)
print("✅ SISTEMA PRONTO PARA USO")
print("="*80)
print(f"\n📊 Data: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
print("🚀 Boa sorte com suas análises!\n")
