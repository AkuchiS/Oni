from core.engine import create_engine
def test_run():
    assert create_engine({}).run_pipeline("x") == 2
