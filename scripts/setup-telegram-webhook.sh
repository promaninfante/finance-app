#!/usr/bin/env bash
# Register Telegram webhook after deploying the bot Lambda.
# Run once after `sam deploy` to point Telegram at the Function URL.
#
# Usage:
#   export TELEGRAM_TOKEN="<your bot token>"
#   export TELEGRAM_WEBHOOK_URL="<TelegramBotFn Function URL from SAM outputs>"
#   export TELEGRAM_WEBHOOK_SECRET="<value of /finance/telegram_webhook_secret in SSM>"
#   ./scripts/setup-telegram-webhook.sh

set -euo pipefail

: "${TELEGRAM_TOKEN:?TELEGRAM_TOKEN is not set}"
: "${TELEGRAM_WEBHOOK_URL:?TELEGRAM_WEBHOOK_URL is not set}"
: "${TELEGRAM_WEBHOOK_SECRET:?TELEGRAM_WEBHOOK_SECRET is not set}"

curl -s -X POST \
  "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook" \
  -d "url=${TELEGRAM_WEBHOOK_URL}&secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
  | python3 -m json.tool

echo ""
echo "Webhook registered. Verify with:"
echo "  curl https://api.telegram.org/bot\${TELEGRAM_TOKEN}/getWebhookInfo"
