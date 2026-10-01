from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest


class Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class UtcDate:
    def __init__(self, value: date) -> None:
        self.value = value

    def __call__(self) -> date:
        return self.value


def _guard(**overrides: object):
    from app.demo.usage import DemoUsageGuard

    clock = overrides.pop("clock", Clock())
    utc_date = overrides.pop("utc_date", UtcDate(date(2026, 10, 1)))
    configuration = {
        "max_characters": 24,
        "requests_per_minute": 2,
        "daily_model_call_budget": 2,
        "monotonic_clock": clock,
        "utc_date_provider": utc_date,
    }
    configuration.update(overrides)
    return DemoUsageGuard(
        **configuration,
    )


def _client(address: str = "203.0.113.9"):
    from app.demo.usage import ClientIdentity

    return ClientIdentity.from_request(remote_address=address)


def test_settings_keep_the_public_demo_disabled_until_explicitly_enabled() -> None:
    from app.config import Settings

    settings = Settings()

    assert settings.public_demo_enabled is False
    assert settings.demo_max_characters > 0
    assert settings.demo_requests_per_minute > 0
    assert settings.demo_daily_model_call_budget >= 0
    assert settings.demo_provider_timeout_seconds > 0
    assert settings.portfolio_origins
    assert settings.trusted_proxy_cidrs == []


def test_guard_rejects_input_larger_than_the_configured_character_limit() -> None:
    from app.demo.usage import DemoInputLimitError

    guard = _guard(max_characters=3)

    with pytest.raises(DemoInputLimitError, match="input exceeds"):
        guard.check_request(_client(), input_length=4)


def test_guard_limits_each_client_in_a_rolling_minute_window() -> None:
    from app.demo.usage import DemoRateLimitError

    clock = Clock()
    guard = _guard(clock=clock, requests_per_minute=2)
    client = _client()

    guard.check_request(client, input_length=1)
    clock.advance(20)
    guard.check_request(client, input_length=1)
    with pytest.raises(DemoRateLimitError, match="rate limit"):
        guard.check_request(client, input_length=1)

    clock.advance(40)
    guard.check_request(client, input_length=1)


def test_guard_keeps_rate_limits_separate_for_distinct_clients() -> None:
    from app.demo.usage import DemoRateLimitError

    guard = _guard(requests_per_minute=1)

    guard.check_request(_client("203.0.113.9"), input_length=1)
    guard.check_request(_client("203.0.113.10"), input_length=1)
    with pytest.raises(DemoRateLimitError):
        guard.check_request(_client("203.0.113.9"), input_length=1)


def test_reservation_enforces_daily_budget_and_resets_on_utc_day_rollover() -> None:
    from app.demo.usage import DemoModelBudgetError

    utc_date = UtcDate(date(2026, 10, 1))
    guard = _guard(utc_date=utc_date, daily_model_call_budget=1)

    first = guard.check_request(_client(), input_length=1).reserve_model_call()
    first.finish("success")
    with pytest.raises(DemoModelBudgetError, match="daily model budget"):
        guard.check_request(_client("203.0.113.10"), input_length=1).reserve_model_call()

    utc_date.value = date(2026, 10, 2)
    guard.check_request(_client("203.0.113.10"), input_length=1).reserve_model_call()


def test_reservation_is_consumed_once_when_the_provider_falls_back() -> None:
    from app.demo.usage import DemoModelBudgetError

    guard = _guard(daily_model_call_budget=1)
    reservation = guard.check_request(_client(), input_length=1).reserve_model_call()

    try:
        raise TimeoutError("provider failed after the reservation")
    except TimeoutError:
        reservation.finish("fallback")
    reservation.finish("fallback")

    with pytest.raises(DemoModelBudgetError):
        guard.check_request(_client("203.0.113.10"), input_length=1).reserve_model_call()


def test_concurrent_reservations_cannot_overspend_the_daily_budget() -> None:
    from app.demo.usage import DemoModelBudgetError

    guard = _guard(daily_model_call_budget=1)
    permits = [
        guard.check_request(_client(f"203.0.113.{index}"), input_length=1) for index in (9, 10)
    ]
    barrier = Barrier(2)

    def reserve(permit: object) -> str:
        barrier.wait()
        try:
            reservation = permit.reserve_model_call()  # type: ignore[attr-defined]
        except DemoModelBudgetError:
            return "budget"
        reservation.finish("success")
        return "reserved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(reserve, permits))

    assert sorted(outcomes) == ["budget", "reserved"]


def test_untrusted_peers_cannot_select_a_client_address_through_x_forwarded_for() -> None:
    from app.demo.usage import ClientIdentity

    client = ClientIdentity.from_request(
        remote_address="203.0.113.9",
        forwarded_for="198.51.100.7",
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )

    assert client.address == "203.0.113.9"


def test_trusted_proxy_extracts_the_original_client_address_from_x_forwarded_for() -> None:
    from app.demo.usage import ClientIdentity

    client = ClientIdentity.from_request(
        remote_address="10.1.2.3",
        forwarded_for="198.51.100.7, 10.2.3.4",
        trusted_proxy_cidrs=["10.0.0.0/8"],
    )

    assert client.address == "198.51.100.7"


def test_guard_retains_no_submitted_text_in_its_errors_or_state() -> None:
    from app.demo.usage import DemoInputLimitError

    guard = _guard(max_characters=1)
    secret = "JD-SECRET-SENTINEL"

    with pytest.raises(DemoInputLimitError) as exc_info:
        guard.check_request(_client(), input_length=len(secret))

    assert secret not in str(exc_info.value)
    assert secret not in repr(guard)
    assert secret not in repr(vars(guard))


def test_guard_evicts_old_client_keys_when_its_retention_capacity_is_full() -> None:
    guard = _guard(requests_per_minute=1, max_tracked_clients=2)

    guard.check_request(_client("203.0.113.9"), input_length=1)
    guard.check_request(_client("203.0.113.10"), input_length=1)
    guard.check_request(_client("203.0.113.11"), input_length=1)

    assert len(guard._requests_by_client) == 2
    guard.check_request(_client("203.0.113.9"), input_length=1)
