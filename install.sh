#!/usr/bin/env bash
# Enlaza el skill en ~/.claude/skills/ y chequea los requisitos. No toca tus datos.
set -euo pipefail

AQUI="$(cd "$(dirname "$0")" && pwd)"
DESTINO="$HOME/.claude/skills/diario-del-sabado"
DATOS="${DIARIO_HOME:-$HOME/.diario-del-sabado}"

mkdir -p "$HOME/.claude/skills" "$DATOS"
if [ -e "$DESTINO" ] && [ ! -L "$DESTINO" ]; then
  echo "⚠ Ya existe $DESTINO y no es un enlace. Movelo o borralo y volvé a correr." >&2
  exit 1
fi
ln -sfn "$AQUI" "$DESTINO"
echo "✓ Skill enlazado en $DESTINO"
echo "✓ Tus datos van a vivir en $DATOS"
echo

ok() { printf "  ✓ %s\n" "$1"; }
falta() { printf "  ✗ %s → %s\n" "$1" "$2"; }

echo "Requisitos:"
if python3 -c "import sys; sys.exit(sys.version_info < (3, 9))" 2>/dev/null; then
  ok "python3 $(python3 -c 'import platform; print(platform.python_version())')"
else
  falta "python3 3.9+" "instalá Python 3.9 o más nuevo"
fi
python3 -c "import PIL" 2>/dev/null && ok "Pillow" || falta "Pillow" "python3 -m pip install --user Pillow (si pip se niega, usá un venv)"
if command -v gws >/dev/null; then
  PERFIL="$(gws gmail users getProfile --params '{"userId":"me"}' --format json 2>&1 || true)"
  if echo "$PERFIL" | grep -q '"emailAddress"'; then
    ok "gws conectado a Gmail"
  elif echo "$PERFIL" | grep -qE '"code": *40[13]|invalid_grant|No credentials|not authenticated'; then
    falta "gws sin permiso de Gmail" "gws auth setup (una vez) y gws auth login -s gmail"
  else
    falta "gws no respondió" "$(echo "$PERFIL" | grep -m1 -iE 'message|error' | head -c 160)"
  fi
else
  falta "gws" "npm install -g @googleworkspace/cli"
fi
command -v pandoc >/dev/null && ok "pandoc (Kindle)" || echo "  · pandoc no está: solo hace falta para el Kindle (https://pandoc.org/installing.html)"
echo
echo "Listo. Abrí Claude Code y decí: «configurá el diario»."
