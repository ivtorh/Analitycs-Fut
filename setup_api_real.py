#!/usr/bin/env python3
"""
Guia Prático: Integrando com Dados Reais (football-data.org)

Este script mostra como:
1. Obter uma chave da API
2. Buscar dados reais de times
3. Analisar jogos com dados concretos

IMPORTANTE: Você precisa de uma conta gratuita em https://www.football-data.org
"""

import os
import sys
from typing import Optional

# Importar o cliente de dados reais
from football_data_provider import FootballDataClient, LiveMatchupData
from football_total_goals_strategy import (
    evaluate_matchup,
    format_ticket_suggestion,
    project_bankroll,
    MatchStat,
)


def print_header(title: str):
    """Imprime um cabeçalho formatado."""
    print("\n" + "="*80)
    print(title.center(80))
    print("="*80)


def setup_api_key() -> Optional[str]:
    """
    Guia para configurar a chave da API.
    """
    print_header("PASSO 1: Configurar Chave da API")
    
    print("""
📋 INSTRUÇÕES:

1. Visite: https://www.football-data.org
2. Clique em "Sign Up" (canto superior direito)
3. Crie sua conta (é GRATUITA)
4. Faça login
5. Vá para "My Account" → "API Tokens"
6. Copie seu token

⚠️  IMPORTANTE:
- A conta gratuita permite ~10 requisições por minuto
- Limite mensal de ~100.000 requisições
- Use sempre a mesma chave para dev

""")
    
    existing_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
    if existing_key:
        print(f"✅ Variável de ambiente FOOTBALL_DATA_API_KEY já definida!")
        use_existing = input("Usar essa chave? (S/N): ").strip().upper()
        if use_existing == "S":
            return existing_key
    
    key = input("\nDigite sua chave da API: ").strip()
    
    if not key:
        print("❌ Chave não fornecida.")
        return None
    
    # Salvar no ambiente
    os.environ["FOOTBALL_DATA_API_KEY"] = key
    
    print(f"✅ Chave salva na variável de ambiente.")
    print(f"   Para sessões futuras, defina: export FOOTBALL_DATA_API_KEY='{key}'")
    
    return key


def test_api_connection(api_key: str) -> bool:
    """
    Testa a conexão com a API.
    """
    print_header("PASSO 2: Testar Conexão com API")
    
    try:
        client = FootballDataClient(api_key=api_key)
        
        # Tentar requisição simples
        print("\nTestando conexão... ", end="", flush=True)
        
        # Buscar lista de competições (teste simples)
        competitions = client.competitions()
        
        print("✅ Conexão estabelecida com sucesso!")
        print(f"\n📊 Competições disponíveis encontradas: {len(competitions)}")
        
        # Mostrar algumas competições populares
        popular = {
            "PL": "Premier League (Inglaterra)",
            "PD": "La Liga (Espanha)",
            "BL1": "Bundesliga (Alemanha)",
            "FL1": "Ligue 1 (França)",
            "SA": "Serie A (Itália)",
            "PPL": "Primeira Liga (Portugal)",
            "DED": "Eredivisie (Holanda)",
        }
        
        print("\n🏆 Competições Populares (códigos usados na API):")
        for code, name in popular.items():
            status = "✓" if any(comp.code == code for comp in competitions) if competitions else " "
            print(f"  {status} {code}: {name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        print("\nVerifique:")
        print("  - Sua chave está correta?")
        print("  - Você tem internet?")
        print("  - Respeitou o limite de requisições?")
        return False


def list_competitions(api_key: str):
    """
    Lista as competições disponíveis.
    """
    print_header("PASSO 3: Explorar Competições")
    
    try:
        client = FootballDataClient(api_key=api_key)
        competitions = client.competitions()
        
        if not competitions:
            print("❌ Nenhuma competição encontrada.")
            return
        
        print(f"\n📋 Total de competições: {len(competitions)}\n")
        
        print("Código | Nome")
        print("-" * 60)
        for comp in competitions[:20]:  # Mostrar apenas 20
            print(f"{comp.code:<6} | {comp.name[:50]}")
        
        if len(competitions) > 20:
            print(f"\n... e mais {len(competitions) - 20} competições")
        
        print("\nUse o código (ex: 'PL') para buscar dados em evaluate_matchday.")
        
    except Exception as e:
        print(f"❌ Erro ao listar competições: {e}")


def demo_with_hardcoded_data():
    """
    Demonstra análise sem precisar de API (usando dados simulados melhorados).
    """
    print_header("DEMONSTRAÇÃO: Análise Sem API")
    
    print("""
📌 Como este funcionaria com DADOS REAIS:

1. Você buscaria os últimos 10 jogos de cada time via API
2. Extrairia os gols marcados/sofridos
3. Passaria para evaluate_matchup()
4. Receberia recomendações com dados concretos

SIMULANDO UM JOGO REAL:
""")
    
    # Simular dados reais de times
    print("\n🏟️  Simulando: Real Madrid vs Barcelona\n")
    
    # Real Madrid - padrão típico: bom ataque, boa defesa
    real_madrid = [
        MatchStat(3, 1),  # Vitória 3-1
        MatchStat(2, 0),  # Vitória 2-0
        MatchStat(1, 1),  # Empate 1-1
        MatchStat(3, 2),  # Vitória 3-2
        MatchStat(2, 1),  # Vitória 2-1
        MatchStat(4, 0),  # Goleada 4-0
        MatchStat(2, 1),  # Vitória 2-1
        MatchStat(3, 1),  # Vitória 3-1
        MatchStat(2, 2),  # Empate 2-2
        MatchStat(1, 0),  # Vitória 1-0
    ]
    
    # Barcelona - padrão típico: também bom ataque, defesa sólida
    barcelona = [
        MatchStat(2, 1),  # Vitória 2-1
        MatchStat(1, 0),  # Vitória 1-0
        MatchStat(3, 1),  # Vitória 3-1
        MatchStat(2, 2),  # Empate 2-2
        MatchStat(2, 0),  # Vitória 2-0
        MatchStat(3, 2),  # Vitória 3-2
        MatchStat(1, 1),  # Empate 1-1
        MatchStat(2, 1),  # Vitória 2-1
        MatchStat(4, 1),  # Goleada 4-1
        MatchStat(3, 0),  # Vitória 3-0
    ]
    
    # H2H histórico (últimos 5)
    h2h = [
        MatchStat(3, 1),
        MatchStat(2, 2),
        MatchStat(1, 0),
        MatchStat(2, 1),
        MatchStat(3, 2),
    ]
    
    # Notícias simuladas
    news = [
        "Nenhuma informação de lesões graves reportadas",
        "Ambas equipes com escalações fortes",
        "Clássico equilibrado esperado"
    ]
    
    # Análise
    rec = evaluate_matchup(
        "Real Madrid",
        "Barcelona",
        real_madrid,
        barcelona,
        h2h,
        news_texts=news
    )
    
    # Resultado
    print(f"Jogo: {rec.home_team} x {rec.away_team}")
    print(f"Aprovado: {'✅ SIM' if rec.approved else '❌ NÃO'}")
    print(f"Confiança: {rec.confidence_score}/100")
    print(f"Média de Gols: {rec.combined_avg_goals:.2f}")
    print(f"\nSugestão: {format_ticket_suggestion(rec)}")
    
    if not rec.approved:
        print("\nMotivos de Rejeição:")
        for reason in rec.reasons:
            print(f"  - {reason}")
    
    # Projetar banca
    print("\n" + "-"*80)
    print("💰 Projeção de Banca (5 dias de exemplo)")
    print("-"*80)
    
    bankroll_plan = project_bankroll(
        initial_balance=50.0,
        daily_target=0.20,
        odd_target=rec.suggested_odd,
        days=5
    )
    
    for row in bankroll_plan:
        print(f"Dia {row.day}: R$ {row.opening_bankroll:.2f} → "
              f"R$ {row.closing_bankroll:.2f} (lucro R$ {row.target_profit:.2f})")


def show_next_steps(api_key_working: bool):
    """
    Mostra próximas etapas.
    """
    print_header("PRÓXIMOS PASSOS")
    
    if api_key_working:
        print("""
✅ Sua API está funcionando!

PRÓXIMO:

1. Escolha uma rodada de uma competição
2. Use analyze_matchday_recommendations() para analisar todos os jogos
3. O sistema vai:
   - Buscar os últimos 10 jogos de cada time
   - Buscar o H2H
   - Aplicar todos os filtros
   - Gerar ranking de recomendações

EXEMPLO:

    from football_data_provider import analyze_matchday_recommendations
    from football_total_goals_web import get_api_client
    
    client = get_api_client()
    recommendations = analyze_matchday_recommendations(
        client=client,
        competition_code="PL",  # Premier League
        matchday=15
    )
    
    for rec in sorted(recommendations, key=lambda r: r.confidence_score, reverse=True):
        print(f"{rec.home_team} x {rec.away_team}: {rec.confidence_score}/100")
""")
    
    else:
        print("""
⚠️  API ainda não está funcionando.

OPÇÕES:

1. Verificar sua chave (está ativa no site?)
2. Usar dados simulados para praticar (demo_interativo.py)
3. Voltar e tentar setup novamente

Para usar dados reais depois, basta:
    export FOOTBALL_DATA_API_KEY="sua_chave"
    python seu_script.py
""")
    
    print("""

RECURSOS ADICIONAIS:

- Documentação: https://www.football-data.org/documentation
- GitHub: https://github.com/jokecamp/football-data-api
- Chat: Discord da comunidade

Boa sorte! ⚽📊
""")


def main():
    """Executa o guia completo."""
    
    print("\n🏆 SISTEMA DE ANÁLISE DE FUTEBOL - TOTAL DE GOLS")
    print("Guia de Integração com Dados Reais")
    print("="*80)
    
    # Passo 1: Obter chave
    api_key = setup_api_key()
    
    if not api_key:
        print("\n❌ Sem chave, vou usar dados simulados para demonstração.\n")
        demo_with_hardcoded_data()
        show_next_steps(False)
        return 0
    
    # Passo 2: Testar conexão
    api_works = test_api_connection(api_key)
    
    if not api_works:
        print("\n⚠️  Vou usar dados simulados para demonstração.\n")
        demo_with_hardcoded_data()
        show_next_steps(False)
        return 1
    
    # Passo 3: Listar competições
    list_competitions(api_key)
    
    # Passo 4: Demonstração
    demo_with_hardcoded_data()
    
    # Próximas etapas
    show_next_steps(True)
    
    return 0


if __name__ == "__main__":
    exit(main())
