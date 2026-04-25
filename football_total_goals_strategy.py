"""Ferramenta inicial para análise de futebol focada em Total de Gols.

O script foi desenhado para:
- Filtrar jogos com base nos últimos 10 jogos de cada time;
- Calcular consistência de placar por H2H;
- Projetar banca com juros compostos;
- Sugerir como integrar contexto de notícias/IA para ajustar risco.

Observações:
- O núcleo funciona sem dependências externas, mas aceita pandas quando disponível.
- Requests é usado apenas na integração opcional com APIs de notícias/dados.
- Para uma versão de produção, conecte as funções de ingestão de dados a uma API real
  ou a um scraper permitido pelo site de estatísticas que você for usar.

Estratégia de mercado:
- Intervalo 1-5 gols: linha mais conservadora para jogos com média controlada.
- Intervalo 0-4 gols: útil quando o modelo indicar viés de jogo mais truncado.

Integração de contexto inteligente (visão geral):
1) Fonte: NewsAPI, GNews, feed RSS do clube, Twitter/X via API, ou endpoint próprio
   que agregue manchetes por time e data do jogo.
2) NLP: use embeddings + classificador (ex.: sentence-transformers + sklearn),
   ou um LLM via API (OpenAI, Anthropic) com prompt que extrai JSON estruturado:
   ausências confirmadas (goleiro, zagueiros, artilheiro), dúvidas, retornos.
3) Encaixe no script: `fetch_news_from_api()` ou busca customizada -> lista de
   textos -> `evaluate_news_texts()` ajusta `NewsImpact` e a pontuação de confiança.
   Para produção, mapeie entidades (nome do jogador) contra escalação provável
   (API-Sports, Understat, etc.) em vez de só palavras-chave.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence, Any
import os
import statistics

try:
    import pandas as pd  # type: ignore
except Exception:  # pragma: no cover - opcional
    pd = None

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - opcional
    requests = None


# -----------------------------
# Constantes do modelo
# -----------------------------

MIN_COMBINED_AVG_GOALS = 1.8
MAX_COMBINED_AVG_GOALS = 3.8
MAX_ZERO_ZERO_RATE = 0.15
MAX_EXTREME_GOALS_RATE = 0.05
MIN_H2H_RANGE_RATE = 0.80
TARGET_GOALS_MIDPOINT = 2.8
DEFAULT_ODD_TARGET = 1.20
DEFAULT_DAILY_TARGET = 0.20
DEFAULT_DAYS = 30


class GoalsInterval(str, Enum):
    """Mercado-alvo para validação H2H e texto da sugestão de bilhete."""

    RANGE_1_5 = "1-5"
    RANGE_0_4 = "0-4"


# -----------------------------
# Estruturas de dados
# -----------------------------


@dataclass(frozen=True)
class MatchStat:
    """Representa um jogo individual na forma de estatística recente."""

    goals_for: int
    goals_against: int
    opponent: str = ""
    competition: str = ""

    @property
    def total_goals(self) -> int:
        return self.goals_for + self.goals_against

    @property
    def is_zero_zero(self) -> bool:
        return self.total_goals == 0

    @property
    def is_extreme_over(self) -> bool:
        # Mais de 5.5 gols no jogo => 6+ gols com placares inteiros.
        return self.total_goals > 5


@dataclass(frozen=True)
class TeamMetrics:
    """Resumo estatístico dos últimos jogos de um time."""

    matches: int
    avg_scored: float
    avg_conceded: float
    avg_total_goals: float
    zero_zero_rate: float
    extreme_over_rate: float
    zero_zero_count: int
    extreme_over_count: int


@dataclass(frozen=True)
class NewsImpact:
    """Impacto estimado de notícias/informações de elenco sobre o risco do jogo."""

    risk_adjustment: int
    notes: tuple[str, ...]


@dataclass(frozen=True)
class MatchRecommendation:
    """Resultado da avaliação de um confronto."""

    home_team: str
    away_team: str
    approved: bool
    confidence_score: int
    combined_avg_goals: float
    team_home_metrics: TeamMetrics
    team_away_metrics: TeamMetrics
    h2h_range_rate: Optional[float]
    h2h_matches: int
    reasons: tuple[str, ...]
    suggested_market: str
    suggested_odd: float
    news_impact: NewsImpact


@dataclass(frozen=True)
class BankrollRow:
    """Linha da projeção de banca."""

    day: int
    opening_bankroll: float
    target_profit: float
    suggested_stake: float
    closing_bankroll: float


# -----------------------------
# Utilitários básicos
# -----------------------------


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def format_brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def normalize_match_stats(matches: Any) -> list[MatchStat]:
    """Aceita DataFrame pandas, lista de dicts ou lista de MatchStat."""

    if pd is not None and isinstance(matches, pd.DataFrame):
        records = matches.to_dict("records")
        return [MatchStat(**record) for record in records]

    normalized: list[MatchStat] = []
    for item in matches:
        if isinstance(item, MatchStat):
            normalized.append(item)
        elif isinstance(item, dict):
            normalized.append(MatchStat(**item))
        else:
            raise TypeError(
                "Cada item deve ser MatchStat, dict compatível ou um pandas.DataFrame."
            )
    return normalized


def average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.fmean(values))


# -----------------------------
# Motor estatístico
# -----------------------------


def compute_team_metrics(matches: Sequence[MatchStat]) -> TeamMetrics:
    normalized = normalize_match_stats(matches)
    if not normalized:
        raise ValueError("A lista de jogos recentes não pode estar vazia.")

    total_games = len(normalized)
    scored_values = [match.goals_for for match in normalized]
    conceded_values = [match.goals_against for match in normalized]
    total_goals_values = [match.total_goals for match in normalized]
    zero_zero_count = sum(1 for match in normalized if match.is_zero_zero)
    extreme_over_count = sum(1 for match in normalized if match.is_extreme_over)

    return TeamMetrics(
        matches=total_games,
        avg_scored=average(scored_values),
        avg_conceded=average(conceded_values),
        avg_total_goals=average(total_goals_values),
        zero_zero_rate=zero_zero_count / total_games,
        extreme_over_rate=extreme_over_count / total_games,
        zero_zero_count=zero_zero_count,
        extreme_over_count=extreme_over_count,
    )


def _h2h_hit(total_goals: int, interval: GoalsInterval) -> bool:
    if interval is GoalsInterval.RANGE_1_5:
        return 1 <= total_goals <= 5
    return 0 <= total_goals <= 4


def h2h_range_rate(
    matches: Sequence[MatchStat],
    interval: GoalsInterval = GoalsInterval.RANGE_1_5,
) -> Optional[float]:
    normalized = normalize_match_stats(matches)
    if not normalized:
        return None
    hits = sum(1 for match in normalized if _h2h_hit(match.total_goals, interval))
    return hits / len(normalized)


def suggested_market_label(interval: GoalsInterval) -> str:
    if interval is GoalsInterval.RANGE_1_5:
        return "Intervalo 1-5 Gols"
    return "Intervalo 0-4 Gols"


def evaluate_news_texts(texts: Sequence[str]) -> NewsImpact:
    """Heurística simples para ajustar risco com base em notícias.

    Ideia de integração real:
    1. Coletar manchetes/trechos de notícias via API.
    2. Rodar NLP/keyword matching.
    3. Ajustar o score do jogo.

    Sinais positivos para gols:
    - ausência de goleiro titular;
    - ausência de zagueiros/defensores centrais.
    Sinais que favorecem 0x0 ou under:
    - ausência do artilheiro principal;
    - ausência de criadores ofensivos.
    """

    joined = " ".join(texts).lower()
    notes: list[str] = []
    adjustment = 0

    goalkeeper_terms = [
        "goleiro",
        "keeper",
        "goalkeeper",
        "goleiro titular",
        "goleiro reserva",
        "zagueiro",
        "defensor",
        "center-back",
        "centre-back",
        "defence",
        "defender",
    ]
    scorer_terms = [
        "artilheiro",
        "scorer",
        "top scorer",
        "striker",
        "atacante",
        "centroavante",
        "forward",
    ]

    if any(term in joined for term in goalkeeper_terms):
        adjustment += 10
        notes.append("Sinal de possível aumento de gols por ausência/risco defensivo.")

    if any(term in joined for term in scorer_terms):
        adjustment -= 8
        notes.append("Sinal de possível queda de gols por ausência ofensiva.")

    adjustment = int(clamp(adjustment, -20, 20))
    return NewsImpact(risk_adjustment=adjustment, notes=tuple(notes))


def score_matchup(
    home_metrics: TeamMetrics,
    away_metrics: TeamMetrics,
    combined_avg_goals: float,
    h2h_rate: Optional[float],
    news_impact: NewsImpact,
    interval: GoalsInterval,
) -> int:
    score = 0

    # Parte 1: média de gols ideal perto de 2.8
    distance_from_target = abs(combined_avg_goals - TARGET_GOALS_MIDPOINT)
    score += int(clamp(25 - distance_from_target * 12, 0, 25))

    # Parte 2: consistência dos times
    score += int(clamp(15 - (home_metrics.zero_zero_rate * 100) * 0.9, 0, 15))
    score += int(clamp(15 - (away_metrics.zero_zero_rate * 100) * 0.9, 0, 15))

    # Parte 3: proteção contra blowout
    score += int(clamp(10 - (home_metrics.extreme_over_rate * 100) * 1.5, 0, 10))
    score += int(clamp(10 - (away_metrics.extreme_over_rate * 100) * 1.5, 0, 10))

    # Parte 4: H2H (peso um pouco maior no mercado 0-4, mais sensível a 0x0)
    h2h_weight = 22 if interval is GoalsInterval.RANGE_0_4 else 20
    neutral_h2h_bonus = 6 if interval is GoalsInterval.RANGE_0_4 else 8
    if h2h_rate is not None:
        score += int(clamp(h2h_rate * h2h_weight, 0, h2h_weight))
    else:
        score += neutral_h2h_bonus

    # Parte 5: contexto de notícias
    score += news_impact.risk_adjustment

    return int(clamp(score, 0, 100))


def evaluate_matchup(
    home_team: str,
    away_team: str,
    home_matches: Sequence[MatchStat],
    away_matches: Sequence[MatchStat],
    h2h_matches: Sequence[MatchStat] | None = None,
    news_texts: Sequence[str] | None = None,
    goals_interval: GoalsInterval = GoalsInterval.RANGE_1_5,
    suggested_market: str | None = None,
    suggested_odd: float = DEFAULT_ODD_TARGET,
) -> MatchRecommendation:
    home_metrics = compute_team_metrics(home_matches)
    away_metrics = compute_team_metrics(away_matches)
    h2h_matches = h2h_matches or []
    rate = h2h_range_rate(h2h_matches, interval=goals_interval)
    news_impact = evaluate_news_texts(news_texts or [])

    combined_avg_goals = (home_metrics.avg_total_goals + away_metrics.avg_total_goals) / 2

    market_label = suggested_market or suggested_market_label(goals_interval)
    interval_label = "1-5" if goals_interval is GoalsInterval.RANGE_1_5 else "0-4"

    reasons: list[str] = []

    if not (MIN_COMBINED_AVG_GOALS <= combined_avg_goals <= MAX_COMBINED_AVG_GOALS):
        reasons.append(
            f"Média combinada fora da faixa: {combined_avg_goals:.2f} (esperado entre "
            f"{MIN_COMBINED_AVG_GOALS:.1f} e {MAX_COMBINED_AVG_GOALS:.1f})."
        )

    if home_metrics.zero_zero_rate > MAX_ZERO_ZERO_RATE:
        reasons.append(
            f"{home_team} tem {format_pct(home_metrics.zero_zero_rate)} de 0x0, acima do limite."
        )

    if away_metrics.zero_zero_rate > MAX_ZERO_ZERO_RATE:
        reasons.append(
            f"{away_team} tem {format_pct(away_metrics.zero_zero_rate)} de 0x0, acima do limite."
        )

    if home_metrics.extreme_over_rate > MAX_EXTREME_GOALS_RATE:
        reasons.append(
            f"{home_team} teve {format_pct(home_metrics.extreme_over_rate)} de jogos com mais de 5.5 gols (6+)."
        )

    if away_metrics.extreme_over_rate > MAX_EXTREME_GOALS_RATE:
        reasons.append(
            f"{away_team} teve {format_pct(away_metrics.extreme_over_rate)} de jogos com mais de 5.5 gols (6+)."
        )

    if rate is not None and rate < MIN_H2H_RANGE_RATE:
        reasons.append(
            f"H2H abaixo da consistência mínima: {format_pct(rate)} dentro do intervalo {interval_label} gols."
        )

    approved = len(reasons) == 0
    confidence = score_matchup(
        home_metrics,
        away_metrics,
        combined_avg_goals,
        rate,
        news_impact,
        interval=goals_interval,
    )

    if not approved:
        confidence = min(confidence, 69)

    return MatchRecommendation(
        home_team=home_team,
        away_team=away_team,
        approved=approved,
        confidence_score=confidence,
        combined_avg_goals=combined_avg_goals,
        team_home_metrics=home_metrics,
        team_away_metrics=away_metrics,
        h2h_range_rate=rate,
        h2h_matches=len(h2h_matches),
        reasons=tuple(reasons),
        suggested_market=market_label,
        suggested_odd=suggested_odd,
        news_impact=news_impact,
    )


def rank_recommendations(
    recommendations: Sequence[MatchRecommendation],
) -> list[MatchRecommendation]:
    return sorted(recommendations, key=lambda item: item.confidence_score, reverse=True)


def pick_best_recommendation(
    recommendations: Sequence[MatchRecommendation],
) -> Optional[MatchRecommendation]:
    approved = [recommendation for recommendation in recommendations if recommendation.approved]
    if not approved:
        return None
    return rank_recommendations(approved)[0]


# -----------------------------
# Banca e juros compostos
# -----------------------------


def project_bankroll(
    initial_balance: float,
    daily_target: float = DEFAULT_DAILY_TARGET,
    odd_target: float = DEFAULT_ODD_TARGET,
    days: int = DEFAULT_DAYS,
) -> list[BankrollRow]:
    if initial_balance <= 0:
        raise ValueError("O saldo inicial precisa ser maior que zero.")
    if daily_target <= 0:
        raise ValueError("A meta diária precisa ser maior que zero.")
    if odd_target <= 1:
        raise ValueError("A odd alvo precisa ser maior que 1.")
    if days <= 0:
        raise ValueError("A quantidade de dias precisa ser maior que zero.")

    rows: list[BankrollRow] = []
    bankroll = float(initial_balance)

    for day in range(1, days + 1):
        target_profit = bankroll * daily_target
        suggested_stake = target_profit / (odd_target - 1)
        closing_bankroll = bankroll + target_profit

        rows.append(
            BankrollRow(
                day=day,
                opening_bankroll=bankroll,
                target_profit=target_profit,
                suggested_stake=suggested_stake,
                closing_bankroll=closing_bankroll,
            )
        )

        bankroll = closing_bankroll

    return rows


def bankroll_status_message(day: int, target_profit: float) -> str:
    return f"Você está no Dia {day}. Objetivo de hoje: {format_brl(target_profit)}."


# -----------------------------
# Integração com dados externos
# -----------------------------


def fetch_news_from_api(
    api_url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> list[str]:
    """Busca notícias/trechos em uma API externa.

    Estrutura esperada:
    - api_url: endpoint JSON.
    - params: parâmetros da query.
    - headers: cabeçalhos de autenticação.

    Retorno:
    - lista de strings com títulos, resumos ou headlines.

    Exemplos de uso:
    - NewsAPI;
    - API do Google News via agregador próprio;
    - endpoint do seu pipeline NLP.
    """
    if requests is None:
        raise RuntimeError("A biblioteca requests não está instalada.")

    response = requests.get(api_url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        return [str(item) for item in payload]

    if isinstance(payload, dict):
        for key in ("articles", "items", "results", "news"):
            items = payload.get(key)
            if isinstance(items, list):
                extracted: list[str] = []
                for item in items:
                    if isinstance(item, str):
                        extracted.append(item)
                    elif isinstance(item, dict):
                        extracted.append(
                            str(
                                item.get("title")
                                or item.get("headline")
                                or item.get("description")
                                or item.get("summary")
                                or item
                            )
                        )
                    else:
                        extracted.append(str(item))
                return extracted

        return [str(payload)]

    return [str(payload)]


def fetch_football_data_api(
    api_url: str,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
) -> Any:
    """Esqueleto para integrar uma API de estatísticas de futebol.

    Você pode apontar isso para:
    - football-data-api;
    - APIs pagas com dados de eventos e placares;
    - endpoint próprio que consolide estatísticas e notícias.
    """
    if requests is None:
        raise RuntimeError("A biblioteca requests não está instalada.")

    response = requests.get(api_url, params=params, headers=headers, timeout=20)
    response.raise_for_status()
    return response.json()


# -----------------------------
# Renderização
# -----------------------------


def render_dataframe(rows: Sequence[dict[str, Any]]) -> str:
    if pd is not None:
        frame = pd.DataFrame(rows)
        return frame.to_string(index=False)

    if not rows:
        return ""

    headers = list(rows[0].keys())
    widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            widths[header] = max(widths[header], len(str(row.get(header, ""))))

    line_parts = []
    header_line = " | ".join(header.ljust(widths[header]) for header in headers)
    separator = "-+-".join("-" * widths[header] for header in headers)
    line_parts.append(header_line)
    line_parts.append(separator)

    for row in rows:
        line_parts.append(
            " | ".join(str(row.get(header, "")).ljust(widths[header]) for header in headers)
        )

    return "\n".join(line_parts)


def recommendation_to_rows(recommendation: MatchRecommendation) -> list[dict[str, Any]]:
    return [
        {
            "Confronto": f"{recommendation.home_team} x {recommendation.away_team}",
            "Aprovado": "Sim" if recommendation.approved else "Não",
            "Confiança": recommendation.confidence_score,
            "Média Comb.": f"{recommendation.combined_avg_goals:.2f}",
            "H2H (intervalo)": "N/D"
            if recommendation.h2h_range_rate is None
            else format_pct(recommendation.h2h_range_rate),
            "Mercado": recommendation.suggested_market,
            "Odd Alvo": f"{recommendation.suggested_odd:.2f}",
        }
    ]


def bankroll_rows_to_dicts(rows: Sequence[BankrollRow]) -> list[dict[str, Any]]:
    return [
        {
            "Dia": row.day,
            "Banca Abertura": format_brl(row.opening_bankroll),
            "Lucro Meta": format_brl(row.target_profit),
            "Entrada Sugerida": format_brl(row.suggested_stake),
            "Banca Fechamento": format_brl(row.closing_bankroll),
        }
        for row in rows
    ]


# -----------------------------
# Demonstração local
# -----------------------------


def build_sample_data() -> tuple[
    list[MatchStat],
    list[MatchStat],
    list[MatchStat],
    list[MatchStat],
    list[MatchStat],
    list[MatchStat],
]:
    home_a = [
        MatchStat(2, 1, "Team B"),
        MatchStat(1, 1, "Team C"),
        MatchStat(3, 1, "Team D"),
        MatchStat(1, 0, "Team E"),
        MatchStat(2, 2, "Team F"),
        MatchStat(1, 2, "Team G"),
        MatchStat(2, 0, "Team H"),
        MatchStat(1, 1, "Team I"),
        MatchStat(2, 1, "Team J"),
        MatchStat(1, 0, "Team K"),
    ]

    away_a = [
        MatchStat(1, 1, "Team L"),
        MatchStat(2, 1, "Team M"),
        MatchStat(1, 0, "Team N"),
        MatchStat(2, 2, "Team O"),
        MatchStat(1, 1, "Team P"),
        MatchStat(3, 1, "Team Q"),
        MatchStat(2, 0, "Team R"),
        MatchStat(1, 2, "Team S"),
        MatchStat(1, 1, "Team T"),
        MatchStat(2, 1, "Team U"),
    ]

    h2h_a = [
        MatchStat(1, 1, "Team B"),
        MatchStat(2, 1, "Team B"),
        MatchStat(3, 0, "Team B"),
        MatchStat(1, 0, "Team B"),
        MatchStat(2, 2, "Team B"),
    ]

    home_b = [
        MatchStat(0, 0, "Team V"),
        MatchStat(1, 0, "Team W"),
        MatchStat(1, 0, "Team X"),
        MatchStat(0, 1, "Team Y"),
        MatchStat(1, 1, "Team Z"),
        MatchStat(0, 0, "Team AA"),
        MatchStat(2, 1, "Team AB"),
        MatchStat(1, 1, "Team AC"),
        MatchStat(0, 0, "Team AD"),
        MatchStat(1, 2, "Team AE"),
    ]

    away_b = [
        MatchStat(1, 0, "Team AF"),
        MatchStat(0, 0, "Team AG"),
        MatchStat(1, 1, "Team AH"),
        MatchStat(0, 1, "Team AI"),
        MatchStat(2, 0, "Team AJ"),
        MatchStat(0, 0, "Team AK"),
        MatchStat(1, 1, "Team AL"),
        MatchStat(0, 0, "Team AM"),
        MatchStat(1, 0, "Team AN"),
        MatchStat(0, 1, "Team AO"),
    ]

    h2h_b = [
        MatchStat(0, 0, "Team V"),
        MatchStat(1, 0, "Team V"),
        MatchStat(0, 1, "Team V"),
        MatchStat(1, 1, "Team V"),
        MatchStat(2, 0, "Team V"),
    ]

    return home_a, away_a, h2h_a, home_b, away_b, h2h_b


def format_ticket_suggestion(recommendation: MatchRecommendation) -> str:
    return (
        f"Entrada sugerida: {recommendation.suggested_market} | "
        f"Odd Alvo: {recommendation.suggested_odd:.2f}"
    )


def integracao_contexto_inteligente_doc() -> str:
    """Texto de referência para integrar notícias / NLP (imprimível no relatório)."""

    return """
=== Contexto inteligente (notícias e NLP) ===

Objetivo: enriquecer o motor com ausências e dúvidas de elenco antes do apito inicial.

1) Coleta de dados
   - NewsAPI / GNews: busque por nome do clube + 'injury' ou 'suspension' nas 48h do jogo.
   - RSS oficial do clube ou site esportivo (respeite robots.txt e termos de uso).
   - Opcional: API de escalações (ex.: fornecedores esportivos) cruzada com lista de lesionados.

2) Processamento
   - Camada simples (já no script): evaluate_news_texts() com palavras-chave em PT/EN.
   - Camada avançada: envie manchetes para um LLM com prompt fixo pedindo JSON:
     {"goalkeeper_out": bool, "key_defenders_out": int, "top_scorer_out": bool, "quotes": []}
   - Camada híbrida: NER (spaCy) para detectar nomes de jogadores + match contra o plantel.

3) Risco para Total de Gols
   - Goleiro ou zagueiros titulares fora -> tendência a mais gols (defesa mais frágil):
     aumente cautela no mercado 0-4; pode subir levemente a confiança no 1-5 se o restante
     do modelo for sólido (ajuste feito em evaluate_news_texts).
   - Artilheiro ou ponta referência fora -> maior risco de 0x0 ou jogo truncado:
     penalize a confiança e considere filtro extra manual antes de operar.

4) Encaixe técnico
   - Implemente fetch_news_from_api(url, params, headers) ou um cliente dedicado.
   - Concatene títulos relevantes e passe como news_texts= em evaluate_matchup().
"""


def build_text_report(
    recommendations: Sequence[MatchRecommendation],
    bankroll_plan: Sequence[BankrollRow],
    current_day: int,
    include_ia_doc: bool = True,
) -> str:
    ranked = rank_recommendations(recommendations)
    best = pick_best_recommendation(recommendations)
    lines: list[str] = []

    lines.append("=== MELHORES CANDIDATOS ===")
    lines.append(render_dataframe([row for rec in ranked for row in recommendation_to_rows(rec)]))

    if best is None:
        lines.append("\nNenhum jogo aprovado pelos filtros principais.")
    else:
        lines.append("\n=== JOGO DO DIA ===")
        lines.append(f"{best.home_team} x {best.away_team}")
        lines.append(f"Pontuação de Confiança: {best.confidence_score}/100")
        lines.append(f"Sugestão de Bilhete: {format_ticket_suggestion(best)}")
        day = max(1, min(current_day, len(bankroll_plan)))
        target = bankroll_plan[day - 1].target_profit
        lines.append(f"Status da Meta: {bankroll_status_message(day, target_profit=target)}")
        if best.news_impact.notes:
            lines.append("\nContexto (notícias / heurística):")
            for note in best.news_impact.notes:
                lines.append(f"- {note}")
        if best.reasons:
            lines.append("\nAlertas / reprovação:")
            for reason in best.reasons:
                lines.append(f"- {reason}")

    lines.append("\n=== PROJEÇÃO DE BANCA (30 DIAS, REINVESTINDO O LUCRO DA META) ===")
    lines.append(
        "Cada dia: lucro alvo = banca abertura × meta diária; entrada sugerida = lucro / (odd-1); "
        "banca fecha com lucro incorporado (cenário teórico se a meta for atingida todos os dias)."
    )
    lines.append(render_dataframe(bankroll_rows_to_dicts(list(bankroll_plan))))

    if include_ia_doc:
        lines.append(integracao_contexto_inteligente_doc())

    lines.append(
        "\nFonte de dados: use football-data.org (veja football_data_provider.py) ou "
        "scrape apenas onde for legal; o pacote PyPI 'football-data-api' costuma ser "
        "wrapper/redirecionamento — verifique o repositório e a licença antes de usar."
    )
    return "\n".join(lines).strip() + "\n"


def write_report_file(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main() -> None:
    home_a, away_a, h2h_a, home_b, away_b, h2h_b = build_sample_data()

    recommendations = [
        evaluate_matchup(
            "Alpha FC",
            "Beta United",
            home_a,
            away_a,
            h2h_a,
            news_texts=[
                "Goalkeeper ruled out after training injury.",
                "Main striker expected to start.",
            ],
        ),
        evaluate_matchup(
            "Gamma City",
            "Delta Town",
            home_b,
            away_b,
            h2h_b,
            news_texts=[
                "Top scorer unavailable and defensive line with doubts.",
            ],
        ),
    ]

    initial_balance = float(os.getenv("BANKROLL_INITIAL", "10"))
    current_day = int(os.getenv("BANKROLL_CURRENT_DAY", "1"))
    bankroll_plan = project_bankroll(
        initial_balance=initial_balance,
        daily_target=DEFAULT_DAILY_TARGET,
        odd_target=DEFAULT_ODD_TARGET,
        days=DEFAULT_DAYS,
    )

    report = build_text_report(
        recommendations=recommendations,
        bankroll_plan=bankroll_plan,
        current_day=current_day,
        include_ia_doc=True,
    )
    print(report, end="")

    outfile = os.getenv("STRATEGY_REPORT_PATH", "").strip()
    if outfile:
        write_report_file(outfile, report)
        print(f"\nRelatório salvo em: {outfile}")


if __name__ == "__main__":
    main()
