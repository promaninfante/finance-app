# Finance App

Personal finance automation: drop a bank PDF → transactions are extracted, categorized, and reviewable in a mobile PWA.

## Stack

| Layer | Technology |
|---|---|
| Compute | AWS Lambda (Python 3.12, arm64) via AWS SAM |
| Database + Auth | Supabase (PostgreSQL, RLS, Realtime) |
| LLM | AWS Bedrock (Claude Haiku) |
| PWA | React + TypeScript (Vite), AWS Amplify |
| Notifications | Telegram bot |
| Region | eu-west-1 (Ireland) |
| Secrets | AWS SSM Parameter Store (SecureString) |

## Prerequisites

- AWS CLI v2, configured with profile `finance` pointing to `eu-west-1`
- SAM CLI (`sam --version`)
- Python 3.12
- Node.js 20 LTS

## Quick start

```bash
# Validate the SAM template
sam validate --region eu-west-1 --profile finance

# Build all Lambda functions
sam build

# Deploy (first time — guided)
sam deploy --guided

# Deploy (subsequent)
sam deploy
```

## Project structure

```
finance-app/
├── template.yaml          # SAM template — all Lambda functions declared here
├── samconfig.toml         # SAM deployment defaults
├── src/
│   ├── ingest/            # PDF → transactions Lambda (Milestone C/D/E)
│   ├── daily_cron/        # Budget pace + anomaly checks (Milestone I)
│   ├── weekly_digest/     # Sunday digest (Milestone K)
│   ├── telegram_bot/      # Telegram webhook (Milestone J)
│   ├── backup/            # Weekly pg_dump to S3 (Milestone M)
│   └── shared/            # Utilities shared across Lambdas
└── pwa/                   # React + Vite PWA (Milestones F/G/H)
```

## Milestone progress

- [x] **A** — Foundations & Scaffolding
- [ ] **B** — Database schema (Supabase)
- [ ] **C** — Ingestion happy path
- [ ] **D** — PDF extraction
- [ ] **E** — Classification
- [ ] **F** — Review PWA
- [ ] **G** — Dashboard
- [ ] **H** — Budgets
- [ ] **I** — Proactive warnings
- [ ] **J** — Telegram bot
- [ ] **K** — Weekly digest
