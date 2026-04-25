#!/usr/bin/env python3
"""
Script de Demonstração Interativa - Sistema de Análise de Futebol Total de Gols

Permite ao usuário entrar dados manualmente, analisar múltiplos jogos e visualizar
recomendações com scoring de confiança.
"""

import os
from football_total_goals_strategy import (
    MatchStat,
    evaluate_matchup,
    project_bankroll,
    pick_best_recommendation,
    rank_recommendations,
    format_ticket_suggestion,
    DEFAULT_DAILY_TARGET,
    DEFAULT_ODD_TARGET,
)

def input_float(prompt: str, default: float = None) -> float:
    """Entrada segura de float."""
    while True:
        try:
            val = input(prompt).strip()
            if val == "" and default is not None:
                return default
            return float(val)
        except ValueError:
            print("❌ Entrada inválida. Digite um número.")

def input_int(prompt: str, default: int = None) -> int:
    """Entrada segura de inteiro."""
    while True:
        try:
            val = input(prompt).strip()
            if val == "" and default is not None:
                return default
            return int(val)
        except ValueError:
            print("❌ Entrada inválida. Digite um número inteiro.")

def input_matches(team_name: str) -> list[MatchStat]:
    """Coleta os últimos 10 jogos de um time."""
    print(f"\n📝 Digite os últimos 10 jogos de {team_name}:")
    print("(Use 0 0 para parar antes de 10, ou 'x' para usar exemplo)")
    
    matches = []
    for i in range(1, 11):
        while True:
            entry = input(f"  Jogo {i} (gols_marcados gols_sofridos): ").strip()
            
            if entry.lower() == 'x':
                # Dados de exemplo
                example_data = [
                    (2, 1), (1, 1), (3, 1), (1, 0), (2, 2),
                    (1, 2), (2, 0), (1, 1), (2, 1), (1, 0)
                ]
                matches = [MatchStat(for_goals, against_goals) for for_goals, against_goals in example_data]
                print(f"  ✓ Dados de exemplo carregados para {team_name}")
                return matches
            
            if entry == "0 0":
                if len(matches) >= 3:  # Mínimo 3 jogos
                    print(f"  ✓ {len(matches)} jogos registrados")
                    return matches
                else:
                    print(f"  ❌ Mínimo 3 jogos. Você tem {len(matches)}.")
                    continue
            
            try:
                parts = entry.split()
                if len(parts) != 2:
                    raise ValueError("Use formato: gols_marcados gols_sofridos")
                for_goals = int(parts[0])
                against_goals = int(parts[1])
                matches.append(MatchStat(for_goals, against_goals))
                break
            except (ValueError, IndexError):
                print("  ❌ Formato inválido. Use: gols_marcados gols_sofridos (ex: 2 1)")
    
    return matches

def input_news_texts() -> list[str]:
    """Coleta notícias/contextos relevantes."""
    print("\n📰 Notícias/Contexto (opcional):")
    print("Digite manchetes relevantes (uma por linha, vazio para pular):")
    
    texts = []
    while True:
        text = input("  > ").strip()
        if not text:
            break
        texts.append(text)
    
    return texts

def demonstrate_system():
    """Demonstração interativa do sistema."""
    print("\n" + "="*80)
    print("SISTEMA DE ANÁLISE DE FUTEBOL - TOTAL DE GOLS")
    print("Demonstração Interativa")
    print("="*80)
    
    print("\n🏠 JOGO 1: Análise Manual")
    print("-" * 80)
    
    home_team = input("\nNome do time da casa: ").strip() or "Time A"
    away_team = input("Nome do time visitante: ").strip() or "Time B"
    
    print(f"\n📊 Coletando dados para {home_team}...")
    home_matches = input_matches(home_team)
    
    print(f"\n📊 Coletando dados para {away_team}...")
    away_matches = input_matches(away_team)
    
    print(f"\n📊 Coletando dados do confronto direto ({home_team} vs {away_team})...")
    print("(Deixe em branco para não usar H2H)")
    h2h_use = input("Incluir H2H? (S/N): ").strip().upper()
    h2h_matches = []
    if h2h_use == "S":
        h2h_matches = input_matches("confronto direto")
    
    news_texts = input_news_texts()
    
    # Avaliar matchup
    print("\n⏳ Analisando matchup...\n")
    
    rec = evaluate_matchup(
        home_team=home_team,
        away_team=away_team,
        home_matches=home_matches,
        away_matches=away_matches,
        h2h_matches=h2h_matches,
        news_texts=news_texts,
    )
    
    # Exibir resultados
    print("="*80)
    print("📊 RESULTADO DA ANÁLISE")
    print("="*80)
    
    print(f"\n🎯 Jogo: {rec.home_team} x {rec.away_team}")
    print(f"{'Status:':<20} {'✅ APROVADO' if rec.approved else '❌ REJEITADO'}")
    print(f"{'Pontuação:':<20} {rec.confidence_score}/100")
    print(f"{'Média de Gols:':<20} {rec.combined_avg_goals:.2f}")
    
    print(f"\n📈 Estatísticas {rec.home_team}:")
    print(f"  Média Gols Marcados: {rec.team_home_metrics.avg_scored:.2f}")
    print(f"  Média Gols Sofridos: {rec.team_home_metrics.avg_conceded:.2f}")
    print(f"  Média Total de Gols: {rec.team_home_metrics.avg_total_goals:.2f}")
    print(f"  Taxa de 0x0: {rec.team_home_metrics.zero_zero_rate*100:.1f}%")
    print(f"  Taxa de 6+ gols: {rec.team_home_metrics.extreme_over_rate*100:.1f}%")
    
    print(f"\n📉 Estatísticas {rec.away_team}:")
    print(f"  Média Gols Marcados: {rec.team_away_metrics.avg_scored:.2f}")
    print(f"  Média Gols Sofridos: {rec.team_away_metrics.avg_conceded:.2f}")
    print(f"  Média Total de Gols: {rec.team_away_metrics.avg_total_goals:.2f}")
    print(f"  Taxa de 0x0: {rec.team_away_metrics.zero_zero_rate*100:.1f}%")
    print(f"  Taxa de 6+ gols: {rec.team_away_metrics.extreme_over_rate*100:.1f}%")
    
    if rec.h2h_range_rate is not None:
        print(f"\n🔄 H2H: {rec.h2h_range_rate*100:.1f}% dentro do intervalo {rec.suggested_market.split()[-1]}")
    
    print(f"\n💡 Sugestão de Bilhete:")
    print(f"  {format_ticket_suggestion(rec)}")
    
    if rec.reasons:
        print(f"\n⚠️  Motivos de Rejeição:")
        for reason in rec.reasons:
            print(f"  • {reason}")
    
    if rec.news_impact.notes:
        print(f"\n📢 Contexto de Notícias:")
        for note in rec.news_impact.notes:
            print(f"  • {note}")
        print(f"  Ajuste de Risco: {rec.news_impact.risk_adjustment:+d}")
    
    # Calculadora de banca
    print("\n" + "="*80)
    print("💰 CALCULADORA DE BANCA COM JUROS COMPOSTOS")
    print("="*80)
    
    initial_balance = input_float(f"\nSaldo Inicial (padrão R$ 10): ", default=10.0)
    daily_target = input_float("Meta Diária em % (padrão 20): ", default=20.0) / 100
    odd_target = input_float("Odd Alvo (padrão 1.20): ", default=1.20)
    days = input_int("Quantidade de Dias (padrão 30): ", default=30)
    
    try:
        bankroll_plan = project_bankroll(
            initial_balance=initial_balance,
            daily_target=daily_target,
            odd_target=odd_target,
            days=days,
        )
        
        print(f"\n📊 Projeção de Banca para {days} dias:")
        print("-" * 80)
        
        for i, row in enumerate(bankroll_plan):
            if i == 0 or i == len(bankroll_plan) - 1 or (i < 5):
                print(f"Dia {row.day:>2}: Abertura R${row.opening_bankroll:>10.2f} | "
                      f"Lucro R${row.target_profit:>8.2f} | "
                      f"Entrada R${row.suggested_stake:>8.2f} | "
                      f"Fechamento R${row.closing_bankroll:>10.2f}")
            elif i == 5:
                print("...")
        
        final = bankroll_plan[-1].closing_bankroll
        growth = ((final - initial_balance) / initial_balance) * 100
        
        print(f"\n💎 Resultado Final:")
        print(f"  Saldo Inicial: R$ {initial_balance:.2f}")
        print(f"  Saldo Final: R$ {final:.2f}")
        print(f"  Crescimento: {growth:.1f}%")
        
    except ValueError as e:
        print(f"❌ Erro na calculadora: {e}")
    
    print("\n" + "="*80)
    print("✅ Demonstração Finalizada!")
    print("="*80 + "\n")

def main():
    """Menu principal."""
    while True:
        print("\n" + "="*80)
        print("MENU PRINCIPAL - SISTEMA DE ANÁLISE DE FUTEBOL")
        print("="*80)
        print("1. Análise Interativa (inserir dados manualmente)")
        print("2. Teste com Dados de Exemplo")
        print("3. Calculadora de Banca")
        print("4. Sair")
        
        choice = input("\nEscolha uma opção (1-4): ").strip()
        
        if choice == "1":
            demonstrate_system()
        
        elif choice == "2":
            from football_total_goals_strategy import build_sample_data, format_ticket_suggestion, rank_recommendations, pick_best_recommendation
            
            home_a, away_a, h2h_a, home_b, away_b, h2h_b = build_sample_data()
            
            print("\n📊 Analisando com dados de exemplo...\n")
            
            rec1 = evaluate_matchup("Alpha FC", "Beta United", home_a, away_a, h2h_a)
            rec2 = evaluate_matchup("Gamma City", "Delta Town", home_b, away_b, h2h_b)
            
            recommendations = [rec1, rec2]
            ranked = rank_recommendations(recommendations)
            best = pick_best_recommendation(recommendations)
            
            print("="*80)
            print("RANKING DE JOGOS")
            print("="*80)
            for i, rec in enumerate(ranked, 1):
                print(f"{i}. {rec.home_team} x {rec.away_team}")
                print(f"   Confiança: {rec.confidence_score}/100 | "
                      f"Média: {rec.combined_avg_goals:.2f} | "
                      f"{'✅ APROVADO' if rec.approved else '❌ REJEITADO'}")
            
            if best:
                print(f"\n🏆 JOGO DO DIA: {best.home_team} x {best.away_team}")
                print(f"   {format_ticket_suggestion(best)}")
            
            print()
        
        elif choice == "3":
            print("\n💰 CALCULADORA DE BANCA")
            print("="*80)
            
            initial = input_float("Saldo Inicial: ", default=10.0)
            daily = input_float("Meta Diária (%): ", default=20.0) / 100
            odd = input_float("Odd Alvo: ", default=1.20)
            days = input_int("Dias: ", default=30)
            
            try:
                plan = project_bankroll(initial, daily, odd, days)
                
                print("\nProjeção (seleção):")
                for row in plan[::5]:
                    print(f"  Dia {row.day}: R$ {row.opening_bankroll:.2f} → R$ {row.closing_bankroll:.2f}")
                
                final = plan[-1].closing_bankroll
                print(f"\n  Final: R$ {final:.2f} ({((final-initial)/initial)*100:.0f}%)")
            
            except ValueError as e:
                print(f"❌ Erro: {e}")
            
            print()
        
        elif choice == "4":
            print("\n👋 Até logo!\n")
            break
        
        else:
            print("\n❌ Opção inválida!")

if __name__ == "__main__":
    main()
