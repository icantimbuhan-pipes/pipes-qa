import pytest


@pytest.fixture(scope="session")
def env():
    """Load and return the .env config for integration tests."""
    from dotenv import dotenv_values
    return dotenv_values(".env")
