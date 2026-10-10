from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def require(check):
    """Login required, then `check(user)` must be truthy or the user gets a 403."""

    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


finance_required = require(lambda u: u.can_manage_finance)
fund_totals_required = require(lambda u: u.can_view_fund_totals)
admin_required = require(lambda u: u.can_manage_users)
