# Quick Test — Análise Automática

**Validar a implementação em 3 minutos**

## Pré-requisitos
- Python rodando: `python football_total_goals_web.py`
- Navegador aberto em: http://127.0.0.1:8000
- Chave API football-data.org (obter em https://www.football-data.org/client/register)

## Teste 1: Encoding UTF-8 Corrigido ✅

**Objetivo**: Verificar que caracteres especiais (travessões, acentos) agora funcionam

1. Cole a chave API no campo "Token (X-Auth-Token)"
2. Clique "Salvar chave no servidor local"
3. Clique "Listar competições"
4. **Resultado esperado**:
   - Lista de competições aparece sem erro de encoding
   - Nomes como "La Liga 2023–2024" aparecem corretamente com travessão
   - ❌ Erro anterior NÃO deve ocorrer: `'latin-1' codec can't encode character '\u2014'`

---

## Teste 2: Interface do Botão Automático ✅

**Objetivo**: Verificar que a nova interface está presente

1. Scroll até a seção "4) Banca (projeção)"
2. **Você deve ver 2 botões lado a lado**:
   - ← Esquerda: "Analisar (tempo real)" (azul)
   - → Direita: "🤖 Análise Automática" (verde)
3. Dica deve dizer: "use 'Análise Automática' para descobrir os melhores jogos..."

---

## Teste 3: Análise Automática Completa 🤖

**Objetivo**: Testar o fluxo completo de análise automática

1. **Pré-condição**: Chave API válida já salva
2. Clique no botão verde "🤖 Análise Automática"
3. **Você verá mensagem**: "⏳ Analisando todas as competições e suas rodadas atuais..."
4. **Espere 30-60 segundos** (enquanto busca 5 competições)
5. **Resultado esperado**:
   - Mensagem: "✅ Análise automática concluída! X competição(ões) analisada(s)."
   - Seção de "Resultados" aparece com games e informações
   - Lista exibe os top 10 melhores jogos por confiança

---

## Teste 4: Dados da Resposta 📊

**Objetivo**: Verificar que dados corretos são retornados

Se os resultados aparecerem, clique no link "Ver JSON" para ver:

```json
{
  "data_source": "API real (análise automática)",
  "analysis_mode": "auto",
  "meta": {
    "competitions_analyzed": [
      { "code": "PL", "name": "Premier League", "matchday": 28, ... },
      { "code": "SA", "name": "Serie A", "matchday": 25, ... },
      ...
    ],
    ...
  },
  "recommendations": [
    {
      "home_team": "Team A",
      "away_team": "Team B",
      "approved": true,
      "confidence_score": 87,
      ...
    },
    ...
  ]
}
```

---

## Checklist de Validação

- [ ] Teste 1: Encoding UTF-8 funciona (lista de competições)
- [ ] Teste 2: Botão "🤖 Análise Automática" está visível
- [ ] Teste 3: Análise automática completa sem erro
- [ ] Teste 4: JSON contém "competitions_analyzed" com dados
- [ ] Bonus: Resultados são ordenados por `confidence_score` descending

---

## Troubleshooting

**Erro**: "Nenhuma chave configurada"
- **Solução**: Cole a chave API e clique "Salvar chave"

**Erro**: "HTTP 400 em ... Your API token is invalid"
- **Solução**: Verifique se a chave API está correta em https://www.football-data.org

**Erro**: "Rate limit atingido. Aguardando..."
- **Esperado**: O sistema faz retry automático (máx 3 tentativas)
- **Solução**: Aguarde, ele tentará novamente

**Botão não aparece**
- **Solução**: Recarregue a página (Ctrl+F5)

---

## Próxima Execução

Após validar testes, use normalmente:

1. Insira chave API
2. Clique "🤖 Análise Automática"
3. Aguarde resultado
4. Acesse /api/last para ver JSON completo

**Pronto! ✨**
