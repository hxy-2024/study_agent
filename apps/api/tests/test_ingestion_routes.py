from app.main import app


def test_rag_routes_are_registered() -> None:
    paths = {route.path for route in app.routes}

    assert "/api/v1/ingestion/sources/{source_id}/run" in paths
    assert "/api/v1/rag/retrieve" in paths
