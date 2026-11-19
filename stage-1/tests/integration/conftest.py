def pytest_addoption(parser):
    parser.addoption("--integration", action="store_true", help="run docker-backed integration tests")
