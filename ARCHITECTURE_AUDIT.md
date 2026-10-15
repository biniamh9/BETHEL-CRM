# BETHEL-CRM architecture, UX, and security audit

## Executive summary

BETHEL-CRM is a Django 5 application deployed as a Vercel Python function. Production data is PostgreSQL on Supabase; local development defaults to SQLite. Static assets use WhiteNoise. Private uploads can use Supabase Storage through its S3-compatible API. Authentication correctly extends Django's `AbstractUser`, and financial and ministry records already have meaningful server-side authorization checks.

The principal UX defect was architectural: the public navigation linked directly to login-protected portal namespaces. Visitors therefore could not learn about a ministry, browse church activities, or see approved resources without an account. This feature branch separates public discovery from private management while preserving all existing portal URLs.

## Existing strengths

- Django authentication, CSRF middleware, secure password hashing, safe login redirects, and role checks are already in use.
- Ministry leaders are assigned through a many-to-many relationship, so one person can serve multiple ministries.
- Donation details are restricted to finance/admin roles; elders see aggregate information only.
- Ministry portal queries are scoped on the server, not merely hidden in the UI.
- Resource downloads are permission checked and private uploads support persistent Supabase storage.
- Database migrations are additive and the Vercel production build migrates and seeds idempotently.
- Stripe webhooks are covered by replay/idempotency tests.

## Problems and root causes

| Area | Finding | Root cause / risk | Resolution in this branch |
|---|---|---|---|
| Public ministries | Header links redirected visitors to login | Public and portal routes shared the same namespace | Added `/ministries/` public routes; preserved `/portal/ministries/` |
| Ministry privacy | Public discovery could not be added safely to the portal template | Portal pages include participant names, activity notes, and internal resources | New public templates query only public fields, public events, and published announcements |
| Activities | Public header pointed to internal activity reporting | `/portal/activities/` contains attendance and follow-up notes | Added a separate photo-led `/activities/` page |
| Resources | All resources required login | No explicit publication flag | Added opt-in `is_public`; existing records remain private by default |
| Registration | No formal leader access request | Admin promotion was entirely out-of-band | Added pending requests; signup never elevates role or assigns ministries |
| Ministry contact | No secure public workflow | No inquiry model or scoped inbox | Added contact/join inquiries, validation, honeypot, throttling, and portal summary |
| Publishing | No ministry announcement states | Activity log was an operational record, not public content | Added Draft, Pending Review, Published, and Archived states |
| Roles | No team-member label | Existing leader assignment already supported scoped access | Added Ministry Team Member role while preserving existing role behavior |
| Security headers | Baseline was good but incomplete | No explicit referrer policy, SameSite declarations, or numeric-password validator | Added secure defaults without changing sessions or credentials |

## Route structure

Public routes require no login:

- `/ministries/`
- `/ministries/<slug>/`
- `/ministries/<slug>/contact/`
- `/ministries/<slug>/join/`
- `/activities/`
- `/resources/`
- `/resources/<id>/open/` (only explicitly public resources)
- `/events/`

Private routes retain their existing behavior:

- `/portal/`
- `/portal/ministries/`
- `/portal/ministries/<slug>/`
- `/portal/activities/`
- `/portal/resources/`
- `/portal/events/`
- `/portal/fund/`

## Permission model

- Super administrators use Django `is_superuser` and retain unrestricted control.
- Church administrators use the existing `admin` role.
- Ministry leaders and ministry team members receive access only through `Ministry.leaders`; assignment supports multiple ministries.
- Members never receive ministry access during registration.
- Visitors can create an inquiry but cannot read inquiries, rosters, activity notes, or restricted resources.
- An administrator approval action assigns requested ministries transactionally. Rejection grants nothing.

## Migration and production safety

The migrations only add nullable/text/defaulted fields and new tables. The resource publication flag defaults to `False`, so deployment cannot accidentally publish an existing private file. The ministry public flag defaults to `True` to make existing seeded ministry descriptions discoverable. No donation, member, participant, authentication, or ministry records are rewritten.

Before production deployment, take a Supabase database backup or point-in-time recovery checkpoint. Rollback is: redeploy the prior Git commit and leave the additive tables/columns in place. Do not reverse the migrations in production unless a database backup has been verified, because later inquiry data may exist.

## Deferred work

- Verified-email enforcement requires choosing and configuring a transactional email provider and a product decision on whether unverified members may sign in.
- Distributed form throttling should use a shared cache or edge/WAF rate limit; the current application throttle is a safe baseline but each Vercel instance has its own cache.
- Automated inquiry email notifications require an approved recipient policy and email configuration.
- Ministry-specific schedules, leaders, and program copy remain placeholders until church leadership confirms the content.
- Rich ministry media uploads should wait until the private Supabase Storage bucket and editorial approval policy are configured.
- A full leader-facing announcement editor and inquiry status editor can build on the included models after workflow ownership is confirmed; administrators can manage both safely in Django admin now.
- Account email verification and CAPTCHA are intentionally not simulated with an insecure home-grown system.

## Deployment checklist

1. Create a Supabase backup/recovery checkpoint.
2. Review this feature branch in a Vercel preview deployment.
3. Confirm `DATABASE_URL`, `SECRET_KEY`, allowed hosts, and email variables are set for Production.
4. Merge only after visual and permission review.
5. Production build runs `manage.py migrate --noinput`; monitor build and runtime logs.
6. In Django admin, approve public resources individually and review pending access requests with the provided actions.
7. Smoke-test public ministry pages, registration, login, password reset, a leader portal, and finance access.

