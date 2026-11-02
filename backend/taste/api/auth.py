"""Accounts: sign in with Apple or Google, or carry on as a guest; sessions; deleting an account.

A session is a random token. The native app (X-Taste-Client: native) gets it in the response,
keeps it in the Keychain/Keystore and sends it as `Authorization: Bearer`; the web app only ever
gets it as an HttpOnly cookie, which page scripts can't read. Both reach `current_user`. Apple and Google prove who someone is with a signed ID token,
checked here against their published keys; we never see a password.

A guest is a real (anonymous) profile; signing in from a guest session keeps its ratings
(SqlProfileStore.sign_in).
"""

import hashlib
import hmac
import logging
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from taste.api import schemas
from taste.api.engine import Engine
from taste.settings import get_settings
from taste.storage import Account
from taste.storage.sql_store import SESSION_IDLE

COOKIE = "taste_session"
APPLE_KEYS = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"
GOOGLE_KEYS = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]

router = APIRouter()
log = logging.getLogger("taste.auth")


def engine(request: Request) -> Engine:
    return request.app.state.engine


E = Annotated[Engine, Depends(engine)]


# --- sessions ---------------------------------------------------------------------------------

def session_token(request: Request) -> str | None:
    """The bearer token (phones) or the session cookie (web)."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None
    return request.cookies.get(COOKIE)


def optional_user(request: Request, e: E) -> str | None:
    token = session_token(request)
    return e.store.session_user(token) if token else None


def current_user(user: Annotated[str | None, Depends(optional_user)]) -> str:
    if user is None:
        raise HTTPException(401, "Sign in, or continue without an account.")
    return user


Me = Annotated[str, Depends(current_user)]


def signed_in(request: Request, response: Response, e: Engine, account: Account) -> schemas.SignedIn:
    """A new session for the account: a cookie for the web, the token itself for the native app.
    The session the request came with (a guest's, now upgraded or merged) ends."""
    old = session_token(request)
    if old:
        e.store.end_session(old)
    token = e.store.new_session(account.id)
    response.set_cookie(COOKIE, token, max_age=int(SESSION_IDLE.total_seconds()), httponly=True,
                        secure=get_settings().cookie_secure, samesite="lax", path="/")
    native = request.headers.get("x-taste-client") == "native"
    return schemas.SignedIn(token=token if native else None, user=me_out(account))


def me_out(a: Account) -> schemas.Me:
    return schemas.Me(id=a.id, kind=a.kind, email=a.email, name=a.name)


# --- abuse limits -----------------------------------------------------------------------------

class RateLimit:
    """At most `per_minute` requests per client IP (in memory: one API process).

    Behind a proxy or load balancer the client IP comes from X-Forwarded-For, which uvicorn only
    believes from the proxies in FORWARDED_ALLOW_IPS (default 127.0.0.1): set it to the proxy's
    address or network, never "*", or clients could pick their own IP."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()
        self.swept = time.monotonic()

    def __call__(self, request: Request) -> None:
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        with self.lock:
            if now - self.swept > 60:  # forget addresses with nothing in the last minute
                self.hits = defaultdict(deque, {k: v for k, v in self.hits.items() if v and now - v[-1] <= 60})
                self.swept = now
            hits = self.hits[ip]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                raise HTTPException(429, "Too many sign-in attempts; try again in a minute.")
            hits.append(now)


def limited(request: Request) -> None:
    request.app.state.auth_limit(request)


# --- Apple and Google ID tokens -----------------------------------------------------------------

_keys: dict[str, jwt.PyJWKClient] = {}


def _verify(token: str, keys_url: str, issuers: list[str], audiences: list[str], provider: str) -> dict:
    if not audiences:
        raise HTTPException(503, f"{provider} sign-in isn't set up on this server.")
    client = _keys.setdefault(keys_url, jwt.PyJWKClient(keys_url, cache_keys=True))
    try:
        key = client.get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=["RS256"], audience=audiences, issuer=issuers,
                          options={"require": ["exp", "iat", "sub", "aud", "iss"]})
    except (jwt.PyJWTError, jwt.PyJWKClientError) as err:
        log.info("%s token rejected: %s", provider, err)  # details for us, not for the client
        raise HTTPException(401, f"{provider} couldn't confirm who you are; try signing in again.") from None


def verify_apple(token: str) -> tuple[str, str | None]:
    """(subject, email) from an Apple identity token meant for our app."""
    claims = _verify(token, APPLE_KEYS, [APPLE_ISSUER], get_settings().apple_client_ids, "Apple")
    return claims["sub"], claims.get("email")


def verify_google(token: str) -> tuple[str, str | None, str | None]:
    """(subject, email, name) from a Google ID token meant for one of our client ids."""
    claims = _verify(token, GOOGLE_KEYS, GOOGLE_ISSUERS, get_settings().google_client_ids, "Google")
    email = claims.get("email") if claims.get("email_verified") else None
    return claims["sub"], email, claims.get("name")


# --- routes -----------------------------------------------------------------------------------

Limited = Depends(limited)
Guest = Annotated[str | None, Depends(optional_user)]


@router.post("/auth/guest", dependencies=[Limited])
def guest(request: Request, response: Response, e: E) -> schemas.SignedIn:
    """Continue without an account: a new anonymous profile, kept by this device's session."""
    return signed_in(request, response, e, e.store.create_guest())


@router.post("/auth/apple", dependencies=[Limited])
def apple(body: schemas.AppleIn, request: Request, response: Response, e: E, current: Guest) -> schemas.SignedIn:
    subject, email = verify_apple(body.identity_token)
    return signed_in(request, response, e, e.store.sign_in("apple", subject, email, body.name, guest=current))


@router.post("/auth/google", dependencies=[Limited])
def google(body: schemas.GoogleIn, request: Request, response: Response, e: E, current: Guest) -> schemas.SignedIn:
    subject, email, name = verify_google(body.id_token)
    return signed_in(request, response, e, e.store.sign_in("google", subject, email, name, guest=current))


@router.post("/auth/dev", dependencies=[Limited], include_in_schema=False)
def dev(body: schemas.DevIn, request: Request, response: Response, e: E, current: Guest) -> schemas.SignedIn:
    """Local development only (TASTE_DEV_LOGIN): sign in as any email, no proof asked."""
    if not get_settings().dev_login:
        raise HTTPException(404, "Not found")
    email = body.email.strip().lower()
    return signed_in(request, response, e, e.store.sign_in("dev", email, email, None, guest=current))


@router.post("/auth/logout")
def logout(request: Request, response: Response, e: E, everywhere: bool = False) -> dict:
    """End this session (or, with everywhere, all of this user's sessions)."""
    token = session_token(request)
    if token:
        e.store.end_session(token, everywhere=everywhere)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: Me, e: E) -> schemas.Me:
    account = e.store.get_account(user)
    if account is None:
        raise HTTPException(401, "Sign in, or continue without an account.")
    return me_out(account)


@router.delete("/me")
def delete_me(user: Me, response: Response, e: E) -> dict:
    """Delete the account and everything in it: ratings, shelf scan, sign-ins, sessions."""
    e.store.delete_account(user)
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


# --- signed shelf-photo links -----------------------------------------------------------------

_secret: list[bytes] = []
IMAGE_TTL = 3600  # seconds a photo link stays valid


def secret() -> bytes:
    if not _secret:
        _secret.append((get_settings().secret or secrets.token_hex(32)).encode())
    return _secret[0]


def image_sig(user: str, scan_id: str, expires: int) -> str:
    return hmac.new(secret(), f"{user}:{scan_id}:{expires}".encode(), hashlib.sha256).hexdigest()


def image_url(user: str, scan_id: str) -> str:
    """A path to the scan's photo that works without a session (it goes in an <img>) for an hour."""
    expires = int(time.time()) + IMAGE_TTL
    return f"/shelf-images/{user}/{scan_id}?expires={expires}&sig={image_sig(user, scan_id, expires)}"


def check_image(user: str, scan_id: str, expires: int, sig: str) -> None:
    if expires < time.time() or not hmac.compare_digest(sig, image_sig(user, scan_id, expires)):
        raise HTTPException(403, "This photo link has expired.")
