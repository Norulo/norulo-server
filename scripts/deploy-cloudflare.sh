#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment=""
execute=0
local_checks=0
activate_production=0
activate_email_auth=0
activate_ai_suggestions=0
activate_recurring_expenses=0
temporary_config=""

cleanup() {
  if [[ -n "$temporary_config" ]]; then rm -f -- "$temporary_config"; fi
}
trap cleanup EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

usage() {
  echo "Usage: $0 --environment preview|production [--execute --local-checks-passed] [--activate-production [--activate-email-auth [--activate-ai-suggestions [--activate-recurring-expenses]]]]" >&2
}

while (($#)); do
  case "$1" in
    --environment)
      (($# >= 2)) || { usage; exit 2; }
      environment="$2"
      shift 2
      ;;
    --execute) execute=1; shift ;;
    --local-checks-passed) local_checks=1; shift ;;
    --activate-production) activate_production=1; shift ;;
    --activate-email-auth) activate_email_auth=1; shift ;;
    --activate-ai-suggestions) activate_ai_suggestions=1; shift ;;
    --activate-recurring-expenses) activate_recurring_expenses=1; shift ;;
    *) usage; exit 2 ;;
  esac
done

[[ "$environment" == preview || "$environment" == production ]] || { usage; exit 2; }
if ((activate_production)) && [[ "$environment" != production ]]; then
  echo "--activate-production requires --environment production." >&2
  exit 2
fi
if ((activate_email_auth)) && { [[ "$environment" != production ]] || ((!activate_production)); }; then
  echo "--activate-email-auth requires --environment production --activate-production." >&2
  exit 2
fi
if ((activate_ai_suggestions)) && { [[ "$environment" != production ]] || ((!activate_production)) || ((!activate_email_auth)); }; then
  echo "--activate-ai-suggestions requires --environment production --activate-production --activate-email-auth." >&2
  exit 2
fi
if ((activate_recurring_expenses)) && { [[ "$environment" != production ]] || ((!activate_production)) || ((!activate_email_auth)) || ((!activate_ai_suggestions)); }; then
  echo "--activate-recurring-expenses requires --environment production --activate-production --activate-email-auth --activate-ai-suggestions." >&2
  exit 2
fi
if ((execute && !local_checks)); then
  echo "Remote execution requires completed local checks (--local-checks-passed)." >&2
  exit 2
fi

cd "$repo_root"
checker_args=(--environment "$environment")
if ((activate_production)); then checker_args+=(--activate-production); fi
if ((activate_email_auth)); then checker_args+=(--activate-email-auth); fi
if ((activate_ai_suggestions)); then checker_args+=(--activate-ai-suggestions); fi
config="wrangler.${environment}.jsonc"
if ((activate_recurring_expenses)); then
  temporary_config="$(mktemp "$repo_root/cloudflare/server/.norulo-recurring-deploy.XXXXXX.jsonc")"
  config="$temporary_config"
  checker_args+=(--activate-recurring-expenses --write-deploy-config "$temporary_config")
fi
if ((!execute)); then checker_args+=(--allow-placeholders); fi
"${NORULO_PYTHON:-python3}" scripts/check-ledger-s01.py "${checker_args[@]}"
# Live paid plans depend on these Creem product IDs. An upload replaces every
# public variable, so never publish production with an empty or partial list.
if [[ "$environment" == production ]] && ((execute)); then
  "${NORULO_PYTHON:-python3}" - "cloudflare/server/wrangler.production.jsonc" <<'PY' || exit 2
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r'"NORULO_CREEM_PRODUCT_IDS_JSON"\s*:\s*("(?:[^"\\]|\\.)*")', text)
products = json.loads(json.loads(match.group(1))) if match else {}
complete = (set(products) == {"pro", "max"} and all(
    isinstance(products[plan], dict) and set(products[plan]) == {"month", "year"}
    and all(isinstance(value, str) and value for value in products[plan].values())
    for plan in products))
if not complete:
    sys.exit("Refusing production deploy: NORULO_CREEM_PRODUCT_IDS_JSON must list pro and max month/year Creem product IDs.")
PY
fi
if ((activate_recurring_expenses)); then
  production_cron="$("${NORULO_PYTHON:-python3}" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["triggers"]["crons"][0])' "$temporary_config")"
fi
deploy_args=(--config "$config")
if ((activate_production)); then deploy_args+=(--var NORULO_D1_ACCESS_ENABLED:1); fi
if ((activate_email_auth)); then deploy_args+=(--var NORULO_EMAIL_AUTH_ENABLED:1); fi
if ((activate_ai_suggestions)); then
  deploy_args+=(--var NORULO_JEV_SUGGESTIONS_ENABLED:1 --var NORULO_JEV_SUGGESTIONS_EVALUATED:1)
fi
if ((activate_recurring_expenses)); then deploy_args+=(--var NORULO_RECURRING_EXPENSES_ENABLED:1); fi
wrangler="cloudflare/server/node_modules/wrangler/wrangler-dist/cli.js"
if ((execute)); then
  [[ -f "$wrangler" ]] || { echo "Pinned local Wrangler installation is missing." >&2; exit 2; }
  command -v uv >/dev/null || { echo "uv is required for pinned Python Worker packaging." >&2; exit 2; }
  "${NORULO_PYTHON:-python3}" cloudflare/server/sync_server_modules.py
  echo "D1 migrations remain outside this command."
  if ((activate_production)); then
    echo "Explicit production D1 activation overlay; the checked-in config remains paused."
    if ((activate_email_auth)); then
      echo "Explicit production email authentication activation overlay; the checked-in email flag remains paused."
    fi
    if ((activate_ai_suggestions)); then
      echo "Explicit production AI suggestions activation overlay; the checked-in AI flags remain paused."
    fi
    if ((activate_recurring_expenses)); then
      echo "Explicit production recurrence activation with one daily UTC cron ($production_cron); the checked-in config has no cron."
    fi
  else
    echo "Runtime switches stay as configured."
  fi
  echo "Deploying Server Worker for $environment"
  cd cloudflare/server
  uv run --frozen --python 3.14.2 pywrangler deploy "${deploy_args[@]}"
else
  echo "Dry run only. After local verification, --execute --local-checks-passed would run:"
  if ((activate_recurring_expenses)); then
    echo "A fresh temporary configuration preserves Worker-relative src/migrations paths and installs one daily UTC cron ($production_cron)."
    echo "This dry-run configuration is removed on exit; execution regenerates and validates it."
    printf 'bash %q --environment production --activate-production --activate-email-auth --activate-ai-suggestions --activate-recurring-expenses --execute --local-checks-passed\n' "$repo_root/scripts/deploy-cloudflare.sh"
    printf 'Validated deployment arguments: '
    printf '%q ' "${deploy_args[@]}"
    printf '\n'
  else
    echo "cd cloudflare/server && uv run --frozen --python 3.14.2 pywrangler deploy ${deploy_args[*]}"
  fi
fi
