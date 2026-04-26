"""Sistema de Liquidação de Bilhetes (Settlement).

Responsabilidades:
- Monitorar status das partidas até conclusão
- Comparar resultado final com palpite do usuário
- Calcular ganho/perda
- Registrar resultado no banco de dados
- Notificar usuário de forma estruturada
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Callable
import threading
import time


class BetStatus(str, Enum):
    """Status de um bilhete de aposta."""
    PENDING = "Pendente"           # Aguardando resultado
    WON = "Vencido"                # Ganhou
    LOST = "Perdido"               # Perdeu
    VOID = "Cancelado"             # Anulado (jogo não jogado)
    PARTIALLY_WON = "Parcialmente Vencido"
    PUSH = "Empate"                # Retorno de aposta


class BetMarket(str, Enum):
    """Mercados de aposta suportados para liquidação."""
    HOME_WIN = "Home"
    DRAW = "Draw"
    AWAY_WIN = "Away"
    OVER = "Over"
    UNDER = "Under"
    BOTH_TO_SCORE_YES = "Both to Score Yes"
    BOTH_TO_SCORE_NO = "Both to Score No"
    HOME_TOTAL = "Home Total"
    AWAY_TOTAL = "Away Total"


class SettlementResult(str, Enum):
    """Resultado final da liquidação."""
    WIN = "WIN"
    LOSS = "LOSS"
    VOID = "VOID"
    PUSH = "PUSH"


@dataclass(frozen=True)
class MatchResult:
    """Resultado final de uma partida."""
    
    match_id: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    status: str  # "FINISHED", "POSTPONED", "CANCELLED"
    timestamp: datetime = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())
    
    @property
    def total_goals(self) -> int:
        """Total de gols da partida."""
        return self.home_goals + self.away_goals
    
    @property
    def result_type(self) -> str:
        """Tipo de resultado: 'Home Win', 'Draw', 'Away Win'."""
        if self.home_goals > self.away_goals:
            return "Home Win"
        elif self.away_goals > self.home_goals:
            return "Away Win"
        else:
            return "Draw"


@dataclass(frozen=True)
class Bet:
    """Bilhete de aposta do usuário."""
    
    bet_id: str
    match_id: str
    home_team: str
    away_team: str
    market: BetMarket
    stake: float                   # Valor apostado
    odds: float                    # Odd original
    market_value: Optional[Any] = None  # Ex: total >= 2.5 para Over/Under
    timestamp: datetime = None
    
    def __post_init__(self) -> None:
        if self.timestamp is None:
            object.__setattr__(self, 'timestamp', datetime.now())
    
    @property
    def potential_win(self) -> float:
        """Retorno potencial se ganhar."""
        return self.stake * self.odds
    
    @property
    def potential_profit(self) -> float:
        """Lucro potencial se ganhar."""
        return self.potential_win - self.stake


@dataclass(frozen=True)
class SettlementRecord:
    """Registro de liquidação de um bilhete."""
    
    bet_id: str
    match_id: str
    home_team: str
    away_team: str
    market: str
    stake: float
    odds: float
    result: SettlementResult
    home_goals: int
    away_goals: int
    settled_amount: float          # Valor pago (stake ou stake * odds)
    profit_loss: float             # Lucro ou perda
    payout_multiplier: float       # Multiplicador (0 = perda, 1 = push, odds = ganho)
    status_before: str
    status_after: str
    settlement_time: datetime = None
    
    def __post_init__(self) -> None:
        if self.settlement_time is None:
            object.__setattr__(self, 'settlement_time', datetime.now())


class SettlementEngine:
    """Motor de liquidação de bilhetes."""
    
    def __init__(self):
        self._bets: dict[str, Bet] = {}
        self._results: dict[str, MatchResult] = {}
        self._settlements: dict[str, SettlementRecord] = {}
        self._callbacks: list[Callable[[SettlementRecord], None]] = []
        self._lock = threading.Lock()
    
    def register_bet(self, bet: Bet) -> None:
        """Registra novo bilhete de aposta."""
        with self._lock:
            self._bets[bet.bet_id] = bet
    
    def update_match_result(self, result: MatchResult) -> Optional[list[SettlementRecord]]:
        """Atualiza resultado de partida e liquida bilhetes relacionados.
        
        Args:
            result: Resultado da partida
        
        Returns:
            Lista de registros de liquidação gerados
        """
        with self._lock:
            self._results[result.match_id] = result
            
            # Encontrar bilhetes para esta partida
            related_bets = [
                bet for bet in self._bets.values()
                if bet.match_id == result.match_id
            ]
            
            settlements = []
            for bet in related_bets:
                settlement = self._settle_bet(bet, result)
                if settlement:
                    self._settlements[settlement.bet_id] = settlement
                    settlements.append(settlement)
                    self._notify_callbacks(settlement)
            
            return settlements
    
    def _settle_bet(
        self,
        bet: Bet,
        result: MatchResult,
    ) -> Optional[SettlementRecord]:
        """Liquida um bilhete individual contra um resultado.
        
        Args:
            bet: Bilhete a liquidar
            result: Resultado da partida
        
        Returns:
            SettlementRecord com resultado da liquidação
        """
        # Verificar status do jogo
        if result.status == "CANCELLED":
            settlement_result = SettlementResult.VOID
            settled_amount = bet.stake
            payout_multiplier = 1.0
        elif result.status == "POSTPONED":
            settlement_result = SettlementResult.VOID
            settled_amount = bet.stake
            payout_multiplier = 1.0
        else:
            # Analisar resultado baseado no mercado
            settlement_result, payout_multiplier = self._evaluate_bet(
                bet,
                result,
            )
            settled_amount = bet.stake * payout_multiplier
        
        profit_loss = settled_amount - bet.stake
        
        return SettlementRecord(
            bet_id=bet.bet_id,
            match_id=bet.match_id,
            home_team=result.home_team,
            away_team=result.away_team,
            market=bet.market.value,
            stake=bet.stake,
            odds=bet.odds,
            result=settlement_result,
            home_goals=result.home_goals,
            away_goals=result.away_goals,
            settled_amount=settled_amount,
            profit_loss=profit_loss,
            payout_multiplier=payout_multiplier,
            status_before=BetStatus.PENDING.value,
            status_after=self._result_to_status(settlement_result),
        )
    
    def _evaluate_bet(
        self,
        bet: Bet,
        result: MatchResult,
    ) -> tuple[SettlementResult, float]:
        """Avalia se um bilhete ganhou ou perdeu.
        
        Args:
            bet: Bilhete a avaliar
            result: Resultado da partida
        
        Returns:
            Tupla (SettlementResult, multiplicador de pagamento)
        """
        # Lógica por mercado
        if bet.market == BetMarket.HOME_WIN:
            if result.home_goals > result.away_goals:
                return SettlementResult.WIN, bet.odds
            elif result.home_goals == result.away_goals:
                return SettlementResult.PUSH, 1.0  # Empate = aposta retorna
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.DRAW:
            if result.home_goals == result.away_goals:
                return SettlementResult.WIN, bet.odds
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.AWAY_WIN:
            if result.away_goals > result.home_goals:
                return SettlementResult.WIN, bet.odds
            elif result.home_goals == result.away_goals:
                return SettlementResult.PUSH, 1.0
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.OVER:
            threshold = bet.market_value or 2.5
            if result.total_goals > threshold:
                return SettlementResult.WIN, bet.odds
            elif result.total_goals == threshold:
                # Bettings market rules: exactly at threshold = push
                return SettlementResult.PUSH, 1.0
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.UNDER:
            threshold = bet.market_value or 2.5
            if result.total_goals < threshold:
                return SettlementResult.WIN, bet.odds
            elif result.total_goals == threshold:
                return SettlementResult.PUSH, 1.0
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.BOTH_TO_SCORE_YES:
            if result.home_goals > 0 and result.away_goals > 0:
                return SettlementResult.WIN, bet.odds
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.BOTH_TO_SCORE_NO:
            if result.home_goals == 0 or result.away_goals == 0:
                return SettlementResult.WIN, bet.odds
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.HOME_TOTAL:
            threshold = bet.market_value or 1.5
            if result.home_goals > threshold:
                return SettlementResult.WIN, bet.odds
            else:
                return SettlementResult.LOSS, 0.0
        
        elif bet.market == BetMarket.AWAY_TOTAL:
            threshold = bet.market_value or 1.5
            if result.away_goals > threshold:
                return SettlementResult.WIN, bet.odds
            else:
                return SettlementResult.LOSS, 0.0
        
        # Padrão: perder
        return SettlementResult.LOSS, 0.0
    
    def _result_to_status(self, result: SettlementResult) -> str:
        """Converte SettlementResult para BetStatus."""
        mapping = {
            SettlementResult.WIN: BetStatus.WON.value,
            SettlementResult.LOSS: BetStatus.LOST.value,
            SettlementResult.VOID: BetStatus.VOID.value,
            SettlementResult.PUSH: BetStatus.PUSH.value,
        }
        return mapping.get(result, BetStatus.PENDING.value)
    
    def subscribe(self, callback: Callable[[SettlementRecord], None]) -> None:
        """Registra callback para eventos de liquidação.
        
        Args:
            callback: Função que recebe SettlementRecord
        """
        with self._lock:
            self._callbacks.append(callback)
    
    def unsubscribe(self, callback: Callable[[SettlementRecord], None]) -> None:
        """Remove callback."""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
    
    def _notify_callbacks(self, settlement: SettlementRecord) -> None:
        """Notifica todos os callbacks registrados."""
        with self._lock:
            callbacks = list(self._callbacks)
        
        for callback in callbacks:
            try:
                callback(settlement)
            except Exception as e:
                print(f"❌ Erro em callback de settlement: {e}")
    
    def get_settlement(self, bet_id: str) -> Optional[SettlementRecord]:
        """Obtém registro de liquidação de um bilhete."""
        with self._lock:
            return self._settlements.get(bet_id)
    
    def get_settlements_by_match(self, match_id: str) -> list[SettlementRecord]:
        """Obtém todos os registros de liquidação para uma partida."""
        with self._lock:
            return [
                s for s in self._settlements.values()
                if s.match_id == match_id
            ]
    
    def get_user_stats(self) -> dict[str, Any]:
        """Retorna estatísticas gerais de apostas.
        
        Returns:
            Dicionário com stats: wins, losses, voids, total_profit, etc.
        """
        with self._lock:
            settlements = list(self._settlements.values())
        
        if not settlements:
            return {
                "total_bets": 0,
                "won": 0,
                "lost": 0,
                "void": 0,
                "push": 0,
                "total_staked": 0.0,
                "total_returned": 0.0,
                "total_profit": 0.0,
                "roi": 0.0,
                "win_rate": 0.0,
            }
        
        total_staked = sum(s.stake for s in settlements)
        total_returned = sum(s.settled_amount for s in settlements)
        total_profit = total_returned - total_staked
        
        won = sum(1 for s in settlements if s.result == SettlementResult.WIN)
        lost = sum(1 for s in settlements if s.result == SettlementResult.LOSS)
        void = sum(1 for s in settlements if s.result == SettlementResult.VOID)
        push = sum(1 for s in settlements if s.result == SettlementResult.PUSH)
        
        win_rate = (won / len(settlements) * 100) if settlements else 0.0
        roi = (total_profit / total_staked * 100) if total_staked > 0 else 0.0
        
        return {
            "total_bets": len(settlements),
            "won": won,
            "lost": lost,
            "void": void,
            "push": push,
            "total_staked": round(total_staked, 2),
            "total_returned": round(total_returned, 2),
            "total_profit": round(total_profit, 2),
            "roi": round(roi, 2),
            "win_rate": round(win_rate, 2),
        }


# Exemplo de uso
if __name__ == "__main__":
    engine = SettlementEngine()
    
    # Registrar callback
    def on_settlement(record: SettlementRecord) -> None:
        status_color = "🟢" if record.result == SettlementResult.WIN else "🔴"
        print(f"{status_color} Bilhete {record.bet_id}: {record.result.value}")
        print(f"   {record.home_team} {record.home_goals} x {record.away_goals} {record.away_team}")
        print(f"   Mercado: {record.market}")
        print(f"   Lucro/Perda: ${record.profit_loss:+.2f}")
    
    engine.subscribe(on_settlement)
    
    # Criar e registrar uma aposta
    bet = Bet(
        bet_id="BET001",
        match_id="MATCH001",
        home_team="Manchester United",
        away_team="Liverpool",
        market=BetMarket.HOME_WIN,
        stake=100.0,
        odds=1.85,
    )
    engine.register_bet(bet)
    print(f"💰 Aposta registrada: {bet.home_team} Win @ {bet.odds}")
    
    # Simular resultado
    result = MatchResult(
        match_id="MATCH001",
        home_team="Manchester United",
        away_team="Liverpool",
        home_goals=2,
        away_goals=1,
        status="FINISHED",
    )
    
    print("\n⚽ Resultado chegou...")
    settlements = engine.update_match_result(result)
    
    # Exibir estatísticas
    stats = engine.get_user_stats()
    print(f"\n📊 Estatísticas do usuário:")
    print(f"   Total de apostas: {stats['total_bets']}")
    print(f"   Vitórias: {stats['won']} | Derrotas: {stats['lost']}")
    print(f"   ROI: {stats['roi']:.1f}%")
    print(f"   Lucro total: ${stats['total_profit']:.2f}")
