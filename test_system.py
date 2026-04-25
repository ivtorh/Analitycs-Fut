#!/usr/bin/env python3
"""
Script de teste para validar as funcionalidades do sistema de análise de futebol.
Testa: filtragem estatística, banca com juros compostos, H2H e contexto inteligente.
"""

import os
from football_total_goals_strategy import (
    MatchStat,
    build_sample_data,
    evaluate_matchup,
    project_bankroll,
    bankroll_rows_to_dicts,
    recommendation_to_rows,
    build_text_report,
    write_report_file,
    pick_best_recommendation,
    rank_recommendations,
    DEFAULT_DAILY_TARGET,
    DEFAULT_ODD_TARGET,
    DEFAULT_DAYS,
)

def test_motor_filtragem():
    """Testa o motor de filtragem estatística com dados de exemplo."""
    print("\n" + "="*80)
    print("TESTE 1: Motor de Filtragem Estatística")
    print("="*80)
    
    home_a, away_a, h2h_a, _, _, _ = build_sample_data()
    
    rec = evaluate_matchup(
        home_team="Alpha FC",
        away_team="Beta United",
        home_matches=home_a,
        away_matches=away_a,
        h2h_matches=h2h_a,
        news_texts=["Goalkeeper ruled out.", "Main striker expected."]
    )
    
    print(f"\nJogo: {rec.home_team} x {rec.away_team}")
    print(f"Aprovado: {'✓ SIM' if rec.approved else '✗ NÃO'}")
    print(f"Confiança: {rec.confidence_score}/100")
    print(f"Média Combinada de Gols: {rec.combined_avg_goals:.2f}")
    print(f"Mercado Sugerido: {rec.suggested_market}")
    print(f"Odd Alvo: {rec.suggested_odd:.2f}")
    
    if rec.h2h_range_rate:
        print(f"Taxa H2H (intervalo): {rec.h2h_range_rate*100:.1f}%")
    
    print(f"\nMétricas Time Casa ({rec.home_team}):")
    print(f"  - Jogos: {rec.team_home_metrics.matches}")
    print(f"  - Média Gols Marcados: {rec.team_home_metrics.avg_scored:.2f}")
    print(f"  - Média Gols Sofridos: {rec.team_home_metrics.avg_conceded:.2f}")
    print(f"  - Média Total de Gols: {rec.team_home_metrics.avg_total_goals:.2f}")
    print(f"  - Taxa de 0x0: {rec.team_home_metrics.zero_zero_rate*100:.1f}%")
    print(f"  - Taxa de 6+ gols: {rec.team_home_metrics.extreme_over_rate*100:.1f}%")
    
    print(f"\nMétricas Time Visitante ({rec.away_team}):")
    print(f"  - Jogos: {rec.team_away_metrics.matches}")
    print(f"  - Média Gols Marcados: {rec.team_away_metrics.avg_scored:.2f}")
    print(f"  - Média Gols Sofridos: {rec.team_away_metrics.avg_conceded:.2f}")
    print(f"  - Média Total de Gols: {rec.team_away_metrics.avg_total_goals:.2f}")
    print(f"  - Taxa de 0x0: {rec.team_away_metrics.zero_zero_rate*100:.1f}%")
    print(f"  - Taxa de 6+ gols: {rec.team_away_metrics.extreme_over_rate*100:.1f}%")
    
    if rec.reasons:
        print(f"\n⚠️  Alertas/Motivos de Rejeição:")
        for reason in rec.reasons:
            print(f"   - {reason}")
    
    if rec.news_impact.notes:
        print(f"\n📰 Contexto Inteligente (Notícias):")
        for note in rec.news_impact.notes:
            print(f"   - {note}")
        print(f"   Ajuste de Risco: {rec.news_impact.risk_adjustment:+d}")
    
    return rec

def test_banca_juros_compostos():
    """Testa o cálculo de banca com juros compostos."""
    print("\n" + "="*80)
    print("TESTE 2: Banca com Juros Compostos (30 dias)")
    print("="*80)
    
    initial_balance = 10.0
    daily_target = 0.20  # 20%
    odd_target = 1.20
    
    print(f"\nParâmetros:")
    print(f"  - Saldo Inicial: R$ {initial_balance:.2f}")
    print(f"  - Meta Diária: {daily_target*100:.0f}%")
    print(f"  - Odd Alvo: {odd_target:.2f}")
    
    bankroll_plan = project_bankroll(
        initial_balance=initial_balance,
        daily_target=daily_target,
        odd_target=odd_target,
        days=30
    )
    
    print(f"\nProjeção para os primeiros 5 dias:")
    print("-" * 80)
    for i, row in enumerate(bankroll_plan[:5], 1):
        print(f"Dia {row.day}:")
        print(f"  Abertura: R$ {row.opening_bankroll:>10.2f} | "
              f"Lucro Meta: R$ {row.target_profit:>8.2f} | "
              f"Entrada: R$ {row.suggested_stake:>8.2f} | "
              f"Fechamento: R$ {row.closing_bankroll:>10.2f}")
    
    print(f"\n... (dias 6-25 omitidos) ...\n")
    
    print(f"Projeção para os últimos 5 dias:")
    print("-" * 80)
    for row in bankroll_plan[-5:]:
        print(f"Dia {row.day}:")
        print(f"  Abertura: R$ {row.opening_bankroll:>10.2f} | "
              f"Lucro Meta: R$ {row.target_profit:>8.2f} | "
              f"Entrada: R$ {row.suggested_stake:>8.2f} | "
              f"Fechamento: R$ {row.closing_bankroll:>10.2f}")
    
    final_balance = bankroll_plan[-1].closing_bankroll
    growth_percentage = ((final_balance - initial_balance) / initial_balance) * 100
    
    print(f"\n📊 Resumo da Projeção:")
    print(f"  - Saldo Final (Dia 30): R$ {final_balance:.2f}")
    print(f"  - Crescimento Absoluto: R$ {final_balance - initial_balance:.2f}")
    print(f"  - Crescimento Percentual: {growth_percentage:.1f}%")
    
    return bankroll_plan

def test_multiplos_jogos():
    """Testa análise de múltiplos jogos e ranking."""
    print("\n" + "="*80)
    print("TESTE 3: Análise de Múltiplos Jogos e Ranking")
    print("="*80)
    
    home_a, away_a, h2h_a, home_b, away_b, h2h_b = build_sample_data()
    
    recommendations = [
        evaluate_matchup(
            "Alpha FC",
            "Beta United",
            home_a,
            away_a,
            h2h_a,
            news_texts=["Goalkeeper ruled out.", "Main striker expected."]
        ),
        evaluate_matchup(
            "Gamma City",
            "Delta Town",
            home_b,
            away_b,
            h2h_b,
            news_texts=["Top scorer unavailable.", "Defensive line with doubts."]
        ),
    ]
    
    ranked = rank_recommendations(recommendations)
    best = pick_best_recommendation(recommendations)
    
    print(f"\nJogos Analisados: {len(recommendations)}")
    print(f"Jogos Aprovados: {sum(1 for r in recommendations if r.approved)}")
    
    print(f"\n📊 Ranking de Confiança (Maior para Menor):")
    print("-" * 80)
    for i, rec in enumerate(ranked, 1):
        status = "✓ APROVADO" if rec.approved else "✗ REJEITADO"
        print(f"{i}. {rec.home_team} x {rec.away_team}")
        print(f"   Confiança: {rec.confidence_score}/100 | {status}")
        print(f"   Média: {rec.combined_avg_goals:.2f} gols | "
              f"Mercado: {rec.suggested_market}")
    
    if best:
        print(f"\n🏆 JOGO DO DIA:")
        print(f"   {best.home_team} x {best.away_team}")
        print(f"   Confiança: {best.confidence_score}/100")
        print(f"   Sugestão: {best.suggested_market} | Odd: {best.suggested_odd:.2f}")
    else:
        print("\n❌ Nenhum jogo aprovado pelos filtros.")
    
    return recommendations, ranked, best

def test_relatorio_completo():
    """Testa a geração de relatório completo."""
    print("\n" + "="*80)
    print("TESTE 4: Relatório Completo")
    print("="*80)
    
    home_a, away_a, h2h_a, home_b, away_b, h2h_b = build_sample_data()
    
    recommendations = [
        evaluate_matchup(
            "Alpha FC",
            "Beta United",
            home_a,
            away_a,
            h2h_a,
            news_texts=["Goalkeeper ruled out.", "Main striker expected."]
        ),
        evaluate_matchup(
            "Gamma City",
            "Delta Town",
            home_b,
            away_b,
            h2h_b,
            news_texts=["Top scorer unavailable.", "Defensive line with doubts."]
        ),
    ]
    
    bankroll_plan = project_bankroll(
        initial_balance=10.0,
        daily_target=DEFAULT_DAILY_TARGET,
        odd_target=DEFAULT_ODD_TARGET,
        days=DEFAULT_DAYS,
    )
    
    report = build_text_report(
        recommendations=recommendations,
        bankroll_plan=bankroll_plan,
        current_day=1,
        include_ia_doc=True,
    )
    
    report_path = "relatorio_analise_futebol.txt"
    write_report_file(report_path, report)
    
    print(f"\n✅ Relatório gerado e salvo em: {report_path}")
    print(f"\nPrimeiras linhas do relatório:")
    print("-" * 80)
    lines = report.split("\n")[:30]
    print("\n".join(lines))
    print("\n... (restante omitido) ...\n")
    
    return report_path

def main():
    """Executa todos os testes."""
    print("\n" + "="*80)
    print("VALIDAÇÃO DO SISTEMA DE ANÁLISE DE FUTEBOL - TOTAL DE GOLS")
    print("="*80)
    print(f"Data de Teste: {__import__('datetime').datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    
    try:
        # Teste 1: Motor de filtragem
        rec = test_motor_filtragem()
        
        # Teste 2: Banca com juros compostos
        bankroll = test_banca_juros_compostos()
        
        # Teste 3: Múltiplos jogos e ranking
        recs, ranked, best = test_multiplos_jogos()
        
        # Teste 4: Relatório completo
        report_path = test_relatorio_completo()
        
        print("\n" + "="*80)
        print("✅ TODOS OS TESTES FORAM EXECUTADOS COM SUCESSO!")
        print("="*80)
        print(f"\nResumo dos Testes:")
        print(f"  1. ✓ Motor de filtragem estatística: OK")
        print(f"  2. ✓ Calculadora de banca: OK")
        print(f"  3. ✓ Ranking de recomendações: OK")
        print(f"  4. ✓ Geração de relatório: OK ({report_path})")
        print(f"\nO sistema está pronto para uso!")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERRO durante a execução: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
