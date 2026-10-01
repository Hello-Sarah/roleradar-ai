"""In-memory, single-instance abuse and model-budget controls for the public demo."""

from __future__ import annotations

from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network, ip_address, ip_network
from threading import Lock
from time import monotonic
from typing import Literal


class DemoUsageError(ValueError):
    """Base class for stable, content-free public demo usage failures."""


class DemoInputLimitError(DemoUsageError):
    """Raised when an input length exceeds the configured public-demo bound."""


class DemoRateLimitError(DemoUsageError):
    """Raised when a client has exhausted its rolling request allowance."""


class DemoModelBudgetError(DemoUsageError):
    """Raised when the daily model-call budget has already been reserved."""


class DemoReservationError(DemoUsageError):
    """Raised when one request tries to reserve more than one model call."""


IpAddress = IPv4Address | IPv6Address
IpNetwork = IPv4Network | IPv6Network


@dataclass(frozen=True)
class ClientIdentity:
    """A normalized client IP resolved only from explicitly trusted proxy hops."""

    address: str

    @classmethod
    def from_request(
        cls,
        *,
        remote_address: str,
        forwarded_for: str | None = None,
        trusted_proxy_cidrs: list[str] | tuple[str, ...] = (),
    ) -> ClientIdentity:
        remote = _parse_ip(remote_address)
        trusted_networks = tuple(ip_network(cidr, strict=False) for cidr in trusted_proxy_cidrs)
        if not _is_trusted(remote, trusted_networks) or not forwarded_for:
            return cls(address=str(remote))

        try:
            forwarded = [_parse_ip(value.strip()) for value in forwarded_for.split(",")]
        except ValueError:
            return cls(address=str(remote))
        if not forwarded or len(forwarded) > 20:
            return cls(address=str(remote))

        # Walk from the direct-proxy side toward the browser. A trusted proxy can only
        # vouch for the hop immediately before it, never for a header from an untrusted peer.
        for candidate in reversed(forwarded):
            if not _is_trusted(candidate, trusted_networks):
                return cls(address=str(candidate))
        return cls(address=str(forwarded[0]))


def _parse_ip(value: str) -> IpAddress:
    try:
        return ip_address(value)
    except ValueError as exc:
        raise ValueError("client address must be an IP address") from exc


def _is_trusted(address: IpAddress, networks: tuple[IpNetwork, ...]) -> bool:
    return any(address in network for network in networks)


def _utc_today() -> date:
    return datetime.now(UTC).date()


@dataclass
class ModelCallReservation:
    """One already-counted provider attempt; ``finish`` is deliberately idempotent."""

    _finished: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    def finish(self, outcome: Literal["success", "fallback"]) -> None:
        if outcome not in {"success", "fallback"}:
            raise ValueError("invalid model-call outcome")
        with self._lock:
            if self._finished:
                return
            self._finished = True


@dataclass
class UsagePermit:
    """A request accepted by the rate guard and eligible for one model reservation."""

    _guard: DemoUsageGuard
    _reserved: bool = False
    _lock: Lock = field(default_factory=Lock, repr=False)

    def reserve_model_call(self) -> ModelCallReservation:
        with self._lock:
            if self._reserved:
                raise DemoReservationError("model call has already been reserved for this request")
            self._guard._reserve_model_call()
            self._reserved = True
            return ModelCallReservation()


class DemoUsageGuard:
    """Lock-protected local controls; use a shared store before running multiple instances."""

    _WINDOW_SECONDS = 60.0

    def __init__(
        self,
        *,
        max_characters: int,
        requests_per_minute: int,
        daily_model_call_budget: int,
        monotonic_clock: Callable[[], float] = monotonic,
        utc_date_provider: Callable[[], date] = _utc_today,
        max_tracked_clients: int = 10_000,
    ) -> None:
        if max_characters < 1:
            raise ValueError("max_characters must be positive")
        if requests_per_minute < 1:
            raise ValueError("requests_per_minute must be positive")
        if daily_model_call_budget < 0:
            raise ValueError("daily_model_call_budget cannot be negative")
        if max_tracked_clients < 1:
            raise ValueError("max_tracked_clients must be positive")
        self.max_characters = max_characters
        self.requests_per_minute = requests_per_minute
        self.daily_model_call_budget = daily_model_call_budget
        self._monotonic_clock = monotonic_clock
        self._utc_date_provider = utc_date_provider
        self._max_tracked_clients = max_tracked_clients
        self._lock = Lock()
        self._requests_by_client: OrderedDict[str, deque[float]] = OrderedDict()
        self._budget_day: date | None = None
        self._reserved_model_calls = 0

    def check_request(self, client: ClientIdentity, input_length: int) -> UsagePermit:
        if input_length < 0:
            raise DemoInputLimitError("input length must not be negative")
        if input_length > self.max_characters:
            raise DemoInputLimitError("input exceeds the configured demo limit")
        now = self._monotonic_clock()
        with self._lock:
            self._discard_expired_clients(now)
            requests = self._requests_by_client.get(client.address)
            if requests is None:
                self._evict_for_new_client()
                requests = deque()
                self._requests_by_client[client.address] = requests
            else:
                self._requests_by_client.move_to_end(client.address)
            if len(requests) >= self.requests_per_minute:
                raise DemoRateLimitError("demo request rate limit exceeded")
            requests.append(now)
        return UsagePermit(_guard=self)

    def _reserve_model_call(self) -> None:
        with self._lock:
            today = self._utc_date_provider()
            if self._budget_day != today:
                self._budget_day = today
                self._reserved_model_calls = 0
            if self._reserved_model_calls >= self.daily_model_call_budget:
                raise DemoModelBudgetError("daily model budget exhausted")
            self._reserved_model_calls += 1

    def _discard_expired_clients(self, now: float) -> None:
        cutoff = now - self._WINDOW_SECONDS
        for address, requests in list(self._requests_by_client.items()):
            while requests and requests[0] <= cutoff:
                requests.popleft()
            if not requests:
                del self._requests_by_client[address]

    def _evict_for_new_client(self) -> None:
        while len(self._requests_by_client) >= self._max_tracked_clients:
            self._requests_by_client.popitem(last=False)
