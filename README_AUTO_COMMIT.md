# ✅ AUTO-COMMIT - Sistema de Commits Automáticos

## 🎯 O Que Faz?

Monitora todos os seus arquivos (`.py`, `.html`, `.md`, etc.) e **faz commits automaticamente** no Git sempre que detecta mudanças.

## ⚡ Começar Rápido

### Windows
```cmd
# Duplo clique:
auto_commit.bat

# Ou via PowerShell:
python auto_commit.py
```

### Linux/Mac
```bash
./auto_commit.sh
# Ou:
python3 auto_commit.py
```

## 🔄 Como Funciona

```
1. Detecta mudança em arquivo
   ↓
2. Aguarda 10 segundos (para agregar mudanças)
   ↓
3. Gera mensagem automática
   ↓
4. Faz git add + git commit
   ↓
5. Volta a monitorar
```

## 📊 Exemplo de Saída

```
🚀 SISTEMA DE AUTO-COMMIT INICIADO
📁 Monitorando: c:\Users\Victor\Documents\Analitycs Fut
⏱️  Intervalo: 5s | Delay: 10s

📝 3 arquivo(s) mudado(s):
   ✨ novo_arquivo.py (novo)
   ✏️  arquivo_existente.py (modificado)
   🗑️  arquivo_deletado.txt (deletado)

✅ Commit: ➕ 1 novo(s) | ✏️  1 modificado(s) | 🗑️  1 deletado(s) [14:32:45]
```

## 🛑 Parar

Pressione **Ctrl+C** no terminal.

## 🧪 Testar Sem Fazer Commits Reais

```cmd
# Windows:
auto_commit.bat dry-run

# Linux/Mac:
./auto_commit.sh dry-run
```

## ⚙️ Configurar

Edite `auto_commit.py`:

```python
CHECK_INTERVAL = 5      # A cada 5 segundos verifica
COMMIT_DELAY = 10       # Aguarda 10s antes de commitdar
DRY_RUN = False         # True = não faz commits reais
```

Ou use arquivo `auto_commit_config.json`

## 📖 Documentação Completa

Ver [GUIA_AUTO_COMMIT.md](GUIA_AUTO_COMMIT.md)

## ❓ FAQ

**P: Como vejo os commits?**
```bash
git log --oneline
```

**P: Como desfaço um commit?**
```bash
git reset --soft HEAD~1
```

**P: Posso committar para um servidor remoto?**
```bash
git remote add origin https://github.com/seu-usuario/seu-repo.git
git push -u origin main
```

**P: Quais arquivos são monitorados?**
```
.py, .html, .md, .txt, .json, .csv
```

## 🎯 Pra Que Serve?

✅ Backup automático via Git  
✅ Histórico completo de mudanças  
✅ Trabalhe sem se preocupar em fazer commits  
✅ Sincronize com GitHub/GitLab  
✅ Recupere versões antigas facilmente  

## 🚀 Próximas Integrações

1. Configurar GitHub/GitLab
2. Fazer push automático
3. Criar branches automáticas
4. Deploy automático

---

**Status:** ✅ Pronto para usar  
**Versão:** 1.0  
**Última atualização:** 26 de Abril de 2026
