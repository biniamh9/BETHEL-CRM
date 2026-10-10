# Putting the site online (Supabase + Vercel)

**Supabase** stores the data (members, gifts, events...). **Vercel** runs the website.
Do the steps in order. Each one says exactly where to click.

You need **two values**. Write them down as you go:

| Value | Where it comes from | Example |
|---|---|---|
| **A. Database connection string** | Supabase (step 1) | `postgresql://postgres.abcdefgh:MyPass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres` |
| **B. Secret key** | You make it up (step 2) | `k3J9xQ2mV7pL0wR5tY8uZ1aB4cD6eF...` (50+ random characters) |

---

## Step 1 — Get the database connection string from Supabase (value A)

1. Go to <https://supabase.com/dashboard> and open your project.
2. Click the **Connect** button at the top of the page.
3. Under **Connection string**, keep **Type: URI**.
4. Scroll to **Transaction pooler** (port **6543**) and copy that string.
   ❗ Not "Direct connection" and not the "Project URL" (`https://....supabase.co`). Those don't work.
5. Paste it into a note. Replace `[YOUR-PASSWORD]` **including the square brackets** with your database password.

   Before: `postgresql://postgres.abcdefgh:[YOUR-PASSWORD]@aws-0-us-east-1.pooler.supabase.com:6543/postgres`
   After:  `postgresql://postgres.abcdefgh:MyPass123@aws-0-us-east-1.pooler.supabase.com:6543/postgres`

**Forgot the database password, or it has symbols like `# / ? % @`?**
Supabase → **Project Settings** (gear icon) → **Database** → **Reset database password**. Choose one with only letters and numbers, then redo step 1.

Check value A: it starts with `postgresql://`, contains `pooler.supabase.com:6543`, and has no `[` `]`.

## Step 2 — Make a secret key (value B)

Run this on your computer and copy what it prints:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

(Or use any password generator to make 50+ random characters.) Keep it private and don't change it later: changing it logs everyone out.

## Step 3 — Put both values into Vercel

1. Go to <https://vercel.com>, open the **BETHEL-CRM** project.
2. Click **Settings** → **Environment Variables**.
3. **First delete any old `DATABASE_URL`** that's already there (the earlier deploy failed because it held the `https://` Project URL).
4. Add these, one at a time (**Key**, **Value**, leave all environments ticked, click **Save**):

| Key | Value |
|---|---|
| `DATABASE_URL` | value A |
| `SECRET_KEY` | value B |
| `INITIAL_ADMIN_PASSWORD` | Pastor Abraham's first login password (at least 8 characters) |

Nothing else is needed to go live.

## Step 4 — Check the framework setting (once)

Vercel → **Settings** → **Build and Deployment** → **Framework Preset** should be **Django**. If it says something else, change it and **Save**.

## Step 5 — Deploy

Push your code from your computer:

```bash
git push origin main
```

Vercel starts building automatically. (If the code was already pushed: Vercel → **Deployments** → the top one → **⋯** → **Redeploy**.)

## Step 6 — Read the build log

Vercel → **Deployments** → click the newest one → **Build Logs**. Near the top you'll see:

```
Setup checklist (Vercel -> Settings -> Environment Variables):
  [x] DATABASE_URL             Supabase -> Connect -> Transaction pooler URI
  [x] SECRET_KEY               any long random text
  [x] INITIAL_ADMIN_PASSWORD   optional: Pastor Abraham's first password
```

followed by `Connected to the database`, then `migrate` (creates the tables) and `seed_church` (adds the ministries and leaders' logins).

**If it fails**, look for the box marked `SETUP PROBLEM`. It says what's wrong in plain words:

| The box says | Do this |
|---|---|
| Not set yet: DATABASE_URL / SECRET_KEY | Step 3, then Redeploy |
| starts with https:// | You pasted the Project URL. Redo step 1, replace `DATABASE_URL` |
| still contains [YOUR-PASSWORD] | Put your real password in (step 1, item 5) |
| can't be read ... letters and numbers | Reset the password to letters/numbers only (step 1), replace `DATABASE_URL` |
| rejected the database password | Wrong password: reset it (step 1), replace `DATABASE_URL` |
| can't find this project | Copy the whole Transaction pooler string again (step 1) |
| Can't reach the database | You used the Direct connection, or the Supabase project is paused (Supabase dashboard → **Restore project**) |

After changing a variable in Vercel, always **Redeploy**: variables are only read when a deploy starts.

## Step 7 — First login

1. Open your site (the address is on the Vercel project page, e.g. `https://bethel-crm.vercel.app`).
2. Go to `/accounts/login/`, user name **abraham**, password = your `INITIAL_ADMIN_PASSWORD`.
3. **My profile → Change password** and pick a new one.
4. Back in Vercel → Settings → Environment Variables, **delete `INITIAL_ADMIN_PASSWORD`** (it's only used once anyway).
5. Create everyone else's logins on **Team & logins**.

You're live. 🎉

---

## Later, when you're ready (all optional)

Add each variable in Vercel → Settings → Environment Variables, then Redeploy.

**Online giving (Stripe)**
1. Create a Stripe account for the church (church EIN and bank account). Ask Stripe for nonprofit pricing with your 501(c)(3) letter.
2. Stripe → Developers → API keys: add `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY`.
3. Stripe → Developers → Webhooks → Add endpoint `https://YOUR-SITE/stripe/webhook/` with events
   `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`.
   Add its signing secret as `STRIPE_WEBHOOK_SECRET`.

Until then, the giving page shows Zelle / check / cash instructions and the pledge form.

**Email (receipts and password resets)** — from Gmail (app password), SendGrid, Resend, etc.:
`EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.

**File uploads on the Resources page (Supabase Storage)** — until this is set, Resources accepts links only (Google Drive, YouTube...):
1. Supabase → **Storage** → **New bucket**, name `resources`, leave **Public** off.
2. Supabase → **Storage** → **S3 Configuration** (Settings): copy the **Endpoint** and **Region**, then **New access key**.
3. Add `SUPABASE_S3_BUCKET=resources`, `SUPABASE_S3_ENDPOINT`, `SUPABASE_S3_REGION`, `SUPABASE_S3_ACCESS_KEY`, `SUPABASE_S3_SECRET_KEY`.

Vercel limits each upload to about 4 MB; bigger files should go in as links.

**Your own domain** (e.g. `bethelatlanta.org`) — Vercel → Settings → Domains → Add. Then add
`ALLOWED_HOSTS=bethelatlanta.org,www.bethelatlanta.org` and `CSRF_TRUSTED_ORIGINS=https://bethelatlanta.org,https://www.bethelatlanta.org`.

**Church details** (address, phone, EIN, Zelle) are already built in. To change one, set the matching `CHURCH_*` variable (see `.env.example`).

## Running commands against the live database

To run something like `python manage.py changepassword abraham` against Supabase from your computer, temporarily put value A as `DATABASE_URL` in your local `.env`. **Remove it afterwards** so local testing doesn't change live data.

## Notes

- Preview deployments (other branches) never change the database; only `main` (production) does.
- Supabase's free plan pauses a project after a week without use. If the site suddenly can't reach the database, open the Supabase dashboard and click **Restore project**.
- Errors after the site is live show up in Vercel → your project → **Logs**.
