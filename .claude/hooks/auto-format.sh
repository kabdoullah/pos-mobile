#!/usr/bin/env bash
# Hook PostToolUse : formate automatiquement les fichiers édités par Claude.
#
# Usage : auto-format.sh "<paths_separated_by_space>"
#
# Conventions :
# - Backend (Python) : ruff format + ruff check --fix
# - Mobile (Dart)    : dart format
#
# En cas d'échec : log mais ne bloque pas (PostToolUse n'est pas bloquant).

set -uo pipefail

paths="${1:-}"
if [ -z "$paths" ]; then
    exit 0
fi

# Trouver la racine du projet (cherche le CLAUDE.md)
project_root="$PWD"
while [ "$project_root" != "/" ] && [ ! -f "$project_root/CLAUDE.md" ]; do
    project_root="$(dirname "$project_root")"
done

if [ ! -f "$project_root/CLAUDE.md" ]; then
    # Pas dans le projet, ne rien faire
    exit 0
fi

py_files=()
dart_files=()

# Splitter les paths (séparés par espaces ou newlines)
IFS=$'\n\t '
for path in $paths; do
    # Skip si le fichier n'existe pas (ex: vient d'être supprimé)
    [ ! -f "$path" ] && continue

    case "$path" in
        *.py)
            py_files+=("$path")
            ;;
        *.dart)
            # Skip les fichiers générés
            case "$path" in
                *.g.dart|*.freezed.dart|*.config.dart) ;;
                *) dart_files+=("$path") ;;
            esac
            ;;
    esac
done

# Format Python avec ruff (via uv si dispo)
if [ ${#py_files[@]} -gt 0 ]; then
    cd "$project_root/backend" 2>/dev/null || exit 0
    if command -v uv >/dev/null 2>&1; then
        uv run ruff format "${py_files[@]}" >/dev/null 2>&1 || true
        uv run ruff check --fix "${py_files[@]}" >/dev/null 2>&1 || true
    elif command -v ruff >/dev/null 2>&1; then
        ruff format "${py_files[@]}" >/dev/null 2>&1 || true
        ruff check --fix "${py_files[@]}" >/dev/null 2>&1 || true
    fi
fi

# Format Dart
if [ ${#dart_files[@]} -gt 0 ] && command -v dart >/dev/null 2>&1; then
    dart format "${dart_files[@]}" >/dev/null 2>&1 || true
fi

exit 0
