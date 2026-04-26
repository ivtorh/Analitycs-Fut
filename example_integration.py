"""Exemplo completo de integração das três evoluções.

Demonstra:
1. Monitoramento de odds em tempo real
2. Sistema de liquidação de bilhetes
3. Dashboard moderno com segurança
"""

from __future__ import annotations

import time
from datetime import datetime

from football_odds_monitor import (
    OddsMarket,
    OddsMonitor,
    MockOddsProvider,
    OddsSnapshot,
    BookmakerPriority,
)
from football_settlement import (
    Bet,
    BetMarket,
    MatchResult,
    SettlementEngine,
    SettlementRecord,
    SettlementResult,
)
from football_api_security import (
    SecureTokenManager,
    get_token_manager,
)


class IntegratedFootballSystem:
    """Sistema integrado com odds em tempo real, settlement e segurança."""
    
    def __init__(self, api_key: str = "", base_url: str = ""):
        """
        Inicializa o sistema integrado.
        
        Args:
            api_key: Chave da API football-data
            base_url: URL base da API (opcional)
        """
        # Componentes
        self.token_manager = get_token_manager()
        self.token_manager.set_api_credentials(api_key, base_url)
        
        self.odds_provider = MockOddsProvider()
        self.odds_monitor = OddsMonitor(self.odds_provider, update_interval=3)
        
        self.settlement_engine = SettlementEngine()
        
        # Registrar callbacks
        self.odds_monitor.subscribe(self._on_odds_update)
        self.settlement_engine.subscribe(self._on_settlement)
        
        # Estado
        self._active_bets: dict[str, Bet] = {}
        self._session_token: str | None = None
    
    def create_user_session(self, user_ip: str) -> str:
        """Cria sessão segura para usuário.
        
        Args:
            user_ip: IP do usuário
        
        Returns:
            Token de sessão (para usar no frontend)
        """
        self._session_token = self.token_manager.create_session(
            user_identifier=user_ip,
            permissions=[
                "read:matches",
                "read:odds",
                "read:settlement",
                "write:bets",
            ],
            duration_minutes=60,
        )
        print(f"✅ Sessão criada: {self._session_token[:30]}...")
        return self._session_token
    
    def start_monitoring(self, match_ids: list[str], markets: list[OddsMarket] | None = None) -> None:
        """Inicia monitoramento de odds para múltiplas partidas.
        
        Args:
            match_ids: IDs das partidas a monitorar
            markets: Mercados a monitorar (padrão: MATCH_WINNER e OVER_UNDER)
        """
        if markets is None:
            markets = [OddsMarket.MATCH_WINNER, OddsMarket.OVER_UNDER]
        
        for match_id in match_ids:
            self.odds_monitor.watch_match(match_id, markets)
        
        self.odds_monitor.start()
        print(f"🚀 Monitorando {len(match_ids)} partida(s)...")
    
    def place_bet(
        self,
        bet_id: str,
        match_id: str,
        home_team: str,
        away_team: str,
        market: BetMarket,
        stake: float,
        odds: float,
        market_value: float | None = None,
    ) -> Bet:
        """Coloca aposta com validação de sessão.
        
        Args:
            bet_id: ID único da aposta
            match_id: ID da partida
            home_team: Time da casa
            away_team: Time visitante
            market: Mercado da aposta
            stake: Valor apostado
            odds: Odd da aposta
            market_value: Valor do mercado (ex: 2.5 para Over/Under)
        
        Returns:
            Objeto Bet criado
        """
        # Validar sessão
        if not self._session_token or not self.token_manager.validate_session(self._session_token):
            raise PermissionError("Sessão inválida. Faça login novamente.")
        
        # Verificar rate limiting
        client_id = getattr(self, '_user_ip', 'unknown')
        if not self.token_manager.check_rate_limit(client_id, limit=50, window_seconds=60):
            raise RuntimeError("Limite de requisições atingido. Tente novamente em 1 minuto.")
        
        bet = Bet(
            bet_id=bet_id,
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            market=market,
            stake=stake,
            odds=odds,
            market_value=market_value,
        )
        
        self.settlement_engine.register_bet(bet)
        self._active_bets[bet_id] = bet
        
        print(f"\n💰 Aposta colocada:")
        print(f"   ID: {bet_id}")
        print(f"   Partida: {home_team} x {away_team}")
        print(f"   Mercado: {market.value}")
        print(f"   Stake: ${stake:.2f} @ {odds:.2f}")
        print(f"   Retorno potencial: ${bet.potential_win:.2f}")
        
        return bet
    
    def settle_match(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        home_goals: int,
        away_goals: int,
    ) -> list[SettlementRecord]:
        """Liquida todas as apostas de uma partida.
        
        Args:
            match_id: ID da partida
            home_team: Time da casa
            away_team: Time visitante
            home_goals: Gols do time da casa
            away_goals: Gols do time visitante
        
        Returns:
            Lista de registros de liquidação
        """
        result = MatchResult(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            home_goals=home_goals,
            away_goals=away_goals,
            status="FINISHED",
        )
        
        settlements = self.settlement_engine.update_match_result(result)
        return settlements or []
    
    def get_user_dashboard(self) -> dict:
        """Retorna dados do dashboard para o usuário.
        
        Returns:
            Dicionário com dados agregados
        """
        stats = self.settlement_engine.get_user_stats()
        
        return {
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "betting_stats": {
                "total_bets": stats["total_bets"],
                "won": stats["won"],
                "lost": stats["lost"],
                "void": stats["void"],
                "win_rate": f"{stats['win_rate']:.1f}%",
                "roi": f"{stats['roi']:.1f}%",
            },
            "bankroll": {
                "total_staked": f"${stats['total_staked']:.2f}",
                "total_returned": f"${stats['total_returned']:.2f}",
                "total_profit": f"${stats['total_profit']:.2f}",
            },
            "active_bets": len(self._active_bets),
            "session_active": self._session_token is not None,
        }
    
    def _on_odds_update(self, snapshot: OddsSnapshot) -> None:
        """Callback chamado quando odds são atualizadas."""
        print(f"\n📊 Odds Atualizada - {snapshot.home_team} vs {snapshot.away_team}:")
        if snapshot.odd_home:
            print(f"   Home: {snapshot.odd_home:.2f}")
        if snapshot.odd_draw:
            print(f"   Draw: {snapshot.odd_draw:.2f}")
        if snapshot.odd_away:
            print(f"   Away: {snapshot.odd_away:.2f}")
        print(f"   Bookmaker: {snapshot.bookmaker} | Atualizado: {snapshot.last_update.strftime('%H:%M:%S')}")
    
    def _on_settlement(self, record: SettlementRecord) -> None:
        """Callback chamado quando um bilhete é liquidado."""
        status_emoji = "🟢" if record.result == SettlementResult.WIN else ("🔴" if record.result == SettlementResult.LOSS else "⚪")
        print(f"\n{status_emoji} Liquidação - Bilhete {record.bet_id}:")
        print(f"   Partida: {record.home_team} {record.home_goals} x {record.away_goals} {record.away_team}")
        print(f"   Mercado: {record.market}")
        print(f"   Resultado: {record.result.value}")
        print(f"   Lucro/Perda: ${record.profit_loss:+.2f}")
    
    def stop(self) -> None:
        """Para o monitoramento e limpa recursos."""
        self.odds_monitor.stop()
        print("\n⏹️  Sistema parado.")


# Exemplo de uso completo
def main():
    print("=" * 60)
    print("⚽ SISTEMA INTEGRADO DE ANÁLISE DE FUTEBOL")
    print("=" * 60)
    
    # 1. Inicializar sistema
    print("\n1️⃣  Inicializando sistema...")
    system = IntegratedFootballSystem(
        api_key="seu_token_aqui",  # Em produção, vem de variável de ambiente
        base_url="https://api.football-data.org/v4"
    )
    print("✅ Sistema iniciado")
    
    # 2. Criar sessão de usuário
    print("\n2️⃣  Criando sessão de usuário...")
    user_session = system.create_user_session("192.168.1.100")
    system._user_ip = "192.168.1.100"
    
    # 3. Iniciar monitoramento de odds
    print("\n3️⃣  Iniciando monitoramento de odds em tempo real...")
    system.start_monitoring(
        match_ids=["1"],
        markets=[OddsMarket.MATCH_WINNER, OddsMarket.OVER_UNDER],
    )
    time.sleep(2)  # Deixar alguns eventos de atualização acontecer
    
    # 4. Colocar apostas
    print("\n4️⃣  Colocando apostas...")
    
    bet1 = system.place_bet(
        bet_id="BET001",
        match_id="1",
        home_team="Manchester United",
        away_team="Liverpool",
        market=BetMarket.HOME_WIN,
        stake=100.0,
        odds=1.85,
    )
    
    bet2 = system.place_bet(
        bet_id="BET002",
        match_id="1",
        home_team="Manchester United",
        away_team="Liverpool",
        market=BetMarket.OVER,
        stake=50.0,
        odds=1.92,
        market_value=2.5,
    )
    
    time.sleep(1)
    
    # 5. Simular resultado da partida
    print("\n5️⃣  Simulando resultado final da partida...")
    print("   Resultado: Manchester United 2 x 1 Liverpool (Over 2.5)")
    
    settlements = system.settle_match(
        match_id="1",
        home_team="Manchester United",
        away_team="Liverpool",
        home_goals=2,
        away_goals=1,
    )
    
    time.sleep(1)
    
    # 6. Exibir dashboard do usuário
    print("\n6️⃣  Dashboard do usuário:")
    dashboard = system.get_user_dashboard()
    print(f"\n   Status: {dashboard['status']}")
    print(f"   Total de apostas: {dashboard['betting_stats']['total_bets']}")
    print(f"   Vitórias: {dashboard['betting_stats']['won']}")
    print(f"   Derrotas: {dashboard['betting_stats']['lost']}")
    print(f"   Taxa de vitória: {dashboard['betting_stats']['win_rate']}")
    print(f"   ROI: {dashboard['betting_stats']['roi']}")
    print(f"   Lucro total: {dashboard['bankroll']['total_profit']}")
    
    # 7. Parar o sistema
    print("\n7️⃣  Encerrando...")
    system.stop()
    
    print("\n" + "=" * 60)
    print("✅ DEMO CONCLUÍDA COM SUCESSO!")
    print("=" * 60)
    print("\nPróximos passos:")
    print("1. Integrar com dashboard HTML moderno (football_dashboard_modern.html)")
    print("2. Conectar endpoints no servidor web (football_total_goals_web.py)")
    print("3. Configurar WebSocket para atualizações em tempo real")
    print("4. Implementar persistência em banco de dados")
    print("5. Adicionar notificações em tempo real (SMS, email, push)")


if __name__ == "__main__":
    main()
