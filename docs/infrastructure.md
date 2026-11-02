# Running Taste on AWS

A plan for hosting Taste, with monthly cost estimates from 1 to 10,000 users.

**Prices** are AWS us-east-1 on-demand list prices and Anthropic's published Sonnet 5.5 rates, as of late 2026. They're estimates: check the AWS Pricing Calculator before committing. Taxes are excluded.

## The short version

**Start with one small server plus a managed database (~$28/month), and move to fully managed services around 1,000 users.**

A fully managed setup (Fargate + load balancer + RDS) costs about $66/month even with one user. Almost all of that is fixed overhead:

| Overhead | Monthly |
|---|---|
| Load balancer | ~$22 |
| Public IP addresses | ~$11 |
| Managed database | ~$14 |
| Container | ~$17 |

None of it is needed until there's real traffic or a need for high availability.

## What has to run

| Piece | Size |
|---|---|
| API (FastAPI, one process) | ~250 MB RAM measured: the book catalogue in memory, a model fitted per request (about 100 ms) |
| Postgres | Tiny: tens of MB even at 10k users |
| Web app | A static site (`npm run export:web`): a few MB |
| Catalogue data | About 100 MB, read-only |
| Shelf scans | One Claude Sonnet 5.5 call per photo (20–40 s, an ordinary request), billed by Anthropic, at most 5 per user per hour |
| Daily job | `scripts/clean_up.py`, seconds |

## Stage 1: one Lightsail server and a Lightsail database (1 to ~1,000 users)

```
taste.app / api.taste.app ──▶ Lightsail instance (2 GB, static IP)
                              ├─ Caddy: HTTPS (free Let's Encrypt certs), serves the web app,
                              │         proxies api.taste.app to the API
                              └─ API container (docker compose)
                                     │  private network, TLS
                                     ▼
                              Lightsail managed Postgres 16 (not publicly reachable)
                              automatic daily backups + point-in-time restore
```

**Why Lightsail rather than EC2 and RDS:** the same machines, but at flat prices that include the static IPv4 address, 3 TB of data transfer, the disks and the database's backups. The bill is predictable, and cheaper once you add those up on EC2/RDS.

**Why the database is separate:**
- The API and the database don't compete for memory or CPU.
- AWS patches and backs up the database. Point-in-time restore means losing minutes of ratings at worst, not a day.
- The server holds nothing you can't rebuild from git and `.env`: if it breaks, make a new one.
- Upgrading or replacing the server, and the deploys below, never touch the data.

| Line | Monthly |
|---|---|
| Lightsail Linux, 2 GB RAM / 2 vCPU / 60 GB SSD / 3 TB transfer, static IPv4 included | $12.00 |
| Lightsail managed database, Standard (1 GB RAM / 2 vCPU / 40 GB SSD), backups included | $15.00 |
| Route 53 hosted zone | $0.50 |
| **AWS total** | **~$28** |

**Setting it up:**
- **Database:** create a Lightsail PostgreSQL 16 database in the same region, with public mode **off** (only your Lightsail resources can reach it). Create a `taste` database on it.
- **Server:** create the instance (Ubuntu), attach a static IP, and open ports 80 and 443 only. Install Docker.
- **App:** `git clone`, add a production `.env` (no `TASTE_DEV_LOGIN`; the API refuses to start with it) with `TASTE_DATABASE_URL=postgresql+psycopg://<user>:<password>@<database endpoint>:5432/taste?sslmode=require`, then `docker compose up -d`. Migrations run when the API starts, and compose keeps the API on localhost.
- **Caddy:**
  - It serves `dist/` (the exported web app) for `taste.app`.
  - It proxies `api.taste.app` to `localhost:8000`.
  - In `.env`, set `FORWARDED_ALLOW_IPS` to the Docker bridge network (e.g. `172.16.0.0/12`), so sign-in rate limits see real client IPs.
- **Cron:** `docker compose exec api python scripts/clean_up.py` daily. Optionally a weekly `pg_dump` to S3 (cents), as a copy outside Lightsail.

**What it gives up:**
- **One API server.** If it dies, the app is down until you start a new one (minutes, with no data lost).
- **A single-zone database.** A database outage means waiting for AWS to recover it, or restoring a backup. The high-availability plan ($30) adds a standby in a second zone.
- **You patch the server:** turn on `unattended-upgrades`.

At this size those trade-offs are fine.

**Cheaper:**
- **1 GB Lightsail ($7/mo):** fits the API (about 250 MB) and Caddy, but leaves no room to run a second copy during a deploy.
- **Postgres on the server, not managed (−$15/mo):** `docker compose --profile local-db up -d` runs it beside the API, with nightly `pg_dump` to S3 (cents). The API and database then share the machine, and a lost server can lose up to a day of ratings.
- **Free hosting for the web app:** S3 + CloudFront serves it for free at this traffic, instead of from the box.

## Stage 2: managed services (from ~1,000 users, or when downtime starts to matter)

```
taste.app ──▶ CloudFront ──▶ S3 (web app)
api.taste.app ──▶ ALB (HTTPS) ──▶ ECS Fargate (ARM), 2+ tasks ──▶ RDS PostgreSQL (Multi-AZ)
secrets: SSM Parameter Store      daily: EventBridge Scheduler ──▶ clean_up task
```

- **First:** move the sign-in rate limiter out of the API's memory, and make the hourly scan count atomic in Postgres (a row lock), so they hold across tasks. A few hours' work.
- **Uvicorn behind the ALB:** set `FORWARDED_ALLOW_IPS` to the VPC's range (e.g. `10.0.0.0/16`).
- **Moving over** is a `pg_dump`/restore from Lightsail into RDS, and a DNS change.

## Shelf-scan cost (Anthropic)

| Assumption | Value |
|---|---|
| Users active in a month | 50% of registered |
| Scans per active user per month | 3 (hard cap: 5 an hour) |
| Cost per scan | **~$0.035**: ~5,000 input tokens (a 2,576px photo plus the prompt) at $2/MTok, plus ~2,500 output tokens (the book list and thinking at `medium` effort) at $10/MTok |

**This is the cost that grows with use.** The levers:
- `TASTE_SHELF_EFFORT=low`;
- a smaller photo;
- Claude Haiku 5.5 (`TASTE_SHELF_MODEL=claude-haiku-5-5`, about 20x cheaper), after checking it reads spines as well.

Set a monthly spend limit on the Anthropic API key either way.

## Monthly cost by size

| Users (registered) | 1 | 10 | 100 | 1,000 | 10,000 |
|---|---|---|---|---|---|
| Setup | Lightsail 2 GB | Lightsail 2 GB | Lightsail 2 GB | Lightsail 4 GB, or Stage 2 | Stage 2 |
| AWS | $28 | $28 | $28 | $40 (Lightsail) / $164 (Stage 2) | $276 |
| Claude scans | $0.11 | $0.53 | $5 | $53 | $525 |
| **Total / month** | **~$28** | **~$29** | **~$33** | **~$93 / ~$217** | **~$801** |

**Stage 2 at 10,000 users** breaks down as:
- Fargate (2–4 tasks, 1 vCPU / 2 GB): $86;
- RDS db.t4g.medium Multi-AZ, 50 GB: $107;
- ALB: $35;
- public IPs: $18;
- logs, DNS, CloudFront, WAF: $30.

A 1-year Savings Plan and RDS reservation cut about 25% of that once it's stable.

**Other fixed costs:**
- Apple Developer: $99/yr (about $8/mo), once you ship to iOS;
- Google Play: $25 once;
- a domain: about $15/yr.

**Reading the table:**
- **Up to a few hundred users,** Taste costs about as much as a streaming subscription.
- **At 1,000 users,** a bigger Lightsail box still works (about $93 in total). Stage 2 (about $217) buys redundancy, not capacity.
- **At 10,000 users, Claude is about two-thirds of the bill.** Scan cost tuning matters more than infrastructure.
