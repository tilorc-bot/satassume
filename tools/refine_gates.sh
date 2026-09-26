#!/usr/bin/env bash
# Moved to satrefine/tools/refine_gates.sh; this shim (kept for phase 3) runs it with the same arguments.
exec "$(dirname "$0")/../satrefine/tools/refine_gates.sh" "$@"
