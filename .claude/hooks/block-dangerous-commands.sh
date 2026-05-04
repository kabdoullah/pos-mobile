#!/usr/bin/env bash
# Hook PreToolUse : bloque les commandes destructrices avant exécution.
#
# Exit code :
#   0 = autorisé
#   2 = bloqué (Claude Code recevra le message stderr)

set -uo pipefail

input="${1:-}"

# Liste des patterns interdits (regex)
# Format : "pattern|raison"
declare -a forbidden=(
    "rm -rf /|rm -rf sur le filesystem racine"
    "rm -rf \\*|rm -rf wildcard à la racine du repo"
    "rm -rf \\.|rm -rf sur le répertoire courant"
    "git push.*--force.*main|push --force sur main interdit"
    "git push.*-f.*main|push -f sur main interdit"
    "DROP DATABASE|DROP DATABASE manuel sans backup interdit"
    "TRUNCATE.*sales|TRUNCATE de la table sales (données comptables immuables) interdit"
    "DELETE FROM sales|DELETE de la table sales (données comptables immuables) interdit"
    "alembic downgrade base|downgrade complet de toutes les migrations sans confirmation"
    "docker compose down -v|down -v supprime les volumes (DB) — utiliser docker compose down sans -v"
)

# Patterns qui demandent une confirmation explicite (warning, pas blocage)
declare -a warning=(
    "alembic downgrade|downgrade Alembic — vérifier qu'un backup récent existe"
    "DROP TABLE|DROP TABLE — vérifier qu'un backup récent existe"
    "git reset --hard|reset --hard — vérifier qu'aucun travail non commit n'est perdu"
)

for entry in "${forbidden[@]}"; do
    pattern="${entry%%|*}"
    reason="${entry#*|}"
    if echo "$input" | grep -qE "$pattern"; then
        echo "❌ Commande bloquée par le hook .claude/hooks/block-dangerous-commands.sh" >&2
        echo "   Raison : $reason" >&2
        echo "   Si vraiment nécessaire, exécuter manuellement après confirmation." >&2
        exit 2
    fi
done

for entry in "${warning[@]}"; do
    pattern="${entry%%|*}"
    reason="${entry#*|}"
    if echo "$input" | grep -qE "$pattern"; then
        echo "⚠️  Attention : $reason" >&2
        # Pas de exit 2, on laisse passer mais on signale
    fi
done

exit 0
