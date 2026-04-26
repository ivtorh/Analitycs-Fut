"""Sistema de Monitoramento de Odds em Tempo Real.

Responsabilidades:
- Consultar odds de mercados específicos (Match Winner, Over/Under, etc.)
- Filtrar pelo bookmaker de maior prioridade
- Fornecer atualizações contínuas via callback
- Integração com múltiplas fontes de odds (API-Sports, TheSportsDB, etc.)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Callable
import time
import threading

try:
    import requests
except Exception:
    requests = None


class BookmakerPriority(str, Enum):
    """Prioridade de bookmakers para seleção de odds."""
    PINNACLE = "Pinnacle"          # Melhor para trading
    BETFAIR = "Betfair"            # Maior liquidez
    DAFABET = "Dafabet"            # Popular Ásia
    BET365 = "Bet365"              # Confiável
    BETWAY = "Betway"              # Alternativa
    DEFAULT = "Pinnacle"           # Default


class OddsMarket(str, Enum):
    """Mercados de apostas suportados."""
    MATCH_WINNER = "Match Winner"
    OVER_UNDER = "Over/Under"
    BOTH_TEAMS_SCORE = "Both Teams to Score"
    HOME_TOTAL = "Home Total"
    AWAY_TOTAL = "Away Total"


@dataclass(frozen=True)
class OddsSnapshot:
    """Captura de odds em um momento específico."""
    
    match_id: str
    home_team: str
    away_team: str
    market: str
    bookmaker: str
    odd_home: Optional[float] = None
    odd_draw: Optional[float] = None
    odd_away: Optional[float] = None
    over_odd: Optional[float] = None
    under_odd: Optional[float] = None
    timestamp: datetime = None
    last_update: datetime = None
    confidence: float = 1.0  # Confiança na cotação (0-1)
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())
        if self.last_update is None:
            object.__setattr__(self, 'last_update', datetime.now())
    
    @property
    def age_seconds(self) -> float:
        """Retorna idade da cotação em segundos."""
        return (datetime.now() - self.last_update).total_seconds()
    
    @property
    def is_stale(self, max_age: int = 300) -> bool:
        """Verifica se a cotação é antiga (padrão: 5 min)."""
        return self.age_seconds > max_age


@dataclass(frozen=True)
class OddsComparison:
    """Comparação de odds entre bookmakers."""
    
    match_id: str
    market: str
    bookmaker_best: str
    odds_snapshot: dict[str, float]
    arbitrage_opportunity: bool
    best_value: float
    timestamp: datetime = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())


class OddsDataProvider:
    """Interface para diferentes provedores de odds."""
    
    def __init__(self, api_key: str = "", base_url: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = 10
    
    def get_match_odds(
        self,
        match_id: str,
        market: OddsMarket = OddsMarket.MATCH_WINNER,
        bookmaker_priority: Optional[list[str]] = None,
    ) -> Optional[OddsSnapshot]:
        """Busca odds para uma partida específica.
        
        Args:
            match_id: ID da partida na API
            market: Tipo de mercado
            bookmaker_priority: Lista ordenada de bookmakers preferidos
        
        Returns:
            OddsSnapshot com dados da cotação ou None se não encontrado
        """
        raise NotImplementedError("Implementar em subclasse")
    
    def get_live_odds(
        self,
        match_id: str,
        market: OddsMarket = OddsMarket.MATCH_WINNER,
    ) -> Optional[OddsSnapshot]:
        """Busca odds ao vivo de uma partida em andamento."""
        raise NotImplementedError("Implementar em subclasse")


class MockOddsProvider(OddsDataProvider):
    """Provider de teste com dados simulados para desenvolvimento."""
    
    def __init__(self):
        super().__init__()
        self._mock_data = {
            "1": {
                "Match Winner": OddsSnapshot(
                    match_id="1",
                    home_team="Manchester United",
                    away_team="Liverpool",
                    market=OddsMarket.MATCH_WINNER,
                    bookmaker="Pinnacle",
                    odd_home=1.85,
                    odd_draw=3.50,
                    odd_away=2.10,
                ),
                "Over/Under": OddsSnapshot(
                    match_id="1",
                    home_team="Manchester United",
                    away_team="Liverpool",
                    market=OddsMarket.OVER_UNDER,
                    bookmaker="Pinnacle",
                    over_odd=1.90,
                    under_odd=1.95,
                ),
            }
        }
    
    def get_match_odds(
        self,
        match_id: str,
        market: OddsMarket = OddsMarket.MATCH_WINNER,
        bookmaker_priority: Optional[list[str]] = None,
    ) -> Optional[OddsSnapshot]:
        """Simula busca de odds."""
        match_data = self._mock_data.get(match_id, {})
        return match_data.get(market.value)
    
    def get_live_odds(
        self,
        match_id: str,
        market: OddsMarket = OddsMarket.MATCH_WINNER,
    ) -> Optional[OddsSnapshot]:
        """Simula odds ao vivo com variações aleatórias."""
        snapshot = self.get_match_odds(match_id, market)
        if snapshot is None:
            return None
        
        # Simular pequenas variações nas odds
        import random
        variance = random.uniform(-0.05, 0.05)
        
        return OddsSnapshot(
            match_id=snapshot.match_id,
            home_team=snapshot.home_team,
            away_team=snapshot.away_team,
            market=snapshot.market,
            bookmaker=snapshot.bookmaker,
            odd_home=snapshot.odd_home * (1 + variance) if snapshot.odd_home else None,
            odd_draw=snapshot.odd_draw * (1 + variance) if snapshot.odd_draw else None,
            odd_away=snapshot.odd_away * (1 + variance) if snapshot.odd_away else None,
            over_odd=snapshot.over_odd * (1 + variance) if snapshot.over_odd else None,
            under_odd=snapshot.under_odd * (1 + variance) if snapshot.under_odd else None,
            last_update=datetime.now(),
        )


class OddsMonitor:
    """Monitor de odds em tempo real com suporte a callbacks."""
    
    def __init__(
        self,
        provider: OddsDataProvider,
        update_interval: int = 30,  # segundos
    ):
        self.provider = provider
        self.update_interval = update_interval
        self._callbacks: list[Callable[[OddsSnapshot], None]] = []
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._watched_matches: dict[str, set[str]] = {}  # match_id -> set(markets)
        self._lock = threading.Lock()
        self._last_snapshots: dict[tuple[str, str], OddsSnapshot] = {}
    
    def subscribe(self, callback: Callable[[OddsSnapshot], None]) -> None:
        """Registra callback para atualizações de odds.
        
        Args:
            callback: Função que recebe OddsSnapshot como argumento
        """
        with self._lock:
            self._callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable[[OddsSnapshot], None]) -> None:
        """Remove callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def watch_match(
        self,
        match_id: str,
        markets: Optional[list[OddsMarket]] = None,
    ) -> None:
        """Começa a monitorar uma partida específica.
        
        Args:
            match_id: ID da partida
            markets: Lista de mercados a monitorar (padrão: MATCH_WINNER)
        """
        if markets is None:
            markets = [OddsMarket.MATCH_WINNER]
        
        with self._lock:
            if match_id not in self._watched_matches:
                self._watched_matches[match_id] = set()
            self._watched_matches[match_id].update(m.value for m in markets)
    
    def unwatch_match(self, match_id: str) -> None:
        """Para de monitorar uma partida."""
        with self._lock:
            self._watched_matches.pop(match_id, None)
    
    def start(self) -> None:
        """Inicia monitoramento em thread de fundo."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop(self) -> None:
        """Para monitoramento."""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def _monitor_loop(self) -> None:
        """Loop principal de monitoramento (executa em thread)."""
        while self._monitoring:
            try:
                matches_to_check = None
                with self._lock:
                    matches_to_check = dict(self._watched_matches)
                
                for match_id, markets in matches_to_check.items():
                    for market_str in markets:
                        try:
                            market = OddsMarket(market_str)
                            snapshot = self.provider.get_live_odds(match_id, market)
                            
                            if snapshot:
                                key = (match_id, market_str)
                                last = self._last_snapshots.get(key)
                                
                                # Notificar apenas se houver mudança significativa
                                if self._should_notify(last, snapshot):
                                    self._last_snapshots[key] = snapshot
                                    self._notify_callbacks(snapshot)
                        
                        except Exception as e:
                            print(f"❌ Erro ao buscar odds para {match_id}/{market_str}: {e}")
                
                time.sleep(self.update_interval)
            
            except Exception as e:
                print(f"❌ Erro no loop de monitoramento: {e}")
                time.sleep(self.update_interval)
    
    def _should_notify(
        self,
        last: Optional[OddsSnapshot],
        current: OddsSnapshot,
        threshold: float = 0.02,  # 2% de mudança
    ) -> bool:
        """Verifica se deve notificar sobre mudança de odds.
        
        Args:
            last: Última cotação conhecida
            current: Cotação atual
            threshold: Percentual mínimo de mudança para notificar
        
        Returns:
            True se deve notificar
        """
        if last is None:
            return True
        
        # Verificar mudança em odds principais
        if current.odd_home and last.odd_home:
            if abs(current.odd_home - last.odd_home) / last.odd_home > threshold:
                return True
        
        if current.odd_away and last.odd_away:
            if abs(current.odd_away - last.odd_away) / last.odd_away > threshold:
                return True
        
        if current.odd_draw and last.odd_draw:
            if abs(current.odd_draw - last.odd_draw) / last.odd_draw > threshold:
                return True
        
        if current.over_odd and last.over_odd:
            if abs(current.over_odd - last.over_odd) / last.over_odd > threshold:
                return True
        
        if current.under_odd and last.under_odd:
            if abs(current.under_odd - last.under_odd) / last.under_odd > threshold:
                return True
        
        return False
    
    def _notify_callbacks(self, snapshot: OddsSnapshot) -> None:
        """Notifica todos os callbacks registrados."""
        with self._lock:
            callbacks = list(self._callbacks)
        
        for callback in callbacks:
            try:
                callback(snapshot)
            except Exception as e:
                print(f"❌ Erro em callback de odds: {e}")
    
    def get_best_odds(
        self,
        match_id: str,
        market: OddsMarket = OddsMarket.MATCH_WINNER,
        bookmaker_priority: Optional[list[str]] = None,
    ) -> Optional[OddsSnapshot]:
        """Busca melhor odd para um mercado específico.
        
        Args:
            match_id: ID da partida
            market: Tipo de mercado
            bookmaker_priority: Lista de bookmakers por ordem de preferência
        
        Returns:
            OddsSnapshot com melhor cotação
        """
        if bookmaker_priority is None:
            bookmaker_priority = [BookmakerPriority.DEFAULT.value]
        
        return self.provider.get_match_odds(
            match_id,
            market,
            bookmaker_priority,
        )


# Exemplo de uso
if __name__ == "__main__":
    # Criar provider (simulated para teste)
    provider = MockOddsProvider()
    
    # Criar monitor
    monitor = OddsMonitor(provider, update_interval=2)
    
    # Registrar callback
    def on_odds_update(snapshot: OddsSnapshot) -> None:
        print(f"📊 Odds atualizada: {snapshot.home_team} vs {snapshot.away_team}")
        if snapshot.odd_home:
            print(f"   Home: {snapshot.odd_home:.2f}")
        if snapshot.odd_draw:
            print(f"   Draw: {snapshot.odd_draw:.2f}")
        if snapshot.odd_away:
            print(f"   Away: {snapshot.odd_away:.2f}")
        print(f"   Atualizado: {snapshot.last_update.strftime('%H:%M:%S')}")
    
    monitor.subscribe(on_odds_update)
    
    # Começar a monitorar
    monitor.watch_match("1", [OddsMarket.MATCH_WINNER, OddsMarket.OVER_UNDER])
    monitor.start()
    
    # Rodar por um tempo
    try:
        print("🚀 Monitoramento iniciado... (Ctrl+C para sair)")
        for _ in range(10):
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n⏹️  Parando monitoramento...")
    finally:
        monitor.stop()
