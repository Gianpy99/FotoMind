from fastapi import APIRouter

from fotomind.api.auth import CurrentUser, UserDep

router = APIRouter(tags=["session"])


@router.get("/me", response_model=CurrentUser)
def me(user: UserDep) -> CurrentUser:
    """The portal user making the request (from Remote-User / Remote-Groups)."""
    return user
