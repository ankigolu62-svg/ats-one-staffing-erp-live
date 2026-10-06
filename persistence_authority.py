"""Fail-closed, versioned SQLite snapshot persistence primitives.

The application historically uploaded one mutable SQLite object after every
commit.  That protocol cannot distinguish concurrent writers and cannot prove
that restored bytes are a valid database.  This module deliberately requires
an object store with atomic create and compare-and-swap operations.  A backend
that cannot provide those operations must not be used as a write authority.

The public surface is intentionally independent of any cloud vendor:

* :class:`WriterLease` provides one-writer fencing.
* :class:`SnapshotAuthority` publishes immutable, checksummed generations and
  restores only validated SQLite files.
* :class:`DurableSnapshotCoordinator` coalesces concurrent durability requests
  while making every caller wait for (or fail on) the generation covering its
  commit.

Only Python's standard library is used.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional, Protocol


class PersistenceError(RuntimeError):
    """Base error for persistence authority failures."""


class ObjectConflict(PersistenceError):
    """An object-store conditional operation lost a race."""


class LeaseConflict(PersistenceError):
    """Another live writer owns the persistence lease."""


class LeaseLost(PersistenceError):
    """The caller no longer owns a live writer lease."""


class SnapshotValidationError(PersistenceError):
    """A snapshot failed checksum, SQLite, or schema validation."""


class DurabilityError(PersistenceError):
    """A committed local change could not be proven remotely durable."""


class DurabilityTimeout(DurabilityError):
    """The bounded wait for remote durability expired."""


@dataclass(frozen=True)
class StoredObject:
    data: bytes
    version: str


class AtomicObjectStore(Protocol):
    """Minimal store contract required for safe multi-writer operation.

    ``create`` must fail with :class:`ObjectConflict` if *key* exists.
    ``replace`` and ``delete`` must compare the supplied opaque version
    atomically with the current object version.
    """

    def read(self, key: str) -> Optional[StoredObject]: ...

    def create(self, key: str, data: bytes) -> StoredObject: ...

    def replace(self, key: str, data: bytes, expected_version: str) -> StoredObject: ...

    def delete(self, key: str, expected_version: str) -> None: ...

    def list(self, prefix: str) -> Iterable[str]: ...



class SupabasePostgrestAtomicStore:
    """CAS object store backed by a dedicated Supabase/PostgREST table.

    Required table schema is shipped in ``supabase/ats_one_atomic_objects.sql``.
    The service-role key is server-side only.  Every mutation predicates on the
    current integer ``version`` so create/replace/delete have compare-and-swap
    semantics in Postgres rather than last-write-wins object replacement.
    """

    def __init__(
        self,
        url: str,
        service_role_key: str,
        *,
        table: str = "ats_one_atomic_objects",
        timeout: float = 30.0,
    ) -> None:
        self.url = str(url or "").rstrip("/")
        self.key = str(service_role_key or "")
        self.table = str(table or "").strip()
        self.timeout = float(timeout)
        if not self.url or not self.key:
            raise ValueError("Supabase URL and service-role key are required")
        if not self.table.replace("_", "").isalnum():
            raise ValueError("invalid PostgREST table name")

    @property
    def endpoint(self) -> str:
        return f"{self.url}/rest/v1/{self.table}"

    def _request(self, method: str, query: dict | None = None, body: dict | None = None):
        url = self.endpoint
        if query:
            url += "?" + urllib.parse.urlencode(query, safe=".*,:()")
        raw = None if body is None else json.dumps(body, separators=(",", ":")).encode("utf-8")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }
        if raw is not None:
            headers["Content-Type"] = "application/json"
        if method in {"POST", "PATCH", "DELETE"}:
            headers["Prefer"] = "return=representation"
        req = urllib.request.Request(url, data=raw, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1000]
            if exc.code in (409, 412):
                raise ObjectConflict(f"atomic object conflict: HTTP {exc.code}") from exc
            if exc.code in (404, 400) and "does not exist" in detail.lower():
                raise PersistenceError(
                    f"required Supabase persistence table {self.table!r} is not installed"
                ) from exc
            raise PersistenceError(f"Supabase persistence HTTP {exc.code}: {detail}") from exc
        except OSError as exc:
            raise PersistenceError("Supabase persistence request failed") from exc
        if not payload:
            return []
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PersistenceError("Supabase persistence returned invalid JSON") from exc

    def read(self, key: str) -> Optional[StoredObject]:
        rows = self._request(
            "GET",
            {"select": "data_b64,version", "key": f"eq.{key}", "limit": "1"},
        )
        if not rows:
            return None
        item = rows[0]
        try:
            return StoredObject(base64.b64decode(item["data_b64"], validate=True), str(int(item["version"])))
        except (KeyError, TypeError, ValueError) as exc:
            raise PersistenceError("atomic object row is malformed") from exc

    def create(self, key: str, data: bytes) -> StoredObject:
        try:
            rows = self._request(
                "POST",
                body={"key": key, "data_b64": base64.b64encode(bytes(data)).decode("ascii"), "version": 1},
            )
        except ObjectConflict:
            raise
        if len(rows) != 1:
            raise ObjectConflict("atomic create did not create exactly one row")
        return StoredObject(bytes(data), str(int(rows[0]["version"])))

    def replace(self, key: str, data: bytes, expected_version: str) -> StoredObject:
        expected = int(expected_version)
        rows = self._request(
            "PATCH",
            {"key": f"eq.{key}", "version": f"eq.{expected}"},
            {"data_b64": base64.b64encode(bytes(data)).decode("ascii"), "version": expected + 1},
        )
        if len(rows) != 1:
            raise ObjectConflict("atomic replace lost its compare-and-swap race")
        return StoredObject(bytes(data), str(int(rows[0]["version"])))

    def delete(self, key: str, expected_version: str) -> None:
        rows = self._request(
            "DELETE",
            {"key": f"eq.{key}", "version": f"eq.{int(expected_version)}"},
        )
        if len(rows) != 1:
            raise ObjectConflict("atomic delete lost its compare-and-swap race")

    def list(self, prefix: str) -> Iterable[str]:
        rows = self._request(
            "GET",
            {"select": "key", "key": f"like.{prefix}*", "order": "key.asc"},
        )
        return [str(item["key"]) for item in rows]

def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class LeaseRecord:
    owner_id: str
    token: str
    fencing_generation: int
    acquired_at: float
    renewed_at: float
    expires_at: float

    @classmethod
    def decode(cls, raw: bytes) -> "LeaseRecord":
        try:
            value = json.loads(raw.decode("utf-8"))
            record = cls(
                owner_id=str(value["owner_id"]),
                token=str(value["token"]),
                fencing_generation=int(value["fencing_generation"]),
                acquired_at=float(value["acquired_at"]),
                renewed_at=float(value["renewed_at"]),
                expires_at=float(value["expires_at"]),
            )
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LeaseConflict("writer lease record is malformed") from exc
        if not record.owner_id or not record.token or record.fencing_generation < 1:
            raise LeaseConflict("writer lease record is invalid")
        return record

    def encode(self) -> bytes:
        return _canonical_json(asdict(self))


class WriterLease:
    """CAS-backed renewable lease that fences concurrent writers."""

    def __init__(
        self,
        store: AtomicObjectStore,
        *,
        key: str = "authority/writer-lease.json",
        owner_id: str,
        duration_seconds: float = 30.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("owner_id is required")
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        self._store = store
        self.key = key
        self.owner_id = owner_id
        self.duration_seconds = float(duration_seconds)
        self._clock = clock
        self._lock = threading.RLock()
        self._record: Optional[LeaseRecord] = None
        self._object_version: Optional[str] = None

    @property
    def fencing_generation(self) -> Optional[int]:
        with self._lock:
            return self._record.fencing_generation if self._record else None

    def acquire(self, *, attempts: int = 4) -> LeaseRecord:
        """Acquire an absent/expired lease, retrying only CAS races."""
        if attempts < 1:
            raise ValueError("attempts must be at least one")
        with self._lock:
            for _ in range(attempts):
                now = self._clock()
                current = self._store.read(self.key)
                if current is None:
                    record = LeaseRecord(
                        owner_id=self.owner_id,
                        token=secrets.token_urlsafe(24),
                        fencing_generation=1,
                        acquired_at=now,
                        renewed_at=now,
                        expires_at=now + self.duration_seconds,
                    )
                    try:
                        stored = self._store.create(self.key, record.encode())
                    except ObjectConflict:
                        continue
                else:
                    old = LeaseRecord.decode(current.data)
                    if old.expires_at > now:
                        raise LeaseConflict(
                            f"writer lease is held by {old.owner_id!r} until {old.expires_at:.3f}"
                        )
                    record = LeaseRecord(
                        owner_id=self.owner_id,
                        token=secrets.token_urlsafe(24),
                        fencing_generation=old.fencing_generation + 1,
                        acquired_at=now,
                        renewed_at=now,
                        expires_at=now + self.duration_seconds,
                    )
                    try:
                        stored = self._store.replace(
                            self.key, record.encode(), current.version
                        )
                    except ObjectConflict:
                        continue
                self._record = record
                self._object_version = stored.version
                return record
        raise LeaseConflict("writer lease changed during every acquisition attempt")

    def assert_owned(self) -> LeaseRecord:
        """Re-read the lease so an expired or fenced writer fails closed."""
        with self._lock:
            local = self._record
            if local is None:
                raise LeaseLost("writer lease has not been acquired")
            current = self._store.read(self.key)
            if current is None:
                self._clear()
                raise LeaseLost("writer lease no longer exists")
            remote = LeaseRecord.decode(current.data)
            now = self._clock()
            if (
                remote.owner_id != local.owner_id
                or remote.token != local.token
                or remote.fencing_generation != local.fencing_generation
                or remote.expires_at <= now
            ):
                self._clear()
                raise LeaseLost("writer lease expired or was fenced by another writer")
            self._record = remote
            self._object_version = current.version
            return remote

    def renew(self) -> LeaseRecord:
        with self._lock:
            current_record = self.assert_owned()
            assert self._object_version is not None
            now = self._clock()
            renewed = LeaseRecord(
                owner_id=current_record.owner_id,
                token=current_record.token,
                fencing_generation=current_record.fencing_generation,
                acquired_at=current_record.acquired_at,
                renewed_at=now,
                expires_at=now + self.duration_seconds,
            )
            try:
                stored = self._store.replace(
                    self.key, renewed.encode(), self._object_version
                )
            except ObjectConflict as exc:
                self._clear()
                raise LeaseLost("writer lease renewal lost its CAS race") from exc
            self._record = renewed
            self._object_version = stored.version
            return renewed

    def release(self) -> None:
        with self._lock:
            if self._record is None:
                return
            self.assert_owned()
            assert self._object_version is not None
            try:
                self._store.delete(self.key, self._object_version)
            except ObjectConflict as exc:
                self._clear()
                raise LeaseLost("writer lease changed before release") from exc
            self._clear()

    def _clear(self) -> None:
        self._record = None
        self._object_version = None


@dataclass(frozen=True)
class SchemaPolicy:
    required_tables: frozenset[str] = frozenset()
    min_user_version: int = 0
    max_user_version: Optional[int] = None


@dataclass(frozen=True)
class SnapshotEntry:
    generation: int
    object_key: str
    sha256: str
    size: int
    created_at: float
    sqlite_user_version: int
    fencing_generation: int

    @classmethod
    def decode(cls, value: object) -> "SnapshotEntry":
        if not isinstance(value, dict):
            raise SnapshotValidationError("snapshot manifest entry is not an object")
        try:
            entry = cls(
                generation=int(value["generation"]),
                object_key=str(value["object_key"]),
                sha256=str(value["sha256"]),
                size=int(value["size"]),
                created_at=float(value["created_at"]),
                sqlite_user_version=int(value["sqlite_user_version"]),
                fencing_generation=int(value["fencing_generation"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SnapshotValidationError("snapshot manifest entry is malformed") from exc
        if (
            entry.generation < 1
            or entry.size < 1
            or entry.fencing_generation < 1
            or len(entry.sha256) != 64
            or not entry.object_key
        ):
            raise SnapshotValidationError("snapshot manifest entry is invalid")
        return entry


@dataclass(frozen=True)
class SnapshotManifest:
    format_version: int
    current_generation: int
    snapshots: tuple[SnapshotEntry, ...]

    @classmethod
    def empty(cls) -> "SnapshotManifest":
        return cls(format_version=1, current_generation=0, snapshots=())

    @classmethod
    def decode(cls, raw: bytes) -> "SnapshotManifest":
        try:
            value = json.loads(raw.decode("utf-8"))
            if not isinstance(value, dict) or int(value["format_version"]) != 1:
                raise SnapshotValidationError("unsupported snapshot manifest format")
            entries = tuple(SnapshotEntry.decode(item) for item in value["snapshots"])
            manifest = cls(1, int(value["current_generation"]), entries)
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SnapshotValidationError("snapshot manifest is malformed") from exc
        if manifest.current_generation < 0:
            raise SnapshotValidationError("snapshot generation is invalid")
        if entries:
            generations = [entry.generation for entry in entries]
            if generations != sorted(generations, reverse=True):
                raise SnapshotValidationError("snapshot history is not newest-first")
            if len(set(generations)) != len(generations):
                raise SnapshotValidationError("snapshot history repeats a generation")
            if generations[0] != manifest.current_generation:
                raise SnapshotValidationError("manifest current generation is inconsistent")
        elif manifest.current_generation != 0:
            raise SnapshotValidationError("empty manifest has a nonzero generation")
        return manifest

    def encode(self) -> bytes:
        return _canonical_json(
            {
                "format_version": self.format_version,
                "current_generation": self.current_generation,
                "snapshots": [asdict(entry) for entry in self.snapshots],
            }
        )


@dataclass(frozen=True)
class RestoreResult:
    entry: SnapshotEntry
    used_fallback: bool
    last_known_good_path: Optional[Path]


def validate_sqlite_file(path: Path, policy: SchemaPolicy) -> int:
    """Validate SQLite structure and required schema, returning user_version."""
    try:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            rows = conn.execute("PRAGMA integrity_check").fetchall()
            if rows != [("ok",)]:
                detail = "; ".join(str(row[0]) for row in rows[:5])
                raise SnapshotValidationError(f"SQLite integrity_check failed: {detail}")
            user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
    except SnapshotValidationError:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise SnapshotValidationError("snapshot is not a readable SQLite database") from exc
    missing = sorted(policy.required_tables - tables)
    if missing:
        raise SnapshotValidationError(
            "snapshot is missing required tables: " + ", ".join(missing)
        )
    if user_version < policy.min_user_version:
        raise SnapshotValidationError(
            f"SQLite user_version {user_version} is below {policy.min_user_version}"
        )
    if policy.max_user_version is not None and user_version > policy.max_user_version:
        raise SnapshotValidationError(
            f"SQLite user_version {user_version} is above {policy.max_user_version}"
        )
    return user_version


class SnapshotAuthority:
    """Publish immutable SQLite generations and restore validated snapshots."""

    def __init__(
        self,
        store: AtomicObjectStore,
        lease: WriterLease,
        *,
        prefix: str = "database",
        retention: int = 3,
        max_snapshot_bytes: int = 512 * 1024 * 1024,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if retention < 2:
            raise ValueError("retention must preserve at least current and last-known-good")
        if max_snapshot_bytes < 1:
            raise ValueError("max_snapshot_bytes must be positive")
        self._store = store
        self.lease = lease
        self.prefix = prefix.strip("/")
        if not self.prefix:
            raise ValueError("prefix is required")
        self.retention = retention
        self.max_snapshot_bytes = max_snapshot_bytes
        self._clock = clock
        self.manifest_key = f"{self.prefix}/manifest.json"

    def _load_manifest(self) -> tuple[SnapshotManifest, Optional[str]]:
        stored = self._store.read(self.manifest_key)
        if stored is None:
            return SnapshotManifest.empty(), None
        return SnapshotManifest.decode(stored.data), stored.version

    def publish(self, db_path: Path, policy: SchemaPolicy = SchemaPolicy()) -> SnapshotEntry:
        """Synchronously prove a local SQLite state as a durable generation."""
        lease_record = self.lease.assert_owned()
        manifest, manifest_version = self._load_manifest()
        generation = manifest.current_generation + 1
        raw, user_version = self._create_validated_snapshot(Path(db_path), policy)
        digest = hashlib.sha256(raw).hexdigest()
        object_key = (
            f"{self.prefix}/generations/{generation:020d}-"
            f"f{lease_record.fencing_generation}-{digest}.sqlite3"
        )
        # Fence again immediately before any remote mutation.
        self.lease.assert_owned()
        try:
            uploaded = self._store.create(object_key, raw)
        except ObjectConflict as exc:
            raise DurabilityError("immutable generation key already exists") from exc
        try:
            confirmed = self._store.read(object_key)
            if confirmed is None or confirmed.data != raw:
                raise DurabilityError("remote snapshot read-back did not match uploaded bytes")
            entry = SnapshotEntry(
                generation=generation,
                object_key=object_key,
                sha256=digest,
                size=len(raw),
                created_at=self._clock(),
                sqlite_user_version=user_version,
                fencing_generation=lease_record.fencing_generation,
            )
            updated = SnapshotManifest(
                format_version=1,
                current_generation=generation,
                snapshots=(entry,) + manifest.snapshots[: self.retention - 1],
            )
            self.lease.assert_owned()
            try:
                if manifest_version is None:
                    self._store.create(self.manifest_key, updated.encode())
                else:
                    self._store.replace(
                        self.manifest_key, updated.encode(), manifest_version
                    )
            except ObjectConflict as exc:
                raise DurabilityError(
                    "snapshot manifest changed concurrently; durability not acknowledged"
                ) from exc
        except Exception:
            try:
                self._store.delete(object_key, uploaded.version)
            except (ObjectConflict, PersistenceError):
                pass
            raise
        self._prune_generations(updated)
        return entry

    def restore(
        self,
        destination: Path,
        policy: SchemaPolicy = SchemaPolicy(),
    ) -> RestoreResult:
        """Restore the newest valid retained generation via atomic promotion."""
        manifest, _ = self._load_manifest()
        if not manifest.snapshots:
            raise SnapshotValidationError("no remote snapshot generations exist")
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        failures: list[str] = []
        for index, entry in enumerate(manifest.snapshots):
            stored = self._store.read(entry.object_key)
            if stored is None:
                failures.append(f"generation {entry.generation}: object missing")
                continue
            raw = stored.data
            if len(raw) != entry.size or hashlib.sha256(raw).hexdigest() != entry.sha256:
                failures.append(f"generation {entry.generation}: checksum/size mismatch")
                continue
            if len(raw) > self.max_snapshot_bytes:
                failures.append(f"generation {entry.generation}: exceeds size limit")
                continue
            temp_path: Optional[Path] = None
            try:
                fd, temp_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.restore-",
                    suffix=".tmp",
                    dir=str(destination.parent),
                )
                temp_path = Path(temp_name)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                user_version = validate_sqlite_file(temp_path, policy)
                if user_version != entry.sqlite_user_version:
                    raise SnapshotValidationError(
                        "manifest and SQLite user_version do not match"
                    )
                lkg_path: Optional[Path] = None
                if destination.exists():
                    # Retain only a validated local predecessor as last-known-good.
                    lkg_raw, _ = self._create_validated_snapshot(destination, policy)
                    lkg_path = destination.with_suffix(destination.suffix + ".last-known-good")
                    backup_tmp = lkg_path.with_suffix(lkg_path.suffix + ".tmp")
                    with backup_tmp.open("wb") as handle:
                        handle.write(lkg_raw)
                        handle.flush()
                        os.fsync(handle.fileno())
                    os.replace(backup_tmp, lkg_path)
                os.replace(temp_path, destination)
                temp_path = None
                return RestoreResult(entry, index > 0, lkg_path)
            except (OSError, SnapshotValidationError) as exc:
                failures.append(f"generation {entry.generation}: {exc}")
            finally:
                if temp_path is not None:
                    try:
                        temp_path.unlink()
                    except FileNotFoundError:
                        pass
        raise SnapshotValidationError(
            "no retained snapshot passed validation: " + " | ".join(failures)
        )

    def _create_validated_snapshot(
        self, db_path: Path, policy: SchemaPolicy
    ) -> tuple[bytes, int]:
        if not db_path.is_file():
            raise SnapshotValidationError(f"SQLite database does not exist: {db_path}")
        temp_path: Optional[Path] = None
        source: Optional[sqlite3.Connection] = None
        target: Optional[sqlite3.Connection] = None
        try:
            fd, temp_name = tempfile.mkstemp(prefix="ats-one-snapshot-", suffix=".sqlite3")
            os.close(fd)
            temp_path = Path(temp_name)
            source_uri = f"file:{db_path.resolve().as_posix()}?mode=ro"
            source = sqlite3.connect(source_uri, uri=True, timeout=5)
            target = sqlite3.connect(temp_path, timeout=5)
            source.backup(target)
            target.commit()
            target.close()
            target = None
            source.close()
            source = None
            size = temp_path.stat().st_size
            if size < 1 or size > self.max_snapshot_bytes:
                raise SnapshotValidationError(
                    f"snapshot size {size} is outside the allowed range"
                )
            user_version = validate_sqlite_file(temp_path, policy)
            raw = temp_path.read_bytes()
            if len(raw) != size:
                raise SnapshotValidationError("snapshot changed while it was being read")
            return raw, user_version
        except SnapshotValidationError:
            raise
        except (sqlite3.Error, OSError) as exc:
            raise SnapshotValidationError("could not create a consistent SQLite backup") from exc
        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()
            if temp_path is not None:
                try:
                    temp_path.unlink()
                except FileNotFoundError:
                    pass

    def _prune_generations(self, manifest: SnapshotManifest) -> None:
        # Pruning must never run under a stale lease/manifest: a successor could
        # otherwise reference a generation that this process considers old.
        try:
            self.lease.assert_owned()
            current, _ = self._load_manifest()
        except (LeaseLost, SnapshotValidationError):
            return
        if current.current_generation != manifest.current_generation:
            return
        keep = {entry.object_key for entry in current.snapshots}
        prefix = f"{self.prefix}/generations/"
        for key in self._store.list(prefix):
            if key in keep or not key.startswith(prefix) or not key.endswith(".sqlite3"):
                continue
            try:
                self.lease.assert_owned()
            except LeaseLost:
                return
            stored = self._store.read(key)
            if stored is None:
                continue
            try:
                self._store.delete(key, stored.version)
            except ObjectConflict:
                # Pruning is best-effort and never weakens the durable manifest.
                continue


class DurabilityTicket:
    def __init__(self, coordinator: "DurableSnapshotCoordinator", sequence: int) -> None:
        self._coordinator = coordinator
        self.sequence = sequence

    def wait(self, timeout: Optional[float] = None) -> SnapshotEntry:
        return self._coordinator._wait(self.sequence, timeout)


class DurableSnapshotCoordinator:
    """Bounded, coalescing durability worker with a fail-closed error latch."""

    def __init__(
        self,
        authority: SnapshotAuthority,
        db_path: Path,
        policy: SchemaPolicy = SchemaPolicy(),
        *,
        max_pending: int = 256,
        coalesce_seconds: float = 0.01,
    ) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be positive")
        if coalesce_seconds < 0:
            raise ValueError("coalesce_seconds cannot be negative")
        self.authority = authority
        self.db_path = Path(db_path)
        self.policy = policy
        self.max_pending = max_pending
        self.coalesce_seconds = coalesce_seconds
        self._condition = threading.Condition()
        self._submitted = 0
        self._completed = 0
        self._result: Optional[SnapshotEntry] = None
        self._failure: Optional[BaseException] = None
        self._closed = False
        self._thread = threading.Thread(
            target=self._run, name="ats-one-durable-snapshot", daemon=True
        )
        self._thread.start()

    @property
    def healthy(self) -> bool:
        with self._condition:
            return self._failure is None and not self._closed

    def notify_commit(self) -> DurabilityTicket:
        """Register a local commit; caller must wait before acknowledging success."""
        with self._condition:
            if self._closed:
                raise DurabilityError("durability coordinator is closed")
            if self._failure is not None:
                raise DurabilityError("durability coordinator is degraded") from self._failure
            if self._submitted - self._completed >= self.max_pending:
                raise DurabilityError("durability queue is full")
            self._submitted += 1
            ticket = DurabilityTicket(self, self._submitted)
            self._condition.notify_all()
            return ticket

    def flush_commit(self, timeout: float) -> SnapshotEntry:
        return self.notify_commit().wait(timeout)

    def _wait(self, sequence: int, timeout: Optional[float]) -> SnapshotEntry:
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._completed < sequence and self._failure is None:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise DurabilityTimeout(
                        f"remote durability not proven for commit {sequence} before timeout"
                    )
                self._condition.wait(remaining)
            if self._failure is not None:
                raise DurabilityError(
                    f"remote durability failed for commit {sequence}"
                ) from self._failure
            if self._result is None:
                raise DurabilityError("durability worker completed without a snapshot")
            return self._result

    def close(self, timeout: float = 5.0) -> None:
        with self._condition:
            self._closed = True
            self._condition.notify_all()
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise DurabilityTimeout("durability worker did not stop before timeout")

    def _run(self) -> None:
        while True:
            with self._condition:
                while self._submitted <= self._completed and not self._closed:
                    self._condition.wait()
                if self._closed and self._submitted <= self._completed:
                    return
            if self.coalesce_seconds:
                time.sleep(self.coalesce_seconds)
            with self._condition:
                target = self._submitted
            try:
                result = self.authority.publish(self.db_path, self.policy)
            except BaseException as exc:  # latch every worker failure and stop writes
                with self._condition:
                    self._failure = exc
                    self._condition.notify_all()
                return
            with self._condition:
                self._result = result
                self._completed = target
                self._condition.notify_all()
