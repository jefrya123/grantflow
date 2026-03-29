from sqlalchemy import select

from grantflow.models import SavedSearch


def test_create_saved_search(db_session):
    ss = SavedSearch(
        api_key_id=1,
        name="My Grants",
        alert_email="user@example.com",
    )
    db_session.add(ss)
    db_session.flush()

    assert ss.id is not None
    assert ss.name == "My Grants"
    assert ss.api_key_id == 1
    assert ss.alert_email == "user@example.com"


def test_saved_search_default_is_active(db_session):
    ss = SavedSearch(
        api_key_id=2,
        name="Test Search",
        alert_email="test@example.com",
    )
    db_session.add(ss)
    db_session.flush()

    assert ss.is_active is True


def test_saved_search_created_at_auto_set(db_session):
    ss = SavedSearch(
        api_key_id=3,
        name="Auto Date",
        alert_email="auto@example.com",
    )
    db_session.add(ss)
    db_session.flush()

    assert ss.created_at is not None
    assert "T" in ss.created_at  # ISO 8601 format


def test_query_by_api_key_id(db_session):
    for i in range(3):
        db_session.add(
            SavedSearch(
                api_key_id=10,
                name=f"Search {i}",
                alert_email=f"user{i}@example.com",
            )
        )
    db_session.add(
        SavedSearch(
            api_key_id=99,
            name="Other user",
            alert_email="other@example.com",
        )
    )
    db_session.flush()

    results = (
        db_session.execute(select(SavedSearch).where(SavedSearch.api_key_id == 10))
        .scalars()
        .all()
    )

    assert len(results) == 3
    assert all(r.api_key_id == 10 for r in results)


def test_saved_search_optional_filters(db_session):
    ss = SavedSearch(
        api_key_id=5,
        name="Filtered Search",
        query="climate health",
        agency_code="NIH",
        category="research",
        eligible_applicants="nonprofits",
        min_award=10000.0,
        max_award=500000.0,
        alert_email="filtered@example.com",
    )
    db_session.add(ss)
    db_session.flush()

    fetched = db_session.get(SavedSearch, ss.id)
    assert fetched.query == "climate health"
    assert fetched.agency_code == "NIH"
    assert fetched.min_award == 10000.0
    assert fetched.max_award == 500000.0
