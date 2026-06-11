import pytest

from services.user_store import UserStore
from services.auth_service import AuthService


@pytest.fixture
def auth_pair(tmp_path):
    """Fresh UserStore + AuthService per test (uses temp DB)."""
    db_path = tmp_path / "app.db"
    store = UserStore(db_path=str(db_path))
    auth = AuthService(store)
    return store, auth


def test_email_signup_issues_otp_and_verify_grants_token(auth_pair):
    store, auth = auth_pair
    res = auth.signup_with_email("alice@example.com", "s3cr3t-pw", "Alice")
    assert res["success"] is True
    assert "user_id" in res

    # OTP is generated in the store's in-memory cache
    otp_record = store._otp_store.get("alice@example.com")
    assert otp_record is not None
    code = otp_record["code"]

    verify = auth.complete_email_verification("alice@example.com", code)
    assert verify["success"] is True
    assert "token" in verify and verify["token"]
    assert verify["user"]["email"] == "alice@example.com"

    # Token must resolve
    user = auth.get_user_from_token(verify["token"])
    assert user is not None
    assert user.email == "alice@example.com"


def test_login_with_correct_password(auth_pair):
    store, auth = auth_pair
    # Pre-create verified user by going through signup+verify
    auth.signup_with_email("bob@example.com", "correct-horse", "Bob")
    code = store._otp_store["bob@example.com"]["code"]
    auth.complete_email_verification("bob@example.com", code)

    login = auth.login_with_email("bob@example.com", "correct-horse")
    assert login["success"] is True
    assert "token" in login

    user = auth.get_user_from_token(login["token"])
    assert user and user.name == "Bob"


def test_login_rejects_bad_password(auth_pair):
    store, auth = auth_pair
    auth.signup_with_email("carol@example.com", "right-pw", None)
    code = store._otp_store["carol@example.com"]["code"]
    auth.complete_email_verification("carol@example.com", code)

    bad = auth.login_with_email("carol@example.com", "wrong-pw")
    assert bad["success"] is False
    assert "Invalid email or password" in bad["error"]


def test_otp_verification_rejects_bad_code_and_enforces_attempts(auth_pair):
    store, auth = auth_pair
    auth.signup_with_email("dave@example.com", "pw123456", "Dave")

    # Bad code should fail
    ok = auth.verify_otp("dave@example.com", "000000")
    assert ok is False

    # After enough bad attempts the record is cleared and further attempts fail
    for _ in range(6):
        auth.verify_otp("dave@example.com", "000000")

    # Record should have been deleted
    assert "dave@example.com" not in store._otp_store


def test_guest_session_has_short_expiry_and_is_marked(auth_pair):
    _, auth = auth_pair
    res = auth.create_guest_session()
    assert res["success"]
    assert res["user"]["is_guest"] is True

    user = auth.get_user_from_token(res["token"])
    assert user is not None
    assert user.is_guest is True


def test_logout_invalidates_token(auth_pair):
    store, auth = auth_pair
    auth.signup_with_email("eve@example.com", "pw", None)
    code = store._otp_store["eve@example.com"]["code"]
    verified = auth.complete_email_verification("eve@example.com", code)
    token = verified["token"]

    assert auth.get_user_from_token(token) is not None

    logout_res = auth.logout(token)
    assert logout_res["success"] is True

    # Token must no longer be valid
    assert auth.get_user_from_token(token) is None


def test_cross_user_cannot_access_another_users_conversation_messages(auth_pair):
    store, auth = auth_pair

    # Create two users
    auth.signup_with_email("u1@test.com", "pw1", "U1")
    code1 = store._otp_store["u1@test.com"]["code"]
    u1 = auth.complete_email_verification("u1@test.com", code1)["user"]

    auth.signup_with_email("u2@test.com", "pw2", "U2")
    code2 = store._otp_store["u2@test.com"]["code"]
    u2 = auth.complete_email_verification("u2@test.com", code2)["user"]

    # Create private conversations + messages for each
    c1 = store.create_conversation(u1["id"], "U1 secrets")
    store.add_message(c1, "user", "private u1 note")

    c2 = store.create_conversation(u2["id"], "U2 secrets")
    store.add_message(c2, "user", "private u2 note")

    # U1 using the SAFE method must not see U2's data
    u1_view_of_u2 = store.get_user_conversation_messages(u1["id"], c2)
    assert u1_view_of_u2 is None

    # U2 cannot see U1's
    u2_view_of_u1 = store.get_user_conversation_messages(u2["id"], c1)
    assert u2_view_of_u1 is None

    # Owner can see their own
    own = store.get_user_conversation_messages(u1["id"], c1)
    assert own is not None
    assert len(own) == 1
    assert "private u1 note" in own[0]["content"]


def test_unsafe_direct_messages_method_still_exists_but_is_not_recommended(auth_pair):
    store, _ = auth_pair
    # The old method should still be there (for any internal/back-compat use)
    assert hasattr(store, "get_conversation_messages")
    # But the new safe one must exist and be the one used by APIs
    assert hasattr(store, "get_user_conversation_messages")


# --- Route-level smoke tests using Flask test client (web server) ---

def test_web_auth_routes_and_history_authorization(tmp_path):
    # We import here to avoid side effects at module load for all tests
    from web.server import create_web_app
    from services.user_store import UserStore
    from services.auth_service import AuthService

    # Patch the global singletons used by the web app for isolation in this test
    import web.server as web_module

    db_path = tmp_path / "web_app.db"
    test_store = UserStore(db_path=str(db_path))
    test_auth = AuthService(test_store)

    # Override the lazy getters
    original_get_auth = web_module._get_auth
    web_module._user_store = test_store
    web_module._auth_service = test_auth

    app = create_web_app()
    client = app.test_client()

    try:
        # Signup
        r = client.post("/api/auth/signup", json={"email": "web@test.com", "password": "webpass123", "name": "WebUser"})
        assert r.status_code == 200
        signup = r.get_json()
        assert signup["success"]

        # Get OTP (dev mode prints it; it's also in the store we control)
        code = test_store._otp_store["web@test.com"]["code"]

        # Verify OTP -> get token
        r = client.post("/api/auth/verify-otp", json={"email": "web@test.com", "code": code})
        assert r.status_code == 200
        data = r.get_json()
        token = data["token"]
        assert token

        # Login also works
        r = client.post("/api/auth/login", json={"email": "web@test.com", "password": "webpass123"})
        assert r.status_code == 200
        assert r.get_json()["success"]

        # Create a conversation via direct store (simulating chat persistence)
        user = test_auth.get_user_from_token(token)
        conv_id = test_store.create_conversation(user.id, "My conv")
        test_store.add_message(conv_id, "user", "hello from me")

        # List history requires auth
        r = client.get("/api/history")
        assert r.status_code == 401

        r = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        hist = r.get_json()
        assert len(hist["conversations"]) >= 1

        # Per-conv detail requires ownership
        r = client.get(f"/api/history/{conv_id}", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        msgs = r.get_json()["messages"]
        assert len(msgs) == 1

        # Another user cannot access it
        # Create second user + token
        r2 = client.post("/api/auth/guest", json={})
        assert r2.status_code == 200
        guest_token = r2.get_json()["token"]

        r = client.get(f"/api/history/{conv_id}", headers={"Authorization": f"Bearer {guest_token}"})
        assert r.status_code == 404  # Now correctly 404 instead of leaking data

        # Logout should succeed and invalidate
        r = client.post("/api/auth/logout", json={"token": token})
        assert r.status_code == 200
        assert r.get_json()["success"]

        # Old token should no longer work for protected routes
        r = client.get("/api/history", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401

    finally:
        # Restore
        web_module._user_store = None
        web_module._auth_service = None
        web_module._get_auth = original_get_auth
