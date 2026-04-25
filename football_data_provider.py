"""Integração com dados reais de futebol via football-data.org.

Este módulo foi criado para substituir os dados simulados por partidas atuais,
últimos jogos e histórico direto entre dois times.

Uso esperado com variáveis de ambiente:

- FOOTBALL_DATA_API_KEY: token da API
- FOOTBALL_DATA_COMPETITION: código do campeonato, ex. PL, PD, SA, BL1, FL1
- HOME_TEAM_ID: id do time da casa
- AWAY_TEAM_ID: id do time visitante
- HOME_TEAM_NAME: nome opcional do time da casa
- AWAY_TEAM_NAME: nome opcional do time visitante
- FOOTBALL_DATA_MATCHDAY: número da rodada — quando definido junto com a chave e o código
  da competição, o painel web analisa **todos os jogos** da rodada (últimos jogos + H2H por confronto).

A partir disso, o painel pode buscar:
- jogos recentes de cada time;
- confronto direto;
- nome do campeonato;
- status real do sistema usando os dados atuais.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import os
import re
import time
from typing import Any, Optional

try:
    import requests  # type: ignore
except Exception:  # pragma: no cover - opcional
    requests = None

from football_total_goals_strategy import MatchRecommendation, MatchStat, evaluate_matchup


DEFAULT_BASE_URL = "https://api.football-data.org/v4"
DEFAULT_LOOKBACK_MATCHES = 10


@dataclass(frozen=True)
class LiveMatchupData:
    """Dados reais consolidados para alimentar o motor de análise."""

    competition_code: str
    competition_name: str
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str
    home_matches: list[MatchStat]
    away_matches: list[MatchStat]
    h2h_matches: list[MatchStat]


@dataclass(frozen=True)
class CompetitionFixture:
    """Jogo individual de uma rodada da competição."""

    match_id: str
    utc_date: str
    status: str
    home_team_id: int
    home_team_name: str
    away_team_id: int
    away_team_name: str


@dataclass(frozen=True)
class CompetitionMatchdayData:
    """Dados de uma rodada completa de competição."""

    competition_code: str
    competition_name: str
    matchday: int
    fixtures: list[CompetitionFixture]


def _require_requests() -> None:
    if requests is None:
        raise RuntimeError("A biblioteca requests não está instalada.")


def _iso_date(value: date | str | None) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return value


def _match_datetime(match: dict[str, Any]) -> datetime:
    raw_value = str(match.get("utcDate") or "")
    if not raw_value:
        return datetime.min
    normalized = raw_value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min


def _extract_matches(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        matches = payload.get("matches")
        if isinstance(matches, list):
            return [item for item in matches if isinstance(item, dict)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _team_name(team: Any) -> str:
    if isinstance(team, dict):
        return str(team.get("name") or team.get("shortName") or team.get("tla") or "")
    return ""


def _team_id(team: Any) -> Optional[int]:
    if isinstance(team, dict):
        value = team.get("id")
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _competition_name(match: dict[str, Any]) -> str:
    competition = match.get("competition")
    if isinstance(competition, dict):
        return str(competition.get("name") or competition.get("code") or "")
    return ""


def _match_to_fixture(match: dict[str, Any]) -> CompetitionFixture:
    home_team = match.get("homeTeam")
    away_team = match.get("awayTeam")

    return CompetitionFixture(
        match_id=str(match.get("id") or ""),
        utc_date=str(match.get("utcDate") or ""),
        status=str(match.get("status") or ""),
        home_team_id=_team_id(home_team) or 0,
        home_team_name=_team_name(home_team),
        away_team_id=_team_id(away_team) or 0,
        away_team_name=_team_name(away_team),
    )


class FootballDataClient:
    """Cliente simples para football-data.org."""

    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: int = 20,
        request_delay: float = 0.5,  # Delay entre requisições (segundos)
    ) -> None:
        _require_requests()
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.request_delay = request_delay
        self._last_request_time = 0.0

    @classmethod
    def from_env(cls) -> "FootballDataClient":
        api_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Defina FOOTBALL_DATA_API_KEY no ambiente.")
        base_url = os.getenv("FOOTBALL_DATA_BASE_URL", DEFAULT_BASE_URL).strip()
        return cls(api_key=api_key, base_url=base_url)

    def _request(
        self,
        path: str,
        params: Optional[dict[str, Any]] = None,
        headers: Optional[dict[str, str]] = None,
        retry_count: int = 0,
        max_retries: int = 3,
    ) -> Any:
        _require_requests()
        
        # Aplicar throttling: aguardar delay entre requisições
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()
        
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_headers = {"X-Auth-Token": self.api_key}
        if headers:
            request_headers.update(headers)
        response = requests.get(url, headers=request_headers, params=params, timeout=self.timeout)

        # Tratamento especial para Rate Limit (429)
        if response.status_code == 429:
            # Extrair tempo de espera da resposta
            wait_time = 2 ** (retry_count + 1)  # Exponential backoff: 2, 4, 8, 16 segundos
            
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    message = str(payload.get("message") or "")
                    if "Wait" in message and "seconds" in message:
                        # Tentar extrair o tempo exato (ex: "Wait 17 seconds")
                        match = re.search(r"Wait\s+(\d+)\s+seconds", message)
                        if match:
                            wait_time = int(match.group(1))
            except Exception:
                pass
            
            if retry_count < max_retries:
                print(f"⏳ Rate limit atingido. Aguardando {wait_time} segundos... "
                      f"(tentativa {retry_count + 1}/{max_retries})")
                time.sleep(wait_time)
                return self._request(path, params, headers, retry_count=retry_count + 1, max_retries=max_retries)
            else:
                raise RuntimeError(f"Rate limit (429) — Limite de tentativas atingido. Aguarde 1 minuto antes de tentar novamente.")

        # Melhora o diagnóstico no painel (a API costuma retornar JSON com "message").
        if not response.ok:
            details = ""
            try:
                payload = response.json()
                if isinstance(payload, dict):
                    details = str(payload.get("message") or payload.get("error") or payload)
                else:
                    details = str(payload)
            except Exception:
                details = (response.text or "").strip()

            details = details[:500] if details else ""
            suffix = f" — {details}" if details else ""
            raise RuntimeError(f"HTTP {response.status_code} em {url}{suffix}")

        return response.json()

    def list_competitions(self) -> list[dict[str, Any]]:
        payload = self._request("/competitions")
        if isinstance(payload, dict):
            items = payload.get("competitions")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return []

    def get_competition(self, competition_code: str) -> dict[str, Any]:
        payload = self._request(f"/competitions/{competition_code}")
        if isinstance(payload, dict):
            return payload
        raise ValueError(f"Resposta inesperada para competição {competition_code!r}.")

    def get_current_matchday(self, competition_code: str) -> Optional[int]:
        """Retorna o número da rodada atual de uma competição."""
        try:
            comp = self.get_competition(competition_code)
            
            # Tentar várias chaves possíveis
            for key in ("currentSeason", "season"):
                season = comp.get(key)
                if isinstance(season, dict):
                    matchday = season.get("currentMatchday")
                    if isinstance(matchday, int) and matchday > 0:
                        return matchday
            
            # Fallback: buscar o maior matchday dos jogos recentes
            matches = self.get_competition_matches(
                competition_code=competition_code,
                status=None
            )
            if matches:
                # Ordenar por data mais recente
                sorted_matches = sorted(matches, key=_match_datetime, reverse=True)
                for match in sorted_matches[:1]:
                    matchday = match.get("season", {}).get("currentMatchday")
                    if isinstance(matchday, int):
                        return matchday
                    # Ou tentar extrair do match
                    md = match.get("matchday")
                    if isinstance(md, int):
                        return md
            
            return None
        except Exception:
            return None

    def get_competition_teams(self, competition_code: str) -> list[dict[str, Any]]:
        payload = self._request(f"/competitions/{competition_code}/teams")
        teams = payload.get("teams") if isinstance(payload, dict) else None
        if isinstance(teams, list):
            return [item for item in teams if isinstance(item, dict)]
        return []

    def get_competition_matches(
        self,
        competition_code: str,
        status: str | None = "FINISHED",
        matchday: int | None = None,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
        unfold_goals: bool = False,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if status is not None:
            params["status"] = status
        if matchday is not None:
            params["matchday"] = matchday
        iso_from = _iso_date(date_from)
        iso_to = _iso_date(date_to)
        if iso_from:
            params["dateFrom"] = iso_from
        if iso_to:
            params["dateTo"] = iso_to

        request_headers: dict[str, str] = {}
        if unfold_goals:
            request_headers["X-Unfold-Goals"] = "true"

        payload = self._request(
            f"/competitions/{competition_code}/matches",
            params=params,
            headers=request_headers or None,
        )
        return _extract_matches(payload)

    def get_competition_matchday(
        self,
        competition_code: str,
        matchday: int,
        unfold_goals: bool = True,
    ) -> CompetitionMatchdayData:
        competition = self.get_competition(competition_code)
        competition_name = str(competition.get("name") or competition_code)
        matches = self.get_competition_matches(
            competition_code=competition_code,
            status=None,
            matchday=matchday,
            unfold_goals=unfold_goals,
        )
        fixtures = [_match_to_fixture(match) for match in matches]
        return CompetitionMatchdayData(
            competition_code=competition_code,
            competition_name=competition_name,
            matchday=matchday,
            fixtures=fixtures,
        )

    def get_team_matches(
        self,
        team_id: int,
        status: str = "FINISHED",
        date_from: date | str | None = None,
        date_to: date | str | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"status": status}
        iso_from = _iso_date(date_from)
        iso_to = _iso_date(date_to)
        if iso_from:
            params["dateFrom"] = iso_from
        if iso_to:
            params["dateTo"] = iso_to

        payload = self._request(f"/teams/{team_id}/matches", params=params)
        matches = _extract_matches(payload)
        return sorted(matches, key=_match_datetime, reverse=True)

    def get_team_recent_stats(
        self,
        team_id: int,
        limit: int = DEFAULT_LOOKBACK_MATCHES,
        status: str = "FINISHED",
    ) -> list[MatchStat]:
        matches = self.get_team_matches(team_id=team_id, status=status)
        return [stat for stat in (self._match_to_stat(match, team_id) for match in matches) if stat][:limit]

    def get_head_to_head_stats(
        self,
        home_team_id: int,
        away_team_id: int,
        limit: int = DEFAULT_LOOKBACK_MATCHES,
    ) -> list[MatchStat]:
        matches = self.get_team_matches(team_id=home_team_id, status="FINISHED")
        stats: list[MatchStat] = []
        for match in matches:
            stat = self._match_to_stat(match, home_team_id)
            if stat is None:
                continue
            opponent_id = self._opponent_id(match, home_team_id)
            if opponent_id != away_team_id:
                continue
            stats.append(stat)
            if len(stats) >= limit:
                break
        return stats

    def _opponent_id(self, match: dict[str, Any], team_id: int) -> Optional[int]:
        home_team = match.get("homeTeam")
        away_team = match.get("awayTeam")
        home_team_id = _team_id(home_team)
        away_team_id = _team_id(away_team)

        if home_team_id == team_id:
            return away_team_id
        if away_team_id == team_id:
            return home_team_id
        return None

    def _match_to_stat(self, match: dict[str, Any], team_id: int) -> Optional[MatchStat]:
        home_team = match.get("homeTeam")
        away_team = match.get("awayTeam")
        home_team_id = _team_id(home_team)
        away_team_id = _team_id(away_team)

        score = match.get("score")
        full_time = score.get("fullTime") if isinstance(score, dict) else None
        if not isinstance(full_time, dict):
            return None

        home_goals = full_time.get("home")
        away_goals = full_time.get("away")
        if home_goals is None or away_goals is None:
            return None

        try:
            home_goals_int = int(home_goals)
            away_goals_int = int(away_goals)
        except (TypeError, ValueError):
            return None

        if home_team_id == team_id:
            opponent_name = _team_name(away_team)
            return MatchStat(
                goals_for=home_goals_int,
                goals_against=away_goals_int,
                opponent=opponent_name,
                competition=_competition_name(match),
            )

        if away_team_id == team_id:
            opponent_name = _team_name(home_team)
            return MatchStat(
                goals_for=away_goals_int,
                goals_against=home_goals_int,
                opponent=opponent_name,
                competition=_competition_name(match),
            )

        return None


def resolve_team_name(
    client: FootballDataClient,
    competition_code: str,
    team_id: int,
    fallback_name: Optional[str] = None,
) -> str:
    if fallback_name:
        return fallback_name

    teams = client.get_competition_teams(competition_code)
    for team in teams:
        if _team_id(team) == team_id:
            return _team_name(team) or f"Team {team_id}"

    return f"Team {team_id}"


def analyze_fixtures_list(
    client: FootballDataClient,
    competition_code: str,
    fixtures: list[CompetitionFixture],
    lookback: int = DEFAULT_LOOKBACK_MATCHES,
) -> list[MatchRecommendation]:
    """Avalia uma lista de confrontos (subconjunto da rodada ou várias rodadas).

    Usa cache em memória por requisição para reduzir chamadas à API (importante no plano gratuito).
    """

    team_cache: dict[int, list[MatchStat]] = {}
    h2h_cache: dict[tuple[int, int], list[MatchStat]] = {}

    def team_stats(team_id: int) -> list[MatchStat]:
        if team_id not in team_cache:
            team_cache[team_id] = client.get_team_recent_stats(team_id, limit=lookback)
        return team_cache[team_id]

    def h2h_stats(team_a: int, team_b: int) -> list[MatchStat]:
        lo, hi = (team_a, team_b) if team_a <= team_b else (team_b, team_a)
        key = (lo, hi)
        if key not in h2h_cache:
            h2h_cache[key] = client.get_head_to_head_stats(lo, hi, limit=lookback)
        return h2h_cache[key]

    results: list[MatchRecommendation] = []
    for fixture in fixtures:
        hid, aid = fixture.home_team_id, fixture.away_team_id
        if hid <= 0 or aid <= 0:
            continue

        home_matches = team_stats(hid)
        away_matches = team_stats(aid)
        h2h_matches = h2h_stats(hid, aid)

        home_name = fixture.home_team_name or resolve_team_name(
            client, competition_code=competition_code, team_id=hid
        )
        away_name = fixture.away_team_name or resolve_team_name(
            client, competition_code=competition_code, team_id=aid
        )

        results.append(
            evaluate_matchup(
                home_name,
                away_name,
                home_matches,
                away_matches,
                h2h_matches,
                news_texts=[],
            )
        )

    return results


def analyze_matchday_recommendations(
    client: FootballDataClient,
    competition_code: str,
    matchday_data: CompetitionMatchdayData,
    lookback: int = DEFAULT_LOOKBACK_MATCHES,
) -> list[MatchRecommendation]:
    """Avalia cada confronto da rodada."""

    return analyze_fixtures_list(
        client,
        competition_code,
        matchday_data.fixtures,
        lookback=lookback,
    )


def load_competition_matchday_from_env(
    client: Optional[FootballDataClient] = None,
) -> Optional[CompetitionMatchdayData]:
    """Carrega a rodada da competição informada via variáveis de ambiente."""
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
    competition_code = os.getenv("FOOTBALL_DATA_COMPETITION", "").strip()
    matchday_raw = os.getenv("FOOTBALL_DATA_MATCHDAY", "").strip()

    if not api_key or not competition_code or not matchday_raw:
        return None

    matchday = int(matchday_raw)
    active_client = client or FootballDataClient(api_key=api_key)
    return active_client.get_competition_matchday(
        competition_code=competition_code,
        matchday=matchday,
        unfold_goals=True,
    )


def load_live_matchup_from_env(
    client: Optional[FootballDataClient] = None,
    lookback: int = DEFAULT_LOOKBACK_MATCHES,
) -> Optional[LiveMatchupData]:
    """Carrega um confronto real a partir das variáveis de ambiente.

    Se faltar qualquer variável obrigatória, retorna None para permitir fallback
    automático para os dados simulados.
    """
    api_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
    competition_code = os.getenv("FOOTBALL_DATA_COMPETITION", "").strip()
    home_team_id_raw = os.getenv("HOME_TEAM_ID", "").strip()
    away_team_id_raw = os.getenv("AWAY_TEAM_ID", "").strip()

    if not api_key or not competition_code or not home_team_id_raw or not away_team_id_raw:
        return None

    home_team_id = int(home_team_id_raw)
    away_team_id = int(away_team_id_raw)

    active_client = client or FootballDataClient(api_key=api_key)
    competition = active_client.get_competition(competition_code)
    competition_name = str(competition.get("name") or competition_code)

    home_team_name = resolve_team_name(
        active_client,
        competition_code=competition_code,
        team_id=home_team_id,
        fallback_name=os.getenv("HOME_TEAM_NAME", "").strip() or None,
    )
    away_team_name = resolve_team_name(
        active_client,
        competition_code=competition_code,
        team_id=away_team_id,
        fallback_name=os.getenv("AWAY_TEAM_NAME", "").strip() or None,
    )

    home_matches = active_client.get_team_recent_stats(home_team_id, limit=lookback)
    away_matches = active_client.get_team_recent_stats(away_team_id, limit=lookback)
    h2h_matches = active_client.get_head_to_head_stats(home_team_id, away_team_id, limit=lookback)

    return LiveMatchupData(
        competition_code=competition_code,
        competition_name=competition_name,
        home_team_id=home_team_id,
        home_team_name=home_team_name,
        away_team_id=away_team_id,
        away_team_name=away_team_name,
        home_matches=home_matches,
        away_matches=away_matches,
        h2h_matches=h2h_matches,
    )
