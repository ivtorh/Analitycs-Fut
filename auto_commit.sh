#!/bin/bash

# Script para ativar auto-commit em Linux/Mac

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================================${NC}"
echo -e "${BLUE} ⚽ SISTEMA DE AUTO-COMMIT - FOOTBALL ANALYTICS${NC}"
echo -e "${BLUE}=====================================================${NC}"
echo ""

# Verificar se Python está instalado
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python não está instalado${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python encontrado$(python3 --version)${NC}"

# Verificar se Git está instalado
if ! command -v git &> /dev/null; then
    echo -e "${RED}❌ Git não está instalado${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Git encontrado ($(git --version))${NC}"
echo ""

# Determinar modo de execução
if [ "$1" == "dry-run" ]; then
    echo -e "${YELLOW}⚠️  MODO DRY-RUN: Nenhum commit será feito de verdade${NC}"
    echo ""
    echo "Iniciando em modo de teste..."
    python3 auto_commit.py --dry-run
else
    echo -e "${GREEN}🟢 MODO NORMAL: Commits reais serão feitos${NC}"
    echo ""
    echo "Iniciando sistema de auto-commit..."
    python3 auto_commit.py
fi

if [ $? -ne 0 ]; then
    echo ""
    echo -e "${RED}❌ Erro ao executar auto-commit${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✅ Auto-commit finalizado${NC}"
