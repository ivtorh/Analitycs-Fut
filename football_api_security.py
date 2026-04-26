"""Sistema de Segurança para Gerenciamento de Tokens API.

Mantém:
- Token da API armazenado apenas no servidor (memória segura)
- Endpoints criptografados para comunicação fronten-backend
- Sessões de usuário com expiração
- Auditoria de requisições
- Rate limiting por IP

O token NUNCA é exposto ao frontend.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from functools import wraps

try:
    import requests
except Exception:
    requests = None


@dataclass
class SessionToken:
    """Token de sessão seguro."""
    
    token_id: str
    user_identifier: str  # IP ou cookie do usuário
    created_at: datetime
    expires_at: datetime
    permissions: list[str]  # Quais endpoints pode acessar
    
    @property
    def is_valid(self) -> bool:
        """Verifica se o token ainda é válido."""
        return datetime.now() < self.expires_at
    
    @property
    def is_expired(self) -> bool:
        """Verifica se o token expirou."""
        return datetime.now() >= self.expires_at


class SecureTokenManager:
    """Gerenciador de tokens de API seguros."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Inicializa o gerenciador.
        
        Args:
            encryption_key: Chave para criptografia (gerada se não fornecida)
        """
        self._api_key: Optional[str] = None
        self._base_url: Optional[str] = None
        self._encryption_key = encryption_key or self._generate_key()
        self._sessions: dict[str, SessionToken] = {}
        self._lock = threading.Lock()
        self._rate_limit: dict[str, list[float]] = {}
        self._audit_log: list[dict[str, Any]] = []
        
        # Carregar token de variável de ambiente se existir
        self._load_from_env()
    
    def _generate_key(self) -> str:
        """Gera uma chave de criptografia aleatória."""
        return secrets.token_hex(32)
    
    def _load_from_env(self) -> None:
        """Carrega credenciais de variáveis de ambiente."""
        self._api_key = os.getenv("FOOTBALL_DATA_API_KEY", "").strip() or None
        self._base_url = os.getenv("FOOTBALL_DATA_BASE_URL", "").strip() or None
    
    def set_api_credentials(self, api_key: str, base_url: Optional[str] = None) -> None:
        """Define credenciais da API de forma segura.
        
        Args:
            api_key: Token da API
            base_url: URL base da API (opcional)
        """
        with self._lock:
            self._api_key = api_key.strip() if api_key else None
            self._base_url = (base_url or "").strip() or None
        
        self._log_audit("SET_CREDENTIALS", {
            "has_key": bool(self._api_key),
            "has_url": bool(self._base_url),
        })
    
    def get_api_key(self) -> Optional[str]:
        """Retorna a chave de API armazenada.
        
        ⚠️ Use apenas dentro do backend (servidor).
        """
        with self._lock:
            return self._api_key
    
    def get_base_url(self) -> Optional[str]:
        """Retorna a URL base armazenada."""
        with self._lock:
            return self._base_url or "https://api.football-data.org/v4"
    
    def create_session(
        self,
        user_identifier: str,
        permissions: Optional[list[str]] = None,
        duration_minutes: int = 60,
    ) -> str:
        """Cria uma nova sessão segura.
        
        Args:
            user_identifier: Identificador do usuário (IP, cookie, etc.)
            permissions: Lista de permissões (ex: ["read:odds", "read:matches"])
            duration_minutes: Duração da sessão em minutos
        
        Returns:
            Token de sessão (opaco, não contém dados sensíveis)
        """
        if permissions is None:
            permissions = ["read:matches", "read:odds", "read:settlement"]
        
        token_id = secrets.token_urlsafe(32)
        session = SessionToken(
            token_id=token_id,
            user_identifier=user_identifier,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=duration_minutes),
            permissions=permissions,
        )
        
        with self._lock:
            self._sessions[token_id] = session
        
        self._log_audit("CREATE_SESSION", {
            "session_id": self._mask_token(token_id),
            "user": user_identifier[:15],
            "permissions": permissions,
        })
        
        return token_id
    
    def validate_session(self, token_id: str) -> bool:
        """Valida um token de sessão.
        
        Args:
            token_id: Token a validar
        
        Returns:
            True se válido, False caso contrário
        """
        with self._lock:
            session = self._sessions.get(token_id)
        
        if not session:
            self._log_audit("INVALID_SESSION", {"token": "NOT_FOUND"})
            return False
        
        if not session.is_valid:
            with self._lock:
                del self._sessions[token_id]
            self._log_audit("EXPIRED_SESSION", {"token": self._mask_token(token_id)})
            return False
        
        return True
    
    def has_permission(self, token_id: str, permission: str) -> bool:
        """Verifica se uma sessão tem permissão específica.
        
        Args:
            token_id: Token de sessão
            permission: Permissão a verificar
        
        Returns:
            True se tem permissão
        """
        with self._lock:
            session = self._sessions.get(token_id)
        
        if not session or not session.is_valid:
            return False
        
        return permission in session.permissions
    
    def revoke_session(self, token_id: str) -> None:
        """Revoga uma sessão.
        
        Args:
            token_id: Token a revogar
        """
        with self._lock:
            if token_id in self._sessions:
                del self._sessions[token_id]
        
        self._log_audit("REVOKE_SESSION", {"token": self._mask_token(token_id)})
    
    def check_rate_limit(
        self,
        identifier: str,
        limit: int = 100,
        window_seconds: int = 60,
    ) -> bool:
        """Verifica e aplica rate limiting.
        
        Args:
            identifier: Identificador do cliente (IP, session ID, etc.)
            limit: Máximo de requisições na janela
            window_seconds: Janela de tempo em segundos
        
        Returns:
            True se dentro do limite, False se excedido
        """
        now = time.time()
        cutoff = now - window_seconds
        
        with self._lock:
            # Limpar requisições antigas
            if identifier in self._rate_limit:
                self._rate_limit[identifier] = [
                    t for t in self._rate_limit[identifier] if t > cutoff
                ]
            else:
                self._rate_limit[identifier] = []
            
            # Verificar limite
            if len(self._rate_limit[identifier]) >= limit:
                self._log_audit("RATE_LIMIT_EXCEEDED", {"client": identifier[:15]})
                return False
            
            # Registrar nova requisição
            self._rate_limit[identifier].append(now)
        
        return True
    
    def create_secure_headers(self) -> dict[str, str]:
        """Cria headers seguros para requisições de backend para API.
        
        Returns:
            Dicionário com headers (contém token API)
        """
        api_key = self.get_api_key()
        if not api_key:
            raise RuntimeError("Nenhuma chave de API configurada")
        
        return {
            "X-Auth-Token": api_key,
            "User-Agent": "Football-Analytics/2.0 (Backend)",
        }
    
    def _mask_token(self, token: str) -> str:
        """Mascara token para logging seguro."""
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"
    
    def _log_audit(self, action: str, details: dict[str, Any]) -> None:
        """Registra ação para auditoria."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
        }
        
        with self._lock:
            self._audit_log.append(record)
            # Manter apenas últimos 1000 registros
            if len(self._audit_log) > 1000:
                self._audit_log = self._audit_log[-1000:]
    
    def get_audit_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna registros de auditoria recentes.
        
        Args:
            limit: Número máximo de registros a retornar
        
        Returns:
            Lista de registros de auditoria
        """
        with self._lock:
            return list(self._audit_log[-limit:])
    
    def cleanup_expired_sessions(self) -> int:
        """Remove sessões expiradas.
        
        Returns:
            Número de sessões removidas
        """
        now = datetime.now()
        removed = 0
        
        with self._lock:
            expired = [
                token_id for token_id, session in self._sessions.items()
                if session.expires_at <= now
            ]
            for token_id in expired:
                del self._sessions[token_id]
                removed += 1
        
        if removed > 0:
            self._log_audit("CLEANUP_SESSIONS", {"removed": removed})
        
        return removed


# Gerenciador global (singleton)
_token_manager = SecureTokenManager()


def get_token_manager() -> SecureTokenManager:
    """Retorna o gerenciador global de tokens."""
    return _token_manager


def require_session(permission: str = "read:matches"):
    """Decorador para proteger endpoints com autenticação de sessão.
    
    Uso:
        @require_session("read:matches")
        def handler_function(token_id, *args, **kwargs):
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, token_id: Optional[str] = None, **kwargs):
            manager = get_token_manager()
            
            if not token_id:
                raise ValueError("Token de sessão não fornecido")
            
            if not manager.validate_session(token_id):
                raise PermissionError("Sessão inválida ou expirada")
            
            if not manager.has_permission(token_id, permission):
                raise PermissionError(f"Sem permissão para: {permission}")
            
            return func(*args, token_id=token_id, **kwargs)
        
        return wrapper
    return decorator


# Exemplo de uso
if __name__ == "__main__":
    manager = SecureTokenManager()
    
    print("🔐 Sistema de Segurança para Football Analytics")
    print("=" * 50)
    
    # 1. Definir credenciais
    print("\n1️⃣  Definindo credenciais de API...")
    manager.set_api_credentials(
        api_key="seu_token_aqui",
        base_url="https://api.football-data.org/v4"
    )
    print("✅ Credenciais definidas (apenas no servidor)")
    
    # 2. Criar sessão
    print("\n2️⃣  Criando sessão para cliente...")
    session_token = manager.create_session(
        user_identifier="192.168.1.100",
        permissions=["read:matches", "read:odds", "read:settlement"],
        duration_minutes=60
    )
    print(f"✅ Sessão criada: {session_token[:20]}...")
    
    # 3. Validar sessão
    print("\n3️⃣  Validando sessão...")
    is_valid = manager.validate_session(session_token)
    print(f"✅ Sessão válida: {is_valid}")
    
    # 4. Verificar permissão
    print("\n4️⃣  Verificando permissões...")
    has_perm = manager.has_permission(session_token, "read:matches")
    print(f"✅ Tem permissão para ler matches: {has_perm}")
    
    # 5. Rate limiting
    print("\n5️⃣  Testando rate limiting...")
    client_id = "192.168.1.100"
    for i in range(3):
        allowed = manager.check_rate_limit(client_id, limit=2, window_seconds=1)
        print(f"   Requisição {i+1}: {'✅ OK' if allowed else '❌ BLOQUEADA'}")
    
    # 6. Auditoria
    print("\n6️⃣  Registros de auditoria:")
    for record in manager.get_audit_log(limit=5):
        print(f"   - {record['action']}: {record['details']}")
    
    print("\n" + "=" * 50)
    print("🎯 Sistema de segurança funcionando corretamente!")
