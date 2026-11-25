import re
from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func, select
from werkzeug.security import check_password_hash, generate_password_hash

from .config import TOKEN_MAX_AGE_SECONDS
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


def json_error(message, status):
    return jsonify({"error": message}), status


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt="docverify-auth")


def issue_token(user):
    return _serializer().dumps({"uid": user.id})


def _user_from_token(token):
    try:
        data = _serializer().loads(token, max_age=TOKEN_MAX_AGE_SECONDS)
    except SignatureExpired:
        return None, "Your session has expired. Sign in again."
    except BadSignature:
        return None, "Invalid session. Sign in again."
    with current_app.config["DB"]() as session:
        user = session.get(User, data.get("uid"))
    if user is None:
        return None, "Account not found. Sign in again."
    return user, None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return json_error("Sign in to continue.", 401)
        user, error = _user_from_token(header.removeprefix("Bearer ").strip())
        if user is None:
            return json_error(error, 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @login_required
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user.role != "admin":
            return json_error("Only administrators can do this.", 403)
        return view(*args, **kwargs)

    return wrapped


def _auth_response(user, status=200):
    return jsonify({"token": issue_token(user), "user": user.to_dict()}), status


@bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not name:
        return json_error("Name is required.", 400)
    if not EMAIL_PATTERN.match(email):
        return json_error("Enter a valid email address.", 400)
    if len(password) < MIN_PASSWORD_LENGTH:
        return json_error(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.", 400)

    with current_app.config["DB"]() as session:
        if session.scalar(select(User).where(User.email == email)):
            return json_error("An account with this email already exists.", 409)
        # The first account becomes the administrator who manages references and records.
        is_first = session.scalar(select(func.count(User.id))) == 0
        user = User(
            name=name,
            email=email,
            password_hash=generate_password_hash(password),
            role="admin" if is_first else "user",
        )
        session.add(user)
        session.commit()
        return _auth_response(user, 201)


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))
    if not email or not password:
        return json_error("Email and password are required.", 400)

    with current_app.config["DB"]() as session:
        user = session.scalar(select(User).where(User.email == email))
    if user is None or not check_password_hash(user.password_hash, password):
        return json_error("Incorrect email or password.", 401)
    return _auth_response(user)


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.user.to_dict()})
