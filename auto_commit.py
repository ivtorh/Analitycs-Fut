"""Sistema de Auto-Commit para o repositório de análise de futebol.

Monitora mudanças em arquivos e faz commits automáticos com mensagens descritivas.
"""

import os
import sys
import subprocess
import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Set, Optional
import threading
import json
import argparse

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

# Diretório raiz do projeto
PROJECT_ROOT = Path(r"c:\Users\Victor\Documents\Analitycs Fut")

# Extensões de arquivo a monitorar
MONITORED_EXTENSIONS = {
    ".py",      # Python
    ".html",    # HTML
    ".md",      # Markdown
    ".txt",     # Text
    ".json",    # JSON
    ".csv",     # CSV
}

# Arquivos/pastas a ignorar
IGNORE_PATTERNS = {
    "__pycache__",
    ".git",
    ".env",
    ".venv",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
}

# Intervalo de verificação (segundos)
CHECK_INTERVAL = 5

# Delay antes de fazer commit após mudança (segundos)
COMMIT_DELAY = 10

# Modo de teste (não faz commits reais)
DRY_RUN = False

# ============================================================================
# IMPLEMENTAÇÃO
# ============================================================================


class FileHashTracker:
    """Rastreia hashes de arquivos para detectar mudanças."""
    
    def __init__(self):
        self.file_hashes: Dict[str, str] = {}
        self.load_current_hashes()
    
    def load_current_hashes(self) -> None:
        """Carrega hashes de todos os arquivos monitorados."""
        print("📊 Carregando hashes de arquivos...")
        for file_path in self._get_monitored_files():
            self.file_hashes[str(file_path)] = self._hash_file(file_path)
        print(f"✅ {len(self.file_hashes)} arquivos rastreados")
    
    def _get_monitored_files(self) -> list[Path]:
        """Retorna lista de arquivos a monitorar."""
        files = []
        for ext in MONITORED_EXTENSIONS:
            files.extend(PROJECT_ROOT.glob(f"**/*{ext}"))
        
        # Filtrar arquivos ignorados
        filtered = []
        for f in files:
            if not any(pattern in str(f) for pattern in IGNORE_PATTERNS):
                filtered.append(f)
        
        return sorted(filtered)
    
    def _hash_file(self, file_path: Path) -> str:
        """Calcula hash SHA-256 de um arquivo."""
        try:
            sha256_hash = hashlib.sha256()
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            print(f"❌ Erro ao ler {file_path}: {e}")
            return ""
    
    def get_changed_files(self) -> Dict[str, str]:
        """Retorna arquivos que mudaram desde a última verificação."""
        changed = {}
        
        for file_path in self._get_monitored_files():
            file_str = str(file_path)
            current_hash = self._hash_file(file_path)
            
            if current_hash:
                old_hash = self.file_hashes.get(file_str, "")
                
                if old_hash and old_hash != current_hash:
                    changed[file_str] = "modificado"
                    self.file_hashes[file_str] = current_hash
                elif not old_hash:
                    changed[file_str] = "novo"
                    self.file_hashes[file_str] = current_hash
        
        # Detectar arquivos deletados
        for file_str in list(self.file_hashes.keys()):
            if not Path(file_str).exists():
                changed[file_str] = "deletado"
                del self.file_hashes[file_str]
        
        return changed


class GitAutoCommit:
    """Gerenciador de commits automáticos."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.hash_tracker = FileHashTracker()
        self.pending_commits: Dict[str, str] = {}
        self.last_commit_time = 0
        self.running = False
        self._lock = threading.Lock()
    
    def init_git_repo(self) -> bool:
        """Inicializa repositório Git se não existir."""
        git_dir = self.project_root / ".git"
        
        if git_dir.exists():
            print("✅ Repositório Git já existe")
            return True
        
        print("🔧 Inicializando repositório Git...")
        try:
            result = subprocess.run(
                ["git", "init"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("✅ Repositório Git criado")
                
                # Configurar usuário
                subprocess.run(
                    ["git", "config", "user.email", "analytics@football.local"],
                    cwd=self.project_root,
                    capture_output=True,
                    timeout=10
                )
                subprocess.run(
                    ["git", "config", "user.name", "Football Analytics Auto"],
                    cwd=self.project_root,
                    capture_output=True,
                    timeout=10
                )
                
                # Criar .gitignore
                self._create_gitignore()
                
                # Commit inicial
                self._git_command("add", ".")
                self._git_command("commit", "-m", "🚀 Commit inicial - Sistema de análise de futebol")
                
                print("✅ Repositório configurado com sucesso")
                return True
            else:
                print(f"❌ Erro ao inicializar Git: {result.stderr}")
                return False
        
        except Exception as e:
            print(f"❌ Erro: {e}")
            return False
    
    def _create_gitignore(self) -> None:
        """Cria arquivo .gitignore."""
        gitignore_path = self.project_root / ".gitignore"
        
        gitignore_content = """# Padrões de ignorar
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.so
*.egg
*.egg-info/
dist/
build/

# Ambientes virtuais
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Arquivos do sistema
.DS_Store
Thumbs.db

# Variáveis de ambiente
.env
.env.local

# Banco de dados
*.db
*.sqlite
*.sqlite3

# Logs
*.log

# Dados temporários
*.tmp
*.temp
"""
        
        if not gitignore_path.exists():
            gitignore_path.write_text(gitignore_content)
            print("✅ Arquivo .gitignore criado")
    
    def _git_command(self, *args) -> tuple[int, str, str]:
        """Executa comando git."""
        try:
            result = subprocess.run(
                ["git"] + list(args),
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        
        except Exception as e:
            return 1, "", str(e)
    
    def _generate_commit_message(self, changed_files: Dict[str, str]) -> str:
        """Gera mensagem de commit baseada nos arquivos mudados."""
        modified = sum(1 for s in changed_files.values() if s == "modificado")
        created = sum(1 for s in changed_files.values() if s == "novo")
        deleted = sum(1 for s in changed_files.values() if s == "deletado")
        
        # Identificar tipos de mudanças
        file_types = {}
        for file_path, status in changed_files.items():
            ext = Path(file_path).suffix
            if ext not in file_types:
                file_types[ext] = []
            file_types[ext].append(Path(file_path).name)
        
        # Gerar mensagem inteligente
        messages = []
        
        if created > 0:
            messages.append(f"➕ {created} novo(s) arquivo(s)")
        
        if modified > 0:
            messages.append(f"✏️  {modified} arquivo(s) modificado(s)")
        
        if deleted > 0:
            messages.append(f"🗑️  {deleted} arquivo(s) deletado(s)")
        
        # Adicionar tipos específicos de arquivo
        if ".py" in file_types:
            py_files = file_types[".py"]
            if len(py_files) <= 3:
                messages.append(f"🐍 {', '.join(py_files)}")
            else:
                messages.append(f"🐍 {len(py_files)} arquivos Python")
        
        if ".html" in file_types:
            messages.append("🎨 Frontend atualizado")
        
        if ".md" in file_types:
            messages.append("📚 Documentação atualizada")
        
        commit_msg = " | ".join(messages)
        
        # Adicionar timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        commit_msg += f" [{timestamp}]"
        
        return commit_msg[:100]  # Limitar tamanho
    
    def commit_changes(self, changed_files: Dict[str, str]) -> bool:
        """Faz commit das mudanças."""
        if not changed_files:
            return False
        
        try:
            # Adicionar arquivos
            for file_path, status in changed_files.items():
                rel_path = Path(file_path).relative_to(self.project_root)
                
                if status == "deletado":
                    self._git_command("rm", str(rel_path))
                else:
                    self._git_command("add", str(rel_path))
            
            # Verificar se há mudanças staged
            returncode, stdout, stderr = self._git_command("status", "--porcelain")
            
            if not stdout.strip():
                print("ℹ️  Nenhuma mudança a fazer commit")
                return False
            
            # Gerar mensagem
            commit_msg = self._generate_commit_message(changed_files)
            
            # Fazer commit
            returncode, stdout, stderr = self._git_command(
                "commit", "-m", commit_msg
            )
            
            if returncode == 0:
                print(f"✅ Commit: {commit_msg}")
                self.last_commit_time = time.time()
                return True
            else:
                if "nothing to commit" not in stderr:
                    print(f"⚠️  Git error: {stderr}")
                return False
        
        except Exception as e:
            print(f"❌ Erro ao fazer commit: {e}")
            return False
    
    def start_monitoring(self) -> None:
        """Inicia monitoramento de mudanças."""
        print("\n" + "=" * 60)
        print("🚀 SISTEMA DE AUTO-COMMIT INICIADO")
        print("=" * 60)
        print(f"📁 Monitorando: {self.project_root}")
        print(f"⏱️  Intervalo: {CHECK_INTERVAL}s")
        print(f"📝 Delay para commit: {COMMIT_DELAY}s")
        print(f"🔄 Modo: {'DRY-RUN (sem commits reais)' if DRY_RUN else 'NORMAL'}")
        print("=" * 60)
        print("Pressione Ctrl+C para parar\n")
        
        self.running = True
        self.init_git_repo()
        
        try:
            last_change_time = 0
            
            while self.running:
                try:
                    # Verificar mudanças
                    changed_files = self.hash_tracker.get_changed_files()
                    
                    if changed_files:
                        print(f"\n📝 {len(changed_files)} arquivo(s) mudado(s):")
                        for file_path, status in changed_files.items():
                            emoji = {"novo": "✨", "modificado": "✏️", "deletado": "🗑️"}.get(status, "❓")
                            rel_path = Path(file_path).relative_to(self.project_root)
                            print(f"   {emoji} {rel_path} ({status})")
                        
                        last_change_time = time.time()
                    
                    # Fazer commit se passou o delay
                    if changed_files and (time.time() - last_change_time) >= COMMIT_DELAY:
                        with self._lock:
                            if not DRY_RUN:
                                self.commit_changes(changed_files)
                            else:
                                commit_msg = self._generate_commit_message(changed_files)
                                print(f"🧪 DRY-RUN: Seria commitado: {commit_msg}")
                            
                            changed_files.clear()
                    
                    time.sleep(CHECK_INTERVAL)
                
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"❌ Erro no loop: {e}")
                    time.sleep(CHECK_INTERVAL)
        
        except KeyboardInterrupt:
            print("\n\n⏹️  Parando auto-commit...")
            self.running = False
            print("✅ Auto-commit parado")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Função principal."""
    
    # Parse de argumentos
    parser = argparse.ArgumentParser(
        description="Sistema de auto-commit para repositórios Git"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Modo de teste - não faz commits reais"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=CHECK_INTERVAL,
        help=f"Intervalo de verificação em segundos (padrão: {CHECK_INTERVAL})"
    )
    parser.add_argument(
        "--delay",
        type=int,
        default=COMMIT_DELAY,
        help=f"Delay antes de commit em segundos (padrão: {COMMIT_DELAY})"
    )
    parser.add_argument(
        "--path",
        type=str,
        default=str(PROJECT_ROOT),
        help=f"Caminho do projeto (padrão: {PROJECT_ROOT})"
    )
    
    args = parser.parse_args()
    
    # Atualizar variáveis globais
    global DRY_RUN, CHECK_INTERVAL, COMMIT_DELAY, PROJECT_ROOT
    DRY_RUN = args.dry_run
    CHECK_INTERVAL = args.interval
    COMMIT_DELAY = args.delay
    PROJECT_ROOT = Path(args.path)
    
    # Verificar se o diretório existe
    if not PROJECT_ROOT.exists():
        print(f"❌ Diretório não existe: {PROJECT_ROOT}")
        return
    
    print("🔐 Verificando Git...")
    
    # Verificar se Git está instalado
    try:
        subprocess.run(["git", "--version"], capture_output=True, timeout=5)
    except Exception:
        print("❌ Git não está instalado ou não está no PATH")
        return
    
    # Iniciar auto-commit
    auto_commit = GitAutoCommit(PROJECT_ROOT)
    auto_commit.start_monitoring()


if __name__ == "__main__":
    main()
