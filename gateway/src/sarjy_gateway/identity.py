from typing import TYPE_CHECKING, NewType
import uuid


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request, Response


COOKIE_NAME = "sarjy_user"

# Browsers cap a cookie's lifetime at 400 days.
COOKIE_MAX_AGE_SECONDS = 400 * 24 * 60 * 60

type NextHandler = Callable[[Request], Awaitable[Response]]

# A user's id, kept apart from session and turn ids by the type checker.
UserId = NewType("UserId", uuid.UUID)


def new_user_id() -> UserId:
    return UserId(uuid.uuid7())


# The cookie holds the user's id, nothing else. It is random enough to work like a session
# token (D-66): knowing it is what makes a browser that user.
def user_id_from(cookie: str | None) -> UserId | None:
    if cookie is None:
        return None
    try:
        return UserId(uuid.UUID(cookie))
    except ValueError:
        return None


# Gives a browser its identity on its first request, normally the page load, so the voice
# socket it opens later carries the cookie. A missing or garbled cookie means a new user.
def identity_cookie(*, secure: bool) -> Callable[[Request, NextHandler], Awaitable[Response]]:
    async def add_identity(request: Request, call_next: NextHandler) -> Response:
        response = await call_next(request)
        if user_id_from(request.cookies.get(COOKIE_NAME)) is None:
            response.set_cookie(
                COOKIE_NAME,
                str(new_user_id()),
                max_age=COOKIE_MAX_AGE_SECONDS,
                httponly=True,
                secure=secure,
                samesite="lax",
            )
        return response

    return add_identity
