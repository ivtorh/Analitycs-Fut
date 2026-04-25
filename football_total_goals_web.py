"""Painel web local interativo — configuração por formulário e análise em tempo real.

- Chave football-data.org só no servidor (POST /api/session).
- Seleção de competição, rodada e múltiplos jogos (checkboxes).
- POST /api/analyze busca estatísticas na API e aplica o motor de filtros.
- Variáveis de ambiente ainda funcionam como fallback em /status.json quando não há última análise.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from football_data_provider import (
    DEFAULT_BASE_URL,
    FootballDataClient,
    analyze_fixtures_list,
    analyze_matchday_recommendations,
    load_competition_matchday_from_env,
    load_live_matchup_from_env,
)
from football_total_goals_strategy import (
    DEFAULT_DAILY_TARGET,
    DEFAULT_ODD_TARGET,
    MatchRecommendation,
    bankroll_status_message,
    build_sample_data,
    evaluate_matchup,
    format_ticket_suggestion,
    pick_best_recommendation,
    project_bankroll,
    rank_recommendations,
)

_state_lock = threading.Lock()
_server_state: dict[str, Any] = {
    "api_key": None,
    "base_url": None,
    "last_snapshot": None,
}


def _init_state_from_env() -> None:
    env_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
    env_base = os.getenv("FOOTBALL_DATA_BASE_URL", "").strip()
    with _state_lock:
        if env_key:
            _server_state["api_key"] = env_key
        if env_base:
            _server_state["base_url"] = env_base


def _effective_api_key() -> str | None:
    with _state_lock:
        k = (_server_state.get("api_key") or "").strip()
    if k:
        return k
    return os.getenv("FOOTBALL_DATA_API_KEY", "").strip() or None


def _effective_base_url() -> str:
    with _state_lock:
        b = (_server_state.get("base_url") or "").strip()
    if b:
        return b.rstrip("/")
    return os.getenv("FOOTBALL_DATA_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/") or DEFAULT_BASE_URL


def get_api_client() -> FootballDataClient:
    key = _effective_api_key()
    if not key:
        raise ValueError(
            "Nenhuma chave configurada. Informe o token football-data.org no painel "
            "ou defina FOOTBALL_DATA_API_KEY."
        )
    return FootballDataClient(api_key=key, base_url=_effective_base_url())


def _fixtures_to_rows(fixtures: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "match_id": fixture.match_id,
            "utc_date": fixture.utc_date,
            "status": fixture.status,
            "home_team_name": fixture.home_team_name,
            "away_team_name": fixture.away_team_name,
        }
        for fixture in fixtures
    ]


def pack_snapshot(
    recommendations: list[MatchRecommendation],
    *,
    data_source: str,
    analysis_mode: str,
    analysis_error: str | None,
    competition_name: str,
    fixture_label: str,
    matchday_label: str | None,
    competition_fixtures: list[dict[str, Any]],
    bankroll_initial: float,
    bankroll_day: int,
) -> dict[str, Any]:
    ranked = rank_recommendations(recommendations)
    best = pick_best_recommendation(recommendations)
    bankroll_plan = project_bankroll(
        initial_balance=bankroll_initial,
        daily_target=DEFAULT_DAILY_TARGET,
        odd_target=DEFAULT_ODD_TARGET,
        days=30,
    )
    day_clamped = max(1, min(int(bankroll_day), len(bankroll_plan)))
    goal_message = bankroll_status_message(day_clamped, bankroll_plan[day_clamped - 1].target_profit)

    approved_count = sum(1 for r in recommendations if r.approved)
    rejected_count = len(recommendations) - approved_count
    system_status = "APROVADO" if best is not None else "REPROVADO"
    system_class = "ok" if best is not None else "bad"

    if best is None:
        best_payload: dict[str, Any] = {
            "status": "Nenhum jogo aprovado",
            "confidence": 0,
            "market": "N/A",
            "odd_target": 0.0,
            "reason_count": 0,
            "reasons": [],
            "ticket_line": "",
        }
    else:
        best_payload = {
            "status": f"{best.home_team} x {best.away_team}",
            "confidence": best.confidence_score,
            "market": best.suggested_market,
            "odd_target": best.suggested_odd,
            "reason_count": len(best.reasons),
            "reasons": list(best.reasons),
            "ticket_line": format_ticket_suggestion(best),
        }

    return {
        "data_source": data_source,
        "analysis_mode": analysis_mode,
        "analysis_error": analysis_error,
        "competition_name": competition_name,
        "fixture_label": fixture_label,
        "matchday_label": matchday_label,
        "competition_fixtures": competition_fixtures,
        "system_status": system_status,
        "system_class": system_class,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "best": best_payload,
        "ranked": [
            {
                "match": f"{item.home_team} x {item.away_team}",
                "approved": item.approved,
                "confidence": item.confidence_score,
                "combined_avg_goals": round(item.combined_avg_goals, 2),
                "market": item.suggested_market,
                "odd_target": item.suggested_odd,
                "reasons": list(item.reasons),
            }
            for item in ranked
        ],
        "bankroll": [
            {
                "day": row.day,
                "opening_bankroll": row.opening_bankroll,
                "target_profit": row.target_profit,
                "suggested_stake": row.suggested_stake,
                "closing_bankroll": row.closing_bankroll,
            }
            for row in bankroll_plan[:10]
        ],
        "goal_message": goal_message,
    }


def build_system_snapshot() -> dict[str, Any]:
    """Compatível com uso só por variáveis de ambiente (sem UI)."""

    competition_matchday = load_competition_matchday_from_env()
    live_data = load_live_matchup_from_env()
    competition_fixtures: list[dict[str, Any]] = []

    data_source = "Demonstração local"
    competition_name = "Dados simulados"
    fixture_label = "Alpha FC x Beta United"
    matchday_label: str | None = None
    analysis_mode = "demo"
    analysis_error: str | None = None
    recommendations: list[MatchRecommendation] = []

    if competition_matchday is not None and competition_matchday.fixtures:
        competition_name = competition_matchday.competition_name
        matchday_label = f"Rodada {competition_matchday.matchday}"
        fixture_label = matchday_label
        competition_fixtures = _fixtures_to_rows(competition_matchday.fixtures)
        try:
            client = get_api_client()
            recommendations = analyze_matchday_recommendations(
                client,
                competition_matchday.competition_code,
                competition_matchday,
            )
            if recommendations:
                analysis_mode = "matchday"
                data_source = "API real (rodada completa)"
                fixture_label = f"{matchday_label} — {len(recommendations)} confronto(s) analisado(s)"
        except Exception as exc:  # noqa: BLE001
            analysis_error = str(exc)
            recommendations = []

    if (
        not recommendations
        and live_data is not None
        and live_data.home_matches
        and live_data.away_matches
    ):
        recommendations = [
            evaluate_matchup(
                live_data.home_team_name,
                live_data.away_team_name,
                live_data.home_matches,
                live_data.away_matches,
                live_data.h2h_matches,
                news_texts=[],
            )
        ]
        analysis_mode = "single"
        data_source = "API real (confronto único)"
        competition_name = live_data.competition_name
        fixture_label = f"{live_data.home_team_name} x {live_data.away_team_name}"

    if not recommendations:
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
        analysis_mode = "demo"
        data_source = "Demonstração local"
        fixture_label = "Alpha FC x Beta United (exemplo)"
        if competition_matchday is None:
            competition_name = "Dados simulados"
            matchday_label = None
            competition_fixtures = []

    initial_balance = float(os.getenv("BANKROLL_INITIAL", "10"))
    current_day = int(os.getenv("BANKROLL_CURRENT_DAY", "1"))

    return pack_snapshot(
        recommendations,
        data_source=data_source,
        analysis_mode=analysis_mode,
        analysis_error=analysis_error,
        competition_name=competition_name,
        fixture_label=fixture_label,
        matchday_label=matchday_label,
        competition_fixtures=competition_fixtures,
        bankroll_initial=initial_balance,
        bankroll_day=current_day,
    )


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def build_interactive_html() -> str:
    return """<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Total de Gols — Painel interativo</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Corrige legibilidade de <option> em alguns navegadores quando o select é estilizado */
    select, option { color: #0f172a; background-color: #ffffff; }
    select { color-scheme: light; }
  </style>
</head>
<body class="bg-slate-50 text-slate-900">
  <div class="mx-auto max-w-6xl px-4 py-10">
    <div class="mb-8">
      <div class="inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-2 text-sm font-semibold text-blue-700 ring-1 ring-blue-100">
        Total de Gols • Painel local
      </div>
      <h1 class="mt-4 text-3xl font-extrabold tracking-tight">Painel interativo</h1>
      <p class="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
        Configure a chave da API <span class="font-semibold">football-data.org</span> (fica apenas no servidor local),
        escolha campeonato e rodada, selecione <span class="font-semibold">vários</span> jogos e rode a análise em tempo real.
      </p>
    </div>

    <div id="globalBanner" class="mb-4"></div>

    <div class="grid grid-cols-1 gap-4">
      <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <h2 class="text-base font-bold">1) Chave da API</h2>
        <p class="mt-1 text-sm text-slate-600">
          Obtenha o token em
          <a class="font-semibold text-blue-700 hover:text-blue-800 hover:underline" href="https://www.football-data.org/client/register" target="_blank" rel="noopener">
            football-data.org
          </a>.
          Se você já usa <code class="rounded bg-slate-100 px-1.5 py-0.5 text-[12px]">FOOTBALL_DATA_API_KEY</code> no ambiente, pode deixar em branco.
        </p>

        <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label for="apiKey" class="text-sm font-semibold text-slate-700">Token (X-Auth-Token)</label>
            <input type="password" id="apiKey" autocomplete="off" placeholder="Cole o token"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
          </div>
          <div>
            <label for="baseUrl" class="text-sm font-semibold text-slate-700">URL base (opcional)</label>
            <input type="text" id="baseUrl" placeholder="https://api.football-data.org/v4"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
          </div>
        </div>

        <div class="mt-4 flex flex-wrap items-center gap-3">
          <button type="button" id="btnSaveKey"
            class="inline-flex items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-200">
            Salvar chave no servidor local
          </button>
          <span class="text-sm text-slate-600" id="keyStatus"></span>
        </div>
      </div>

      <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <h2 class="text-base font-bold">2) Campeonato</h2>
        <div class="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" id="btnLoadComps"
            class="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-100">
            Listar competições
          </button>
          <button type="button" id="btnLoadMeta"
            class="inline-flex items-center justify-center rounded-xl bg-slate-900 px-4 py-2 text-sm font-bold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-slate-200">
            Carregar temporada
          </button>
        </div>

        <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label for="competition" class="text-sm font-semibold text-slate-700">Competição</label>
            <select id="competition"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"></select>
            <p class="mt-2 text-sm text-slate-600" id="compMeta"></p>
          </div>
          <div class="rounded-xl bg-blue-50 p-4 ring-1 ring-blue-100">
            <p class="text-sm font-semibold text-blue-900">Dica</p>
            <p class="mt-1 text-sm text-blue-800">
              Se a lista vier vazia, normalmente é limite do plano da API ou token ausente/ inválido.
            </p>
          </div>
        </div>
      </div>

      <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <h2 class="text-base font-bold">3) Rodada e jogos (multi-seleção)</h2>

        <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label for="matchday" class="text-sm font-semibold text-slate-700">Rodada (select)</label>
            <select id="matchday"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"></select>
          </div>
          <div>
            <label for="matchdayNum" class="text-sm font-semibold text-slate-700">Rodada (manual)</label>
            <input type="number" id="matchdayNum" min="1" max="50" value="1"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
          </div>
          <div class="flex items-end">
            <button type="button" id="btnLoadFixtures"
              class="w-full inline-flex items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-bold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-200">
              Buscar jogos
            </button>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-3">
          <button type="button" id="btnSelectAll"
            class="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-100">
            Marcar todos
          </button>
          <button type="button" id="btnSelectNone"
            class="inline-flex items-center justify-center rounded-xl border border-slate-300 bg-white px-4 py-2 text-sm font-bold text-slate-800 shadow-sm transition hover:-translate-y-0.5 hover:border-blue-300 hover:bg-blue-50 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-100">
            Desmarcar todos
          </button>
          <span class="text-sm text-slate-600">Selecione os jogos que quer analisar.</span>
        </div>

        <div id="fixturesList" class="mt-4 grid gap-2 max-h-72 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50 p-3"></div>
      </div>

      <div class="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200">
        <h2 class="text-base font-bold">4) Banca (projeção)</h2>
        <div class="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div>
            <label for="bankInitial" class="text-sm font-semibold text-slate-700">Saldo inicial (R$)</label>
            <input type="number" id="bankInitial" value="10" min="0.01" step="0.01"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
          </div>
          <div>
            <label for="bankDay" class="text-sm font-semibold text-slate-700">Dia da meta (1–30)</label>
            <input type="number" id="bankDay" value="1" min="1" max="30"
              class="mt-2 w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100" />
          </div>
          <div class="flex items-end gap-2">
            <button type="button" id="btnAnalyze"
              class="flex-1 inline-flex items-center justify-center rounded-xl bg-blue-600 px-4 py-2 text-sm font-extrabold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-blue-700 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-blue-200">
              Analisar (tempo real)
            </button>
            <button type="button" id="btnAutoAnalyze"
              class="flex-1 inline-flex items-center justify-center rounded-xl bg-emerald-600 px-4 py-2 text-sm font-extrabold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-emerald-700 hover:shadow active:translate-y-0 focus:outline-none focus:ring-4 focus:ring-emerald-200"
              title="Analisa automaticamente as rodadas atuais de todas as competições">
              🤖 Análise Automática
            </button>
          </div>
        </div>
        <p class="mt-2 text-sm text-slate-600" id="analyzeHint">Dica: use "Análise Automática" para descobrir os melhores jogos de todas as competições, ou selecione jogos manualmente e clique "Analisar".</p>
      </div>

      <div id="results"></div>
    </div>
  </div>

<script>
(function() {
  const $ = (id) => document.getElementById(id);
  const globalBanner = $("globalBanner");
  const keyStatus = $("keyStatus");

  function showBanner(msg, ok) {
    let displayMsg = msg;
    
    // Tratamentos especiais para erros comuns
    if (msg && msg.includes("429") || msg && msg.includes("rate limit") || msg && msg.includes("Rate limit")) {
      displayMsg = "⏳ Limite de requisições atingido! A API está temporariamente indisponível. Aguarde 1-2 minutos e tente novamente.";
      ok = false;
    } else if (msg && msg.includes("401") || msg && msg.includes("403")) {
      displayMsg = "🔒 Erro de autenticação. Verifique se sua chave da API está correta e ativa.";
      ok = false;
    } else if (msg && msg.includes("404")) {
      displayMsg = "❌ Jogo ou rodada não encontrado(a). Verifique os parâmetros.";
      ok = false;
    } else if (msg && msg.includes("502") || msg && msg.includes("503")) {
      displayMsg = "🔧 Erro do servidor da API. Tente novamente em alguns segundos.";
      ok = false;
    }
    
    globalBanner.innerHTML =
      '<div class="rounded-xl px-4 py-3 text-sm font-semibold ring-1 ' +
      (ok ? 'bg-blue-50 text-blue-900 ring-blue-100' : 'bg-red-50 text-red-900 ring-red-100') +
      '">' + esc(displayMsg) + '</div>';
  }
  function clearBanner() { globalBanner.innerHTML = ''; }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s == null ? '' : String(s);
    return d.innerHTML;
  }

  async function apiJson(url, opts) {
    try {
      const r = await fetch(url, Object.assign({ headers: { 'Accept': 'application/json' } }, opts || {}));
      const text = await r.text();
      let data;
      try { data = JSON.parse(text); } catch (e) { data = { error: text || 'Resposta inválida' }; }
      if (!r.ok) {
        let errMsg = data.error || data.message || r.statusText;
        // Melhorar mensagem de erro para 429
        if (r.status === 429) {
          errMsg = "HTTP 429 — Rate limit atingido (muitas requisições). Aguarde alguns minutos.";
        }
        throw new Error(errMsg);
      }
      return data;
    } catch (e) {
      throw new Error(e.message || String(e));
    }
  }

  async function refreshSession() {
    try {
      const s = await apiJson('/api/session');
      keyStatus.textContent = s.configured
        ? 'Chave disponível no servidor (interface ou variável de ambiente).'
        : 'Nenhuma chave — informe acima ou defina FOOTBALL_DATA_API_KEY.';
    } catch (e) {
      keyStatus.textContent = String(e.message || e);
    }
  }

  $("btnSaveKey").onclick = async () => {
    clearBanner();
    const api_key = $("apiKey").value.trim();
    const base_url = $("baseUrl").value.trim();
    try {
      await apiJson('/api/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key, base_url })
      });
      showBanner('Chave salva apenas na memória deste processo Python (servidor local).', true);
      await refreshSession();
    } catch (e) {
      showBanner(e.message || String(e), false);
    }
  };

  $("btnLoadComps").onclick = async () => {
    clearBanner();
    const sel = $("competition");
    sel.innerHTML = '';
    try {
      const data = await apiJson('/api/competitions');
      const list = data.competitions || [];
      if (!list.length) {
        showBanner('Nenhuma competição retornada (verifique o plano da API).', false);
        return;
      }
      for (const c of list) {
        const o = document.createElement('option');
        o.value = c.code;
        o.textContent = (c.name || c.code) + ' (' + c.code + ')';
        sel.appendChild(o);
      }
      showBanner(list.length + ' competições carregadas.', true);
    } catch (e) {
      showBanner(e.message || String(e), false);
    }
  };

  $("btnLoadMeta").onclick = async () => {
    clearBanner();
    const code = $("competition").value;
    if (!code) { showBanner('Escolha uma competição.', false); return; }
    try {
      const data = await apiJson('/api/competition/' + encodeURIComponent(code) + '/meta');
      $("compMeta").textContent = data.name + ' — rodada atual aproximada: ' + data.current_matchday
        + ' (use o select de 1 a ' + data.matchday_max + ').';
      const md = $("matchday");
      md.innerHTML = '';
      for (let i = 1; i <= data.matchday_max; i++) {
        const o = document.createElement('option');
        o.value = String(i);
        o.textContent = 'Rodada ' + i + (i === data.current_matchday ? ' (atual)' : '');
        if (i === data.current_matchday) o.selected = true;
        md.appendChild(o);
      }
      $("matchdayNum").value = String(data.current_matchday);
      showBanner('Metadados da competição carregados.', true);
    } catch (e) {
      showBanner(e.message || String(e), false);
    }
  };

  $("matchday").addEventListener('change', () => {
    $("matchdayNum").value = $("matchday").value;
  });

  function currentMatchday() {
    const manual = parseInt($("matchdayNum").value, 10);
    if (manual >= 1) return manual;
    return parseInt($("matchday").value, 10) || 1;
  }

  $("btnLoadFixtures").onclick = async () => {
    clearBanner();
    const code = $("competition").value;
    const matchday = currentMatchday();
    if (!code) { showBanner('Escolha uma competição.', false); return; }
    const box = $("fixturesList");
    box.innerHTML = '<div class=\"text-sm text-slate-600\">Carregando…</div>';
    try {
      const data = await apiJson('/api/competition/' + encodeURIComponent(code) + '/fixtures?matchday=' + matchday);
      const fx = data.fixtures || [];
      box.innerHTML = '';
      if (!fx.length) {
        box.innerHTML = '<div class=\"text-sm text-slate-600\">Nenhum jogo encontrado para esta rodada.</div>';
        return;
      }
      for (const f of fx) {
        const row = document.createElement('label');
        row.className =
          'flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm ' +
          'transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = f.match_id;
        cb.checked = true;
        cb.dataset.fixture = JSON.stringify(f);
        cb.className = 'mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-200';
        const span = document.createElement('span');
        span.innerHTML =
          '<div class=\"text-sm font-bold text-slate-900\">' +
          esc(f.home_team_name) + ' <span class=\"text-slate-400 font-semibold\">x</span> ' + esc(f.away_team_name) +
          '</div>' +
          '<div class=\"mt-0.5 text-xs text-slate-600\">Status: ' + esc(f.status) + ' · ID ' + esc(f.match_id) + '</div>';
        row.appendChild(cb);
        row.appendChild(span);
        box.appendChild(row);
      }
      showBanner(fx.length + ' jogos carregados. Desmarque os que não quer analisar.', true);
    } catch (e) {
      box.innerHTML = '';
      showBanner(e.message || String(e), false);
    }
  };

  $("btnSelectAll").onclick = () => {
    document.querySelectorAll('#fixturesList input[type=checkbox]').forEach((c) => { c.checked = true; });
  };
  $("btnSelectNone").onclick = () => {
    document.querySelectorAll('#fixturesList input[type=checkbox]').forEach((c) => { c.checked = false; });
  };

  function renderResults(snap) {
    const el = $("results");
    const best = snap.best || {};
    const ranked = snap.ranked || [];
    const bank = snap.bankroll || [];
    const fxRows = (snap.competition_fixtures || []).map((f) =>
      '<tr class=\"border-t border-slate-200\"><td class=\"px-3 py-2\">' + esc(f.match_id) + '</td><td class=\"px-3 py-2\">' + esc(f.utc_date) + '</td><td class=\"px-3 py-2\">' + esc(f.status) + '</td><td class=\"px-3 py-2\">'
      + esc(f.home_team_name) + '</td><td class=\"px-3 py-2\">' + esc(f.away_team_name) + '</td></tr>').join('');

    const rankedRows = ranked.map((item) => {
      const reasons = (item.reasons && item.reasons.length) ? item.reasons.join('; ') : 'Sem alertas';
      return '<tr class=\"border-t border-slate-200\"><td class=\"px-3 py-2 font-semibold\">' + esc(item.match) + '</td><td class=\"px-3 py-2\">' + (item.approved ? 'Sim' : 'Não') + '</td><td class=\"px-3 py-2\">'
        + esc(item.confidence) + '</td><td class=\"px-3 py-2\">' + esc(item.combined_avg_goals) + '</td><td class=\"px-3 py-2\">' + esc(item.market)
        + '</td><td class=\"px-3 py-2\">' + esc(item.odd_target) + '</td><td class=\"px-3 py-2 text-slate-600\">' + esc(reasons) + '</td></tr>';
    }).join('');

    const bankRows = bank.map((r) =>
      '<tr class=\"border-t border-slate-200\"><td class=\"px-3 py-2\">' + r.day + '</td><td class=\"px-3 py-2\">R$ ' + r.opening_bankroll.toFixed(2) + '</td><td class=\"px-3 py-2\">R$ '
      + r.target_profit.toFixed(2) + '</td><td class=\"px-3 py-2\">R$ ' + r.suggested_stake.toFixed(2) + '</td><td class=\"px-3 py-2\">R$ '
      + r.closing_bankroll.toFixed(2) + '</td></tr>').join('');

    const reasonsBest = (best.reasons || []).map((x) => '<li class=\"ml-5 list-disc text-sm text-slate-700\">' + esc(x) + '</li>').join('') || '<li class=\"ml-5 list-disc text-sm text-slate-700\">Sem alertas</li>';
    const badgeClass = snap.system_class === 'ok'
      ? 'bg-blue-50 text-blue-900 ring-1 ring-blue-100'
      : 'bg-red-50 text-red-900 ring-1 ring-red-100';

    el.innerHTML =
      '<div class=\"mt-2 grid grid-cols-1 gap-4\">' +
        '<div class=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\">' +
          '<div class=\"flex flex-wrap items-center justify-between gap-3\">' +
            '<span class=\"inline-flex items-center rounded-full px-3 py-1 text-xs font-extrabold ' + badgeClass + '\">' + esc(snap.system_status) + '</span>' +
            '<a class=\"text-sm font-semibold text-blue-700 hover:text-blue-800 hover:underline\" href=\"/api/last\">Ver JSON</a>' +
          '</div>' +
          '<div class=\"mt-3 text-sm text-slate-600\">Fonte: <span class=\"font-semibold text-slate-900\">' + esc(snap.data_source) + '</span> · ' +
            'Modo: <span class=\"font-semibold text-slate-900\">' + esc(snap.analysis_mode) + '</span></div>' +
          '<div class=\"mt-1 text-sm text-slate-600\">' + esc(snap.fixture_label) + '</div>' +
          '<div class=\"mt-4 grid grid-cols-1 gap-3 md:grid-cols-3\">' +
            '<div class=\"rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200\"><div class=\"text-xs font-semibold text-slate-600\">Aprovados</div><div class=\"mt-1 text-2xl font-extrabold\">' + snap.approved_count + '</div></div>' +
            '<div class=\"rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200\"><div class=\"text-xs font-semibold text-slate-600\">Rejeitados</div><div class=\"mt-1 text-2xl font-extrabold\">' + snap.rejected_count + '</div></div>' +
            '<div class=\"rounded-xl bg-blue-50 p-4 ring-1 ring-blue-100\"><div class=\"text-xs font-semibold text-blue-700\">Melhor confiança</div><div class=\"mt-1 text-2xl font-extrabold text-blue-900\">' + esc(best.confidence) + '/100</div></div>' +
          '</div>' +
        '</div>' +

        '<div class=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\">' +
          '<h2 class=\"text-base font-extrabold\">Jogo do dia</h2>' +
          '<div class=\"mt-2 text-sm font-bold\">' + esc(best.status) + '</div>' +
          '<div class=\"mt-3 rounded-xl bg-blue-50 p-4 ring-1 ring-blue-100\">' +
            '<div class=\"text-sm font-semibold text-blue-900\">Sugestão de bilhete</div>' +
            '<div class=\"mt-1 text-sm text-blue-900\">' + esc(best.ticket_line || best.market) + '</div>' +
            '<div class=\"mt-2 text-sm font-semibold text-slate-800\">' + esc(snap.goal_message) + '</div>' +
          '</div>' +
          '<h3 class=\"mt-4 text-sm font-extrabold\">Alertas</h3>' +
          '<ul class=\"mt-2 space-y-1\">' + reasonsBest + '</ul>' +
        '</div>' +

        '<div class=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\">' +
          '<h2 class=\"text-base font-extrabold\">Ranking</h2>' +
          '<div class=\"mt-3 overflow-x-auto rounded-xl ring-1 ring-slate-200\">' +
            '<table class=\"min-w-full text-left text-sm\">' +
              '<thead class=\"bg-slate-50 text-xs uppercase tracking-wide text-slate-600\">' +
                '<tr><th class=\"px-3 py-2\">Confronto</th><th class=\"px-3 py-2\">Aprovado</th><th class=\"px-3 py-2\">Confiança</th><th class=\"px-3 py-2\">Média</th><th class=\"px-3 py-2\">Mercado</th><th class=\"px-3 py-2\">Odd</th><th class=\"px-3 py-2\">Alertas</th></tr>' +
              '</thead>' +
              '<tbody class=\"bg-white\">' + rankedRows + '</tbody>' +
            '</table>' +
          '</div>' +
        '</div>' +

        '<div class=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\">' +
          '<h2 class=\"text-base font-extrabold\">Jogos analisados</h2>' +
          '<div class=\"mt-3 overflow-x-auto rounded-xl ring-1 ring-slate-200\">' +
            '<table class=\"min-w-full text-left text-sm\">' +
              '<thead class=\"bg-slate-50 text-xs uppercase tracking-wide text-slate-600\">' +
                '<tr><th class=\"px-3 py-2\">ID</th><th class=\"px-3 py-2\">Data</th><th class=\"px-3 py-2\">Status</th><th class=\"px-3 py-2\">Mandante</th><th class=\"px-3 py-2\">Visitante</th></tr>' +
              '</thead>' +
              '<tbody class=\"bg-white\">' + (fxRows || '<tr><td class=\"px-3 py-3 text-slate-600\" colspan=\"5\">—</td></tr>') + '</tbody>' +
            '</table>' +
          '</div>' +
        '</div>' +

        '<div class=\"rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200\">' +
          '<h2 class=\"text-base font-extrabold\">Projeção de banca (10 dias)</h2>' +
          '<div class=\"mt-3 overflow-x-auto rounded-xl ring-1 ring-slate-200\">' +
            '<table class=\"min-w-full text-left text-sm\">' +
              '<thead class=\"bg-slate-50 text-xs uppercase tracking-wide text-slate-600\">' +
                '<tr><th class=\"px-3 py-2\">Dia</th><th class=\"px-3 py-2\">Abertura</th><th class=\"px-3 py-2\">Lucro meta</th><th class=\"px-3 py-2\">Entrada</th><th class=\"px-3 py-2\">Fechamento</th></tr>' +
              '</thead>' +
              '<tbody class=\"bg-white\">' + bankRows + '</tbody>' +
            '</table>' +
          '</div>' +
          '<div class=\"mt-3 text-sm text-slate-600\">Atalho: <a class=\"font-semibold text-blue-700 hover:text-blue-800 hover:underline\" href=\"/status.json\">/status.json</a></div>' +
        '</div>' +
      '</div>';
  }

  $("btnAnalyze").onclick = async () => {
    clearBanner();
    const code = $("competition").value;
    const matchday = currentMatchday();
    const ids = [];
    document.querySelectorAll('#fixturesList input[type=checkbox]:checked').forEach((c) => ids.push(c.value));
    if (!code) { showBanner('Escolha uma competição.', false); return; }
    if (!ids.length) { showBanner('Marque ao menos um jogo (ou busque a rodada antes).', false); return; }
    $("btnAnalyze").disabled = true;
    $("btnAnalyze").classList.add('opacity-70');
    try {
      const snap = await apiJson('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          competition: code,
          matchday: matchday,
          fixture_ids: ids,
          bankroll_initial: parseFloat($("bankInitial").value) || 10,
          bankroll_day: parseInt($("bankDay").value, 10) || 1
        })
      });
      renderResults(snap);
      showBanner('Análise concluída com dados em tempo real (' + ids.length + ' jogo(s)).', true);
    } catch (e) {
      showBanner(e.message || String(e), false);
    } finally {
      $("btnAnalyze").disabled = false;
      $("btnAnalyze").classList.remove('opacity-70');
    }
  };

  $("btnAutoAnalyze").onclick = async () => {
    clearBanner();
    showBanner('⏳ Analisando todas as competições e suas rodadas atuais...', true);
    $("btnAutoAnalyze").disabled = true;
    $("btnAutoAnalyze").classList.add('opacity-70');
    try {
      const snap = await apiJson('/api/auto-analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bankroll_initial: parseFloat($("bankInitial").value) || 10,
          bankroll_day: parseInt($("bankDay").value, 10) || 1
        })
      });
      renderResults(snap);
      const compsAnalyzed = (snap.meta && snap.meta.competitions_analyzed) ? snap.meta.competitions_analyzed.length : '?';
      showBanner('✅ Análise automática concluída! ' + compsAnalyzed + ' competição(ões) analisada(s).', true);
    } catch (e) {
      showBanner('❌ Erro na análise automática: ' + (e.message || String(e)), false);
    } finally {
      $("btnAutoAnalyze").disabled = false;
      $("btnAutoAnalyze").classList.remove('opacity-70');
    }
  };

  refreshSession();
})();
</script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return
    
    # Corrigir encoding para UTF-8 (evita erro 'latin-1' codec)
    @property
    def server_version(self) -> str:
        return "Football-Dashboard/1.0"

    def _read_json(self) -> Any:
        n = int(self.headers.get("Content-Length", 0))
        if n <= 0:
            return None
        raw = self.rfile.read(n)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, status: int = 200, content_type: str = "text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"

        if path == "/api/session":
            try:
                body = self._read_json() or {}
                api_key = str(body.get("api_key") or "").strip()
                base_url = str(body.get("base_url") or "").strip()
                with _state_lock:
                    _server_state["api_key"] = api_key or None
                    _server_state["base_url"] = base_url or None
                configured = bool(api_key) or bool(os.getenv("FOOTBALL_DATA_API_KEY", "").strip())
                self._send_json({"ok": True, "configured": configured})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 400)
            return

        if path == "/api/analyze":
            try:
                body = self._read_json() or {}
                code = str(body.get("competition") or "").strip()
                matchday = int(body.get("matchday") or 0)
                fixture_ids = body.get("fixture_ids") or []
                bankroll_initial = float(body.get("bankroll_initial") or 10)
                bankroll_day = int(body.get("bankroll_day") or 1)
                if not code or matchday < 1:
                    self._send_json({"error": "Informe competition e matchday válidos."}, 400)
                    return

                client = get_api_client()
                matchday_data = client.get_competition_matchday(code, matchday, unfold_goals=True)
                id_set = {str(x) for x in fixture_ids}
                if id_set:
                    chosen = [f for f in matchday_data.fixtures if f.match_id in id_set]
                else:
                    chosen = list(matchday_data.fixtures)

                if not chosen:
                    self._send_json({"error": "Nenhum jogo correspondente aos IDs selecionados."}, 400)
                    return

                recommendations = analyze_fixtures_list(client, code, chosen)
                fixtures_rows = _fixtures_to_rows(chosen)
                snap = pack_snapshot(
                    recommendations,
                    data_source="API real (seleção múltipla)",
                    analysis_mode="interactive",
                    analysis_error=None,
                    competition_name=matchday_data.competition_name,
                    fixture_label=f"Rodada {matchday} — {len(recommendations)} confronto(s) analisado(s)",
                    matchday_label=f"Rodada {matchday}",
                    competition_fixtures=fixtures_rows,
                    bankroll_initial=bankroll_initial,
                    bankroll_day=bankroll_day,
                )
                with _state_lock:
                    _server_state["last_snapshot"] = snap
                self._send_json(snap)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 502)
            return

        if path == "/api/auto-analyze":
            """Análise automática: carrega competições, rodada atual e analisa melhores."""
            try:
                # Pegar parâmetros de bankroll (GET ou POST)
                if self.command == 'POST':
                    body = self._read_json() or {}
                    bankroll_initial = float(body.get("bankroll_initial") or 10)
                    bankroll_day = int(body.get("bankroll_day") or 1)
                else:
                    bankroll_initial = float(qs.get("bankroll_initial", ["10"])[0]) if qs else 10
                    bankroll_day = int(qs.get("bankroll_day", ["1"])[0]) if qs else 1
                
                client = get_api_client()
                
                # Carregar todas as competições
                all_comps = client.list_competitions()
                
                # Filtrar competições com status ativo e popular
                valid_comps = []
                for comp in all_comps:
                    code = comp.get("code")
                    if not code or comp.get("type") != "LEAGUE":
                        continue
                    valid_comps.append(code)
                
                if not valid_comps:
                    self._send_json({"error": "Nenhuma competição encontrada."}, 400)
                    return
                
                all_recommendations = []
                comp_data = []
                
                # Para cada competição, buscar rodada atual e analisar
                for comp_code in valid_comps[:5]:  # Limitar a 5 competições para não sobrecarregar
                    try:
                        current_md = client.get_current_matchday(comp_code)
                        if not current_md or current_md < 1:
                            current_md = 1  # Fallback
                        
                        # Buscar dados da rodada
                        matchday_data = client.get_competition_matchday(comp_code, current_md, unfold_goals=True)
                        
                        # Analisar todos os jogos
                        recs = analyze_fixtures_list(client, comp_code, matchday_data.fixtures)
                        
                        # Guardar com informação da competição
                        for rec in recs:
                            all_recommendations.append(rec)
                        
                        comp_data.append({
                            "code": comp_code,
                            "name": matchday_data.competition_name,
                            "matchday": current_md,
                            "fixture_count": len(matchday_data.fixtures)
                        })
                    except Exception as e:
                        # Continuar com próxima competição em caso de erro
                        print(f"Erro ao analisar {comp_code}: {e}")
                        continue
                
                # Ordenar recomendações por confiança
                ranked = rank_recommendations(all_recommendations)
                
                # Manter apenas os aprovados, ordena por confiança
                approved = [r for r in ranked if r.approved][:10]  # Top 10
                
                snap = pack_snapshot(
                    approved,
                    data_source="API real (análise automática)",
                    analysis_mode="auto",
                    analysis_error=None,
                    competition_name="Múltiplas Competições",
                    fixture_label=f"Análise Automática — {len(ranked)} jogo(s) total, {len(approved)} aprovado(s)",
                    matchday_label="Rodada Atual",
                    competition_fixtures=[],
                    bankroll_initial=bankroll_initial,
                    bankroll_day=bankroll_day,
                )
                
                # Adicionar dados das competições analisadas
                if isinstance(snap, dict) and isinstance(snap.get("meta"), dict):
                    snap["meta"]["competitions_analyzed"] = comp_data
                
                with _state_lock:
                    _server_state["last_snapshot"] = snap
                self._send_json(snap)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 502)
            return

        self._send_text("Not Found", 404)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        path = u.path.rstrip("/") or "/"
        qs = parse_qs(u.query)

        if path in {"/", "/index.html"}:
            page = build_interactive_html()
            self._send_text(page, 200, "text/html; charset=utf-8")
            return

        if path == "/api/session":
            try:
                env_k = bool(os.getenv("FOOTBALL_DATA_API_KEY", "").strip())
                with _state_lock:
                    ui_k = bool((_server_state.get("api_key") or "").strip())
                self._send_json({"configured": ui_k or env_k})
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 400)
            return

        if path == "/api/competitions":
            try:
                client = get_api_client()
                comps = client.list_competitions()
                out = []
                for item in comps:
                    code = item.get("code")
                    if not code:
                        continue
                    out.append(
                        {
                            "code": code,
                            "name": item.get("name") or code,
                            "type": item.get("type"),
                        }
                    )
                self._send_json({"competitions": out})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 502)
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 4 and parts[0] == "api" and parts[1] == "competition":
            code = unquote(parts[2])
            action = parts[3]
            try:
                client = get_api_client()
                if action == "meta":
                    raw = client.get_competition(code)
                    name = str(raw.get("name") or code)
                    season = raw.get("currentSeason") if isinstance(raw.get("currentSeason"), dict) else {}
                    current_md = season.get("currentMatchday")
                    if not isinstance(current_md, int):
                        current_md = 1
                    matchday_max = 40
                    self._send_json(
                        {
                            "code": code,
                            "name": name,
                            "current_matchday": current_md,
                            "matchday_max": matchday_max,
                        }
                    )
                    return
                if action == "fixtures":
                    md_raw = (qs.get("matchday") or ["1"])[0]
                    matchday = int(md_raw)
                    md_data = client.get_competition_matchday(code, matchday, unfold_goals=True)
                    rows = _fixtures_to_rows(md_data.fixtures)
                    self._send_json(
                        {
                            "competition": code,
                            "competition_name": md_data.competition_name,
                            "matchday": matchday,
                            "fixtures": rows,
                        }
                    )
                    return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, 400)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, 502)
            return

        if path in {"/status.json", "/api/status", "/api/last"}:
            with _state_lock:
                last = _server_state.get("last_snapshot")
            if last:
                self._send_json(last)
            else:
                self._send_json(build_system_snapshot())
            return

        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        self._send_text("Not Found", 404)


def main() -> None:
    _init_state_from_env()
    parser = argparse.ArgumentParser(description="Painel interativo — Total de Gols.")
    parser.add_argument("--host", default="127.0.0.1", help="Host de escuta.")
    parser.add_argument("--port", type=int, default=8000, help="Porta local.")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print(f"Servidor rodando em http://{args.host}:{args.port}")
    print("Abra / no navegador — painel interativo (chave, competição, multi-seleção).")
    print("JSON: /api/last ou /status.json")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando servidor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
