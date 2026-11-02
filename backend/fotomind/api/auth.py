"""Portal authentication (FamilyPortal ``portal`` mode).

Caddy performs the login and forwards ``Remote-User`` / ``Remote-Groups``. These headers are
trusted only because the container port is bound to 127.0.0.1 on the Pi, so only Caddy can reach
the API. In production a missing ``Remote-User`` is a 401; there is never a fallback user.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import BaseModel

from fotomind.config import Settings


class CurrentUser(BaseModel):
    username: str
    groups: list[str]


def get_current_user(request: Request) -> CurrentUser:
    settings: Settings = request.app.state.settings
    username = request.headers.get("Remote-User")
    if not username and not settings.is_production:
        username = settings.dev_user
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    groups = [g.strip() for g in request.headers.get("Remote-Groups", "").split(",") if g.strip()]
    return CurrentUser(username=username, groups=groups)


UserDep = Annotated[CurrentUser, Depends(get_current_user)]
