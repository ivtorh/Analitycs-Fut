# 🚀 Guia de Auto-Commit Automático

## O Que É?

Sistema que **monitora mudanças** em seus arquivos e faz **commits automáticos** no Git com mensagens descritivas.

```
📁 Projeto                    🔄 Auto-Commit                ✅ Git
   ├─ arquivo.py  ──────────> Detecta mudança ────────────> Commit
   ├─ index.html  ──────────> Gera mensagem  ────────────> Histórico
   └─ data.csv    ──────────> Faz commit     ────────────> Backup
```

---

## 🚀 Como Usar

### Opção 1: Windows

**Clique duplo em:**
```
auto_commit.bat
```

Ou execute via PowerShell:
```powershell
cd "c:\Users\Victor\Documents\Analitycs Fut"
python auto_commit.py
```

### Opção 2: Linux/Mac

```bash
cd ~/Documents/Analitycs\ Fut
chmod +x auto_commit.sh
./auto_commit.sh
```

Ou:
```bash
python3 auto_commit.py
```

### Opção 3: Modo Teste (Dry-Run)

Veja o que seria commitado SEM fazer commits reais:

**Windows:**
```cmd
auto_commit.bat dry-run
```

**Linux/Mac:**
```bash
./auto_commit.sh dry-run
```

---

## ⚙️ Configuração

Edite `auto_commit.py` para ajustar:

```python
# Intervalo de verificação (segundos)
CHECK_INTERVAL = 5

# Delay antes de fazer commit após mudança (segundos)
COMMIT_DELAY = 10

# Modo de teste (não faz commits reais)
DRY_RUN = False

# Extensões a monitorar
MONITORED_EXTENSIONS = {
    ".py",   # Python
    ".html", # HTML
    ".md",   # Markdown
    # ... adicione mais
}
```

---

## 📊 Exemplo de Saída

```
============================================================
🚀 SISTEMA DE AUTO-COMMIT INICIADO
============================================================
📁 Monitorando: c:\Users\Victor\Documents\Analitycs Fut
⏱️  Intervalo: 5s
📝 Delay para commit: 10s
🔄 Modo: NORMAL
============================================================
Pressione Ctrl+C para parar

📝 3 arquivo(s) mudado(s):
   ✨ football_odds_monitor.py (novo)
   ✏️  football_settlement.py (modificado)
   🗑️  old_file.txt (deletado)

✅ Commit: ➕ 1 novo(s) arquivo(s) | ✏️  1 arquivo(s) modificado(s) | 🗑️  1 arquivo(s) deletado(s) [14:32:45]
```

---

## 📝 Tipos de Mensagens de Commit

### Exemplo 1: Arquivo novo
```
✅ ➕ 1 novo(s) arquivo(s) | 🐍 football_odds_monitor.py [14:32:45]
```

### Exemplo 2: Arquivo modificado
```
✅ ✏️  1 arquivo(s) modificado(s) | 🐍 football_settlement.py [14:32:50]
```

### Exemplo 3: Múltiplas mudanças
```
✅ ➕ 1 novo(s) arquivo(s) | ✏️  2 arquivo(s) modificado(s) | 🎨 Frontend atualizado [14:33:00]
```

### Exemplo 4: Documentação
```
✅ 📚 Documentação atualizada | ✏️  GUIA_EVOLUÇÕES.md [14:33:15]
```

---

## 🔄 Fluxo de Funcionamento

```
1. Inicia o script
   ↓
2. Inicializa repositório Git (primeira vez)
   ↓
3. Carrega hashes de todos os arquivos
   ↓
4. Loop infinito:
   ├─ A cada 5 segundos:
   │  ├─ Verifica mudanças calculando hashes
   │  ├─ Se há mudança:
   │  │  ├─ Exibe arquivo mudado
   │  │  ├─ Aguarda 10 segundos (COMMIT_DELAY)
   │  │  ├─ Se não houve mais mudanças:
   │  │  │  ├─ Gera mensagem descritiva
   │  │  │  ├─ Executa: git add .
   │  │  │  ├─ Executa: git commit -m "mensagem"
   │  │  │  ├─ Exibe: ✅ Commit feito
   │  │  │  └─ Aguarda próxima mudança
   │  │  └─ Caso contrário: aguarda mais
   │  └─ Fim do loop
   └─ Repetir
```

---

## 🛑 Parar o Auto-Commit

Pressione **Ctrl+C** no terminal.

```
⏹️  Parando auto-commit...
✅ Auto-commit parado
```

---

## 🔒 Segurança

### Arquivos NÃO monitorados

```
__pycache__/        # Compilados Python
*.pyc              # Cache Python
.git/              # Próprio Git
.env               # Variáveis sensíveis
venv/              # Ambiente virtual
.DS_Store          # Arquivos do sistema
*.db               # Banco de dados local
```

Configure via `.gitignore` (criado automaticamente).

---

## 🐛 Troubleshooting

### "Git não está instalado"
```
Solução: Instale Git em: https://git-scm.com/download/
```

### "Python não está instalado"
```
Solução: Instale Python em: https://www.python.org/downloads/
```

### Commits não aparecem
```
Solução:
1. Verifique se Git está configurado:
   git config --global user.name "Seu Nome"
   git config --global user.email "seu@email.com"

2. Verifique status:
   git status

3. Veja log:
   git log --oneline
```

### Muito lento
```
Solução: Aumente CHECK_INTERVAL em auto_commit.py
CHECK_INTERVAL = 15  # De 5 para 15 segundos
```

### Commits muito frequentes
```
Solução: Aumente COMMIT_DELAY em auto_commit.py
COMMIT_DELAY = 30   # De 10 para 30 segundos
```

---

## 💡 Dicas de Uso

### 1. Executar no Início do Dia
```bash
# Terminal 1: Editor (VS Code)
code .

# Terminal 2: Auto-commit
python auto_commit.py
```

### 2. Deixar Rodando de Fundo
Mantenha em uma aba do terminal separada enquanto trabalha.

### 3. Revisar Commits
```bash
# Ver últimos commits
git log --oneline -10

# Ver mudanças de um commit
git show <commit-hash>

# Ver diff desde o último commit
git diff
```

### 4. Desfazer Commit (se necessário)
```bash
# Desfazer último commit (mantém mudanças)
git reset --soft HEAD~1

# Desfazer último commit (perde mudanças)
git reset --hard HEAD~1
```

---

## 📊 Configurações Avançadas

### Monitorar apenas arquivos específicos
```python
MONITORED_EXTENSIONS = {
    ".py",     # Apenas Python
    ".md",     # E Markdown
}
```

### Incluir mais extensões
```python
MONITORED_EXTENSIONS = {
    ".py", ".html", ".css", ".js",  # Web
    ".md", ".txt", ".rst",          # Docs
    ".json", ".yaml", ".xml",       # Configs
    ".csv", ".xlsx", ".sql",        # Data
}
```

### Mudar intervalo de verificação
```python
CHECK_INTERVAL = 2      # Muito rápido (CPU alta)
CHECK_INTERVAL = 5      # Padrão (recomendado)
CHECK_INTERVAL = 15     # Mais lento (economia de CPU)
CHECK_INTERVAL = 30     # Bem lento
```

### Mudar delay antes de commit
```python
COMMIT_DELAY = 5        # Rápido (mais commits pequenos)
COMMIT_DELAY = 10       # Padrão (recomendado)
COMMIT_DELAY = 30       # Agrupa mais mudanças
COMMIT_DELAY = 60       # Agrupa bastante
```

---

## 📚 Comandos Git Úteis

```bash
# Ver status
git status

# Ver log de commits
git log --oneline

# Ver mudanças não commitadas
git diff

# Ver mudanças staged (preparadas)
git diff --cached

# Ver mudanças de um arquivo específico
git log -p football_odds_monitor.py

# Ver quem editou cada linha (blame)
git blame football_odds_monitor.py

# Ver branch atual
git branch

# Ver todas as mudanças
git log --graph --oneline --all
```

---

## 🎯 Próximos Passos

1. **Sincronizar com GitHub**
   ```bash
   git remote add origin https://github.com/seu-usuario/seu-repo.git
   git push -u origin main
   ```

2. **Fazer backup automático**
   - Use GitHub, GitLab, Bitbucket, etc.
   - Commits automáticos já farão backup local

3. **Criar branches para features**
   ```bash
   git checkout -b feature/novo-recurso
   # Fazer mudanças
   # Auto-commit faz commits neste branch
   git push origin feature/novo-recurso
   ```

4. **Colaborar com outros**
   - Compartilhe o repositório
   - Cada um com seu auto-commit
   - Use `git pull` para sincronizar

---

## ⚡ Resumo Rápido

| Ação | Windows | Linux/Mac |
|------|---------|----------|
| Iniciar | `auto_commit.bat` | `./auto_commit.sh` |
| Teste | `auto_commit.bat dry-run` | `./auto_commit.sh dry-run` |
| Parar | Ctrl+C | Ctrl+C |
| Ver histórico | `git log --oneline` | `git log --oneline` |
| Ver mudanças | `git diff` | `git diff` |

---

**Desenvolvido para:** Football Analytics System  
**Versão:** 1.0  
**Status:** ✅ Pronto para Uso  
**Última atualização:** 26 de Abril de 2026
