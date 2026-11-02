# Running Taste on AWS

A plan for hosting Taste, with monthly cost estimates from 1 to 10,000 users.

**Prices** are AWS us-east-1 on-demand list prices and Anthropic's published Sonnet 5.5 rates, as of late 2026. They're estimates: check the AWS Pricing Calculator before committing. Taxes are excluded, and free-tier credits aren't counted, except for the always-free CloudFront allowance.

## What has to run

| Piece | What it is | Notes |
|---|---|---|
| Web app | A static site: `npm run export:web` builds it into `dist/` | Megabytes, no server |
| API | One Python process (FastAPI): catalogues in memory, models fitted per request | About 1 GB RAM with the book catalogue; ratings refit in about 100 ms |
| Database | Postgres: accounts, sessions, ratings, shelf scans (with an 800px photo each) | Tiny: tens of MB even at 10k users |
| Catalogue data | `data/book/*` and `data/genomes/book/truegenome/` | About 100 MB, read-only; changes when the genome or Open Library refresh changes |
| Shelf scans | One Claude Sonnet 5.5 call per photo | Billed per token by Anthropic, not AWS |
| Daily job | `scripts/clean_up.py` | Seconds a day |
| Phone apps | EAS Build, App Store / Play Store | Apple Developer: $99/yr. Google Play: $25 once |

## Recommended architecture

```
          taste.app ──▶ CloudFront ──▶ S3 (web app)
      api.taste.app ──▶ ALB (HTTPS, ACM cert) ──▶ ECS Fargate (ARM): the API container
                                                   │  catalogue data baked into the image
                                                   ├──▶ RDS PostgreSQL
                                                   └──▶ Anthropic API (shelf scans)
   SSM Parameter Store: ANTHROPIC_API_KEY, TASTE_SECRET, DB password
   EventBridge Scheduler ──▶ daily ECS task: clean_up.py
```

- **Same site.** The web app and API sit on `taste.app` and `api.taste.app`, so the HttpOnly session cookie is first-party (see README, Accounts). Set `CORS_ORIGINS=["https://taste.app"]`.
- **Fargate, not EC2:** no servers to patch, and deploying is pushing an image. Use ARM (Graviton), which is about 20% cheaper. Tasks run in public subnets with security groups, which avoids a NAT gateway: about $32/mo each plus data.
- **RDS,** not Postgres on a box: backups, patching and point-in-time restore come built in. Start single-AZ, and go Multi-AZ once people depend on it.
- **Catalogue data in the image.** Refreshing the data becomes a redeploy, so it's versioned and there's no shared file system to run.
- **Secrets** go in SSM Parameter Store (free at this scale), not baked into images.

### Before running more than one API task (from about 1,000 users)
Two things live in the API process's memory today:
- the shelf-scan job queue;
- the sign-in rate limiter.

With two tasks behind the load balancer, a scan started on one task could be polled on the other. Before scaling out:
- **Scan jobs:** store them in Postgres (a `scan_jobs` table) or SQS, with a worker. That's about a day's work.
- **Rate limits:** move them to AWS WAF rate-based rules (about $10/mo), or to Postgres or Redis.

Until then, run one task. It handles hundreds of requests per second, which is plenty for 1,000 users.

## Usage assumptions

| | Per monthly-active user |
|---|---|
| Share of registered users active in a month | 50% |
| API requests | ~300 (browsing, rating, book pages) |
| Shelf scans | 3 |
| Claude cost per scan | **~$0.035**: ~5,000 input tokens (a 2,576px photo, about 4,800 image tokens, plus the prompt) at $2/MTok, plus ~2,500 output tokens (the book list and thinking at `medium` effort) at $10/MTok |

**Claude is the cost to watch.** Everything else grows slowly; scans grow linearly with use. The levers, cheapest first:
- `TASTE_SHELF_EFFORT=low`, which means fewer thinking tokens;
- a smaller photo, e.g. 1,600px: fewer image tokens, at some risk to small spine text;
- Claude Haiku 5.5 (`TASTE_SHELF_MODEL=claude-haiku-5-5`, $0.10/$0.50 per MTok, about 20x cheaper);
- a per-user monthly scan limit.

Test reading quality on a few real shelf photos before switching models.

## Monthly cost by size

### 1 user (baseline)
At this size the fixed costs of managed services dominate, so there are two options.

| | **A. Single small server** | **B. Managed (recommended architecture)** |
|---|---|---|
| Compute | EC2 t4g.small (2 vCPU, 2 GB), API + Postgres via `docker compose`, Caddy for HTTPS: $12.26 | Fargate 0.5 vCPU / 2 GB: $17.00 |
| Load balancer | none (Caddy on the box) | ALB $16.43 + ~1 LCU $5.84 = $22.27 |
| Database | on the box (EBS 20 GB gp3 $1.60, daily snapshots ~$0.50) | RDS db.t4g.micro single-AZ $11.68 + 20 GB $2.30 = $13.98 |
| Public IPv4 | 1 × $3.65 | ALB 2 + task 1 = $10.95 |
| Web (S3 + CloudFront), DNS, logs, registry | ~$1.50 | ~$2.00 |
| **AWS total** | **~$20** | **~$66** |
| Claude (3 scans) | $0.11 | $0.11 |
| **Total** | **~$20/mo** | **~$66/mo** |

Plus, for either option: Apple Developer at $99/yr (about $8/mo) once you ship to iOS, and a domain at about $15/yr.

**Option A** is fine while it's you and a few testers. Its costs: the box is a single point of failure, you patch it, and you set up backups (EBS snapshots via Data Lifecycle Manager). **Option B** costs about $45/mo more, which buys never thinking about servers. Moving from A to B later is a `pg_dump` and a DNS change.

### All sizes (Option B from 100 users)

| Users (registered) | 1 | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| Monthly active | 1 | 5 | 50 | 500 | 5,000 |
| Scans per month | 3 | 15 | 150 | 1,500 | 15,000 |
| API | 0.5 vCPU/2 GB ×1 | same | same | 1 vCPU/2 GB ×2 * | 1 vCPU/2 GB ×2–4, avg 3 * |
| Database | t4g.micro | t4g.micro | t4g.micro | t4g.small Multi-AZ | t4g.medium Multi-AZ, 50 GB |
| Fargate | $17 | $17 | $17 | $58 | $86 |
| ALB | $22 | $22 | $22 | $25 | $35 |
| RDS | $14 | $14 | $14 | $51 | $107 |
| Public IPv4 | $11 | $11 | $11 | $15 | $18 |
| Web, DNS, logs, registry, WAF | $2 | $2 | $3 | $15 | $30 |
| **AWS** | **$66** | **$66** | **$67** | **$164** | **$276** |
| **Claude (scans)** | **$0.11** | **$0.53** | **$5** | **$53** | **$525** |
| **Total / month** | **~$66** | **~$67** | **~$72** | **~$217** | **~$801** |
| Per registered user | $66 | $6.70 | $0.72 | $0.22 | $0.08 |
| With Option A instead | ~$20 | ~$21 | ~$26 | n/a | n/a |

\* Needs the shared scan-job queue and rate limiter first (above).

**Reading the table:**
- **Up to about 100 users the bill is flat.** It's the minimum price of a managed stack, or about $20 on a single server.
- **At 1,000 users,** the step up is mostly a Multi-AZ database and a second API task for availability, not load.
- **At 10,000 users, Claude is about two-thirds of the bill.** Effort `low` or Haiku 5.5 could cut that $525 to roughly $300 or $30, if the reading quality holds.
- **Cover images aren't our bandwidth:** they load from Open Library's servers. The web app itself is a few MB per user, well inside CloudFront's always-free 1 TB a month. If Open Library's covers ever need caching, an S3 + CloudFront cache adds a few dollars.
- **Savings plans:** a 1-year Compute Savings Plan (about 20% off Fargate) and RDS reserved instances (about 30–40% off) are worth it once the setup is stable, typically at 1,000 users.

## Setting it up (Option B), in order
1. Register the domain in Route 53, and get an ACM certificate for `taste.app` and `*.taste.app` (free).
2. **Web:**
   - Create an S3 bucket with CloudFront and a single-page-app fallback to `index.html`.
   - Build it with `EXPO_PUBLIC_API_URL=https://api.taste.app npm run export:web`, then `aws s3 sync dist/ s3://…` and invalidate the CloudFront cache.
3. **Database:** RDS PostgreSQL 16, db.t4g.micro, in private subnets, reachable only from the API's security group. Turn on automated backups (7 days).
4. **Secrets** in SSM Parameter Store:
   - `TASTE_DATABASE_URL`;
   - `TASTE_SECRET` (`python -c "import secrets; print(secrets.token_hex(32))"`);
   - `ANTHROPIC_API_KEY`;
   - `TASTE_APPLE_CLIENT_IDS` and `TASTE_GOOGLE_CLIENT_IDS`.
5. **Image:** build `backend/Dockerfile` for `linux/arm64` with the catalogue data copied into `/data`, and push it to ECR.
6. **ECS:**
   - A cluster, plus a service on Fargate ARM: 0.5 vCPU / 2 GB, one task, behind an ALB on `api.taste.app`, with a health check on `/health`.
   - Secrets come in from SSM. Set `CORS_ORIGINS=["https://taste.app"]`, and **never** `TASTE_DEV_LOGIN`.
   - Migrations run when the container starts.
7. **Daily clean-up:** EventBridge Scheduler runs a one-off ECS task (`python scripts/clean_up.py`) daily.
8. **Monitoring:**
   - CloudWatch alarms on ALB 5xx errors, RDS CPU and free storage.
   - An AWS Budgets alert, e.g. at $100/mo.
   - Anthropic's usage dashboard, plus a spend limit on the API key.

Infrastructure-as-code (AWS CDK in Python, or Terraform) is worth adding when you do this for real, so the setup is reviewable and repeatable.
