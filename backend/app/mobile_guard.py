"""Server-side half of the no-phones rule.

The client gate in ``frontend/src/components/MobileGate.tsx`` stops a phone from
*using* the site; this stops a phone from reaching the API at all, so bypassing
the frontend JS buys nothing. The two use the same definition of "phone": real
phone user-agents only, so tablets (iPad, Android tablets whose UA has no
"Mobile" token) and desktops pass.
"""

from __future__ import annotations

import re

_PHONE_UA = re.compile(
    r"iPhone|iPod|Android.*Mobile|Windows Phone|BlackBerry|Opera Mini|IEMobile",
    re.IGNORECASE,
)


def is_phone(user_agent: str | None) -> bool:
    """True for a phone browser's user-agent, False for tablets and desktops."""
    return bool(user_agent) and bool(_PHONE_UA.search(user_agent))
