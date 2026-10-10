from django.conf import settings
from django.http import HttpResponse

MESSAGE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Database not connected</title>
<body style="font:16px/1.6 system-ui,sans-serif;max-width:640px;margin:60px auto;padding:0 16px;color:#1f2433">
<h1 style="color:#8e2a2c">The site is deployed, but its database isn't connected yet</h1>
<p>Vercel can't store data on its own disk, so this site needs your Supabase database.</p>
<ol>
<li>In Supabase, open your project, click <b>Connect</b>, choose <b>Transaction pooler</b> and copy the URI
(it ends in <code>:6543/postgres</code>). Put your database password in place of <code>[YOUR-PASSWORD]</code>.</li>
<li>In Vercel, open the project &rarr; <b>Settings &rarr; Environment Variables</b> and add
<code>DATABASE_URL</code> with that URI. Also add <code>SECRET_KEY</code> (any long random text) and
<code>INITIAL_ADMIN_PASSWORD</code> (Pastor Abraham's first password).</li>
<li>Go to <b>Deployments</b>, open the latest one and click <b>Redeploy</b>. The database tables are created during the build.</li>
</ol>
<p>Then log in at <code>/accounts/login/</code> as <b>abraham</b>.</p>
</body>"""


class DatabaseConfigCheck:
    """On Vercel without DATABASE_URL, show setup steps instead of a confusing server error."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.missing = getattr(settings, "ON_VERCEL", False) and settings.DATABASES["default"]["ENGINE"].endswith("sqlite3")

    def __call__(self, request):
        if self.missing and not request.path.startswith(settings.STATIC_URL.rstrip("/") or "/static"):
            return HttpResponse(MESSAGE, status=503)
        return self.get_response(request)
