# Bethel Eritrean Alliance Church — CRM & Building Fund

A Django website for Bethel Eritrean Alliance Church Atlanta with three parts:

1. **Public website and giving page** — church story, ministries, eldership, and a live building fund page with a progress ring, online giving (Stripe), pledges, and Zelle / check instructions.
2. **Building fund portal** for the Pastor and CFO — record every gift (cash, check, Zelle, online), track pledges, print tax receipts and year-end statements, export to CSV.
3. **Ministry portals** — each ministry leader logs in and records activities (attendance, volunteer hours, notes, follow-ups) and keeps a roster for their ministry only.
4. **Activities, Calendar, Upcoming events and Resources** for the whole church (see below).

## Portal menu

| Menu | What it does |
|---|---|
| Dashboard | Fund progress, the next two weeks of events, ministry summary, latest activity |
| Ministries ▸ | Expands to list every ministry; each opens its portal (activity log, roster, upcoming events, resources) |
| Activities | Every recorded activity across the ministries you can see, with filters (ministry, type, period, needs follow-up) and CSV export |
| Calendar | Month view of all events, color-coded by ministry; optionally overlays recorded activities. Click + on a day to add an event |
| Upcoming events | The next 30 or 90 days as a list, filterable by ministry |
| Resources | Shared files and links (lessons, forms, policies, song lists, minutes) with access levels |
| Building fund ▸ | Overview, Donations, Donors, Pledges (Pastor and Finance); elders see the overview only |

**Events** can repeat every week, every 2 weeks or every month (e.g. Sunday service, choir rehearsal, elders' meeting). Tick *Show on the public website* to list an event on the public Events page and home page, with an "Add to calendar" button. The Pastor and elders can create church-wide events; ministry leaders create events for their own ministries.

**Resources** have three access levels: everyone with a login, leadership only, or only that ministry's leaders (plus the Pastor and elders). Files are never publicly linked; every download checks the person's access.

## Who can see what

| Role | Who (from the org chart) | Access |
|---|---|---|
| Pastor / Administrator | Pastor Abraham | Everything, plus creating logins on **Team & logins** |
| Finance | Nahom (CFO) | Building fund: donors, gifts, pledges, receipts, exports |
| Elder | Girmay, Dawit, Robel, Tsegazeab | All ministry portals (read-only) and building fund **totals only** |
| Ministry Leader | Meron, Biniam, Miki, Kibrom, Azieb, Solomon, Pitias | Only the ministries ticked on their login |
| Member | Anyone who signs up | Their own profile and giving history |

Individual donor names and amounts are visible only to the Pastor and Finance.

## Run it on your computer

Requires Python 3.11+.

```bash
cd bethel-crm
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # edit later; works as-is for local testing
python manage.py migrate
python manage.py seed_church --password "Bethel-Demo-2026" --demo
python manage.py runserver
```

Open http://127.0.0.1:8000 and log in as `abraham`, `nahom`, `dawit` or `kibrom` with password `Bethel-Demo-2026` to see each role.
`--demo` adds fake donors, gifts and activities for testing; to start clean, delete `db.sqlite3` and rerun without `--demo`.

Run the tests with `python manage.py test`.

## Go live

### 1. Database: Supabase (you already have it)
Supabase → Project Settings → Database → **Connection string → Session pooler (URI)**. Use it as `DATABASE_URL`. Django creates its own tables; Supabase Auth isn't used (Django handles logins).

### 2. Hosting: Render (recommended over Vercel for Django)
1. Push this folder to a GitHub repository.
2. In Render: **New → Blueprint**, pick the repo. `render.yaml` sets everything up.
3. In the service's **Environment** tab paste `DATABASE_URL`, and set `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` to your real domain.
4. After the first deploy, open **Shell** and give the Pastor a password:
   ```bash
   python manage.py changepassword abraham
   ```
   Then log in as Pastor Abraham and set everyone else's temporary password on **Team & logins**.

Railway or Fly.io work the same way (`gunicorn config.wsgi:application`).

### 3. Online giving: Stripe
1. Create a Stripe account for the church (use the church's EIN and bank account). Stripe offers discounted nonprofit pricing — email them with your 501(c)(3) letter.
2. Put `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` in the environment.
3. Stripe → Developers → Webhooks → Add endpoint: `https://YOUR-DOMAIN/stripe/webhook/`, events
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`.
   Copy the signing secret into `STRIPE_WEBHOOK_SECRET`.
4. In Stripe → Settings → Payment methods, turn on cards, Apple Pay / Google Pay and US bank account (ACH has lower fees for large gifts).

Until Stripe keys are set, the giving page shows Zelle / check / cash instructions and the pledge form.

### 4. File storage for Resources
Locally, uploads go to the `media/` folder. Render's disk is wiped on every deploy, so in production store files in a **private** Supabase Storage bucket: Supabase → Storage → New bucket `resources` (private) → Storage settings → S3 access keys. Then set the `SUPABASE_S3_*` variables from `.env.example`. Until then, add Google Drive or YouTube links as resources instead of uploading files.

### 5. Church details and email
Set `CHURCH_EIN`, `CHURCH_ZELLE`, `CHURCH_MAILING_ADDRESS`, etc. (see `.env.example`). Configure SMTP so online donors get emailed receipts and leaders can reset passwords.

### 6. The building fund goal
The goal is seeded at **$1,500,000** as a placeholder with the **$200,000** members have already saved counted as the opening balance. Change both on **Building fund → Edit campaign** once you know the purchase price.

## Project layout

```
config/        settings and URLs
accounts/      users, roles, login/registration, Team & logins page
ministries/    ministries, activity log, rosters, all-activities page
events/        events, repeats, calendar, upcoming list, public events page
resources/     shared files and links with access levels
fundraising/   campaigns, donors, pledges, donations, Stripe, receipts
core/          home page, portal dashboard, seed_church command, template helpers
templates/     all HTML
static/        CSS and the church logo
```

## Ideas for next steps
- Monthly recurring online gifts (Stripe subscriptions) for pledgers
- Automatic pledge reminder emails
- SMS updates to members (Twilio)
- Membership directory and family records
- RSVPs / volunteer sign-ups on events
