from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytest


class TestEnvironment(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    sarjy_test_database_url: SecretStr | None = None
    # GitHub Actions sets CI=true.
    ci: bool = False


# The database tests need a real Postgres (O-20): `docker compose up -d --wait db` locally,
# a service container in CI. Locally they skip without one; in CI a skip would hide
# missing coverage, so it fails instead.
@pytest.fixture
def database_url() -> SecretStr:
    environment = TestEnvironment()
    if environment.sarjy_test_database_url is None:
        if environment.ci:
            pytest.fail("SARJY_TEST_DATABASE_URL must be set in CI")
        pytest.skip("set SARJY_TEST_DATABASE_URL to run the database tests")
    return environment.sarjy_test_database_url
