from app.rbac import (
    COLLECTION_ROLES,
    ROLES,
    can_use_sql,
    collections_for,
    refusal_message,
    role_filter,
)


def test_access_matrix_matches_spec():
    assert collections_for("doctor") == ["general", "clinical", "nursing"]
    assert collections_for("nurse") == ["general", "nursing"]
    assert collections_for("billing_executive") == ["general", "billing"]
    assert collections_for("technician") == ["general", "equipment"]
    assert collections_for("admin") == ["general", "clinical", "nursing", "billing", "equipment"]


def test_every_role_sees_general_and_admin_sees_all():
    assert set(COLLECTION_ROLES["general"]) == set(ROLES)
    assert all("admin" in roles for roles in COLLECTION_ROLES.values())


def test_sql_roles():
    assert {r for r in ROLES if can_use_sql(r)} == {"billing_executive", "admin"}


def test_role_filter_targets_access_roles():
    f = role_filter("nurse")
    cond = f.must[0]
    assert cond.key == "access_roles" and cond.match.value == "nurse"


def test_unknown_role_rejected():
    import pytest

    with pytest.raises(ValueError):
        role_filter("superuser")


def test_refusal_message_wording():
    msg = refusal_message("nurse", ["billing"])
    assert msg == (
        "As a nurse, you don't have access to billing documents. "
        "I can only answer questions from the general and nursing collections."
    )
    assert refusal_message("admin", ["x"]).startswith("As an administrator")
