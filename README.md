# Football Total Goals

Sistema em Python para análise estatística de jogos de futebol com foco no mercado de **Total de Gols**.

## O que o sistema faz

- analisa os **últimos 10 jogos** de cada time;
- aplica filtros de:
  - média de gols combinada;
  - risco de 0x0;
  - risco de goleada extrema;
  - consistência no H2H;
- calcula **projeção de banca com juros compostos**;
- gera uma **pontuação de confiança de 0 a 100**;
- exibe tudo em um **painel web local**.

## Arquivos principais

- `football_total_goals_strategy.py`  
  Motor estatístico e calculadora de banca.

- `football_data_provider.py`  
  Integração com dados reais via `football-data.org`.

- `football_total_goals_web.py`  
  Painel web local.

## Como usar com dados reais

### 1) Instale a dependência necessária

O sistema usa `requests` para buscar dados externos:

```bash
pip install requests
```

### 2) Crie sua conta na API de futebol

Use uma fonte real de dados. A integração atual foi preparada para:

- `football-data.org`

Você precisa de:

- uma API key;
- o código do campeonato;
- o ID do time da casa;
- o ID do time visitante.

### 3) Configure as variáveis de ambiente

Variáveis obrigatórias:

- `FOOTBALL_DATA_API_KEY`
- `FOOTBALL_DATA_COMPETITION`
- `HOME_TEAM_ID`
- `AWAY_TEAM_ID`

Variáveis opcionais:

- `HOME_TEAM_NAME`
- `AWAY_TEAM_NAME`
- `FOOTBALL_DATA_BASE_URL`
- `FOOTBALL_DATA_MATCHDAY`

### 4) Rode o painel

```bash
python football_total_goals_web.py
```

Depois abra no navegador:

```text
http://127.0.0.1:8000
```

Se você quiser carregar uma rodada específica da competição, defina também:

- `FOOTBALL_DATA_MATCHDAY`

Exemplo de consulta que o sistema passa a suportar no backend:

```bash
curl -X GET "http://api.football-data.org/v4/competitions/2003/matches?matchday=1" -H "X-Unfold-Goals: true" -H "X-Auth-Token: SUA_CHAVE"
```

### 5) Veja o status em JSON

Você também pode acessar:

```text
http://127.0.0.1:8000/status.json
```

## Exemplo de configuração

### PowerShell

```powershell
$env:FOOTBALL_DATA_API_KEY="SUA_CHAVE"
$env:FOOTBALL_DATA_COMPETITION="PL"
$env:HOME_TEAM_ID="66"
$env:AWAY_TEAM_ID="57"
python football_total_goals_web.py
```

### CMD

```bat
set FOOTBALL_DATA_API_KEY=SUA_CHAVE
set FOOTBALL_DATA_COMPETITION=PL
set HOME_TEAM_ID=66
set AWAY_TEAM_ID=57
python football_total_goals_web.py
```

## Como descobrir os IDs dos times

A API retorna os times do campeonato. Você pode:

- consultar a documentação da API;
- buscar os times do campeonato;
- pegar os IDs de casa e visitante;
- preencher as variáveis `HOME_TEAM_ID` e `AWAY_TEAM_ID`.

## Quando o sistema usa dados simulados

Se as variáveis obrigatórias não estiverem configuradas, o sistema:

- continua funcionando;
- usa dados de demonstração;
- mostra isso no painel como `Demonstração local`.

Isso evita quebra durante testes, mas para uso real você precisa preencher a API.

## O que você precisa fazer agora

1. Criar conta na API de dados.
2. Copiar sua API key.
3. Escolher um campeonato atual.
4. Obter os IDs dos dois times que você quer analisar.
5. Definir as variáveis de ambiente.
6. Rodar `python football_total_goals_web.py`.
7. Abrir `http://127.0.0.1:8000`.

## Observação importante

Este sistema é um **filtro analítico**, não uma garantia de lucro.  
Use como apoio para decisão, e não como aposta automática.
