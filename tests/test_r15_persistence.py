import hashlib
import json
import sqlite3
import tempfile
import threading
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence_authority import (
    DurableSnapshotCoordinator,
    DurabilityError,
    LeaseConflict,
    LeaseLost,
    ObjectConflict,
    SchemaPolicy,
    SnapshotAuthority,
    SnapshotManifest,
    SnapshotValidationError,
    StoredObject,
    WriterLease,
)


class MemoryAtomicStore:
    """Deterministic CAS store used to exercise authority semantics."""

    def __init__(self):
        self._objects = {}
        self._versions = {}
        self._lock = threading.Lock()
        self.fail_create_prefix = None

    def read(self, key):
        with self._lock:
            if key not in self._objects:
                return None
            return StoredObject(self._objects[key], str(self._versions[key]))

    def create(self, key, data):
        with self._lock:
            if self.fail_create_prefix and key.startswith(self.fail_create_prefix):
                raise RuntimeError("injected remote failure")
            if key in self._objects:
                raise ObjectConflict("exists")
            self._versions[key] = 1
            self._objects[key] = bytes(data)
            return StoredObject(self._objects[key], "1")

    def replace(self, key, data, expected_version):
        with self._lock:
            if key not in self._objects or str(self._versions[key]) != expected_version:
                raise ObjectConflict("CAS mismatch")
            self._versions[key] += 1
            self._objects[key] = bytes(data)
            return StoredObject(self._objects[key], str(self._versions[key]))

    def delete(self, key, expected_version):
        with self._lock:
            if key not in self._objects or str(self._versions[key]) != expected_version:
                raise ObjectConflict("CAS mismatch")
            del self._objects[key]
            del self._versions[key]

    def list(self, prefix):
        with self._lock:
            return sorted(key for key in self._objects if key.startswith(prefix))

    def overwrite_for_test(self, key, data):
        with self._lock:
            self._versions[key] += 1
            self._objects[key] = bytes(data)


class FakeClock:
    def __init__(self, now=1_000.0):
        self.now = now

    def __call__(self):
        return self.now


def create_db(path, value="first"):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA user_version=14")
    conn.execute("CREATE TABLE candidates(id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
    conn.execute("INSERT INTO candidates(name) VALUES(?)", (value,))
    conn.commit()
    conn.close()


def read_value(path):
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT name FROM candidates").fetchone()[0]
    finally:
        conn.close()


class WriterLeaseTests(unittest.TestCase):
    def test_only_one_live_writer_can_acquire(self):
        store = MemoryAtomicStore()
        clock = FakeClock()
        first = WriterLease(store, owner_id="instance-a", clock=clock)
        second = WriterLease(store, owner_id="instance-b", clock=clock)
        record = first.acquire()
        self.assertEqual(record.fencing_generation, 1)
        with self.assertRaises(LeaseConflict):
            second.acquire()
        self.assertEqual(first.assert_owned().owner_id, "instance-a")

    def test_expired_writer_is_fenced_by_cas_takeover(self):
        store = MemoryAtomicStore()
        clock = FakeClock()
        first = WriterLease(store, owner_id="instance-a", duration_seconds=5, clock=clock)
        second = WriterLease(store, owner_id="instance-b", duration_seconds=5, clock=clock)
        first.acquire()
        clock.now += 6
        taken = second.acquire()
        self.assertEqual(taken.fencing_generation, 2)
        with self.assertRaises(LeaseLost):
            first.assert_owned()


class SnapshotAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db = self.root / "source.db"
        create_db(self.db)
        self.store = MemoryAtomicStore()
        self.clock = FakeClock()
        self.lease = WriterLease(
            self.store, owner_id="writer", duration_seconds=60, clock=self.clock
        )
        self.lease.acquire()
        self.authority = SnapshotAuthority(
            self.store, self.lease, retention=2, clock=self.clock
        )
        self.policy = SchemaPolicy(frozenset({"candidates"}), min_user_version=14)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_generations_are_immutable_checksummed_and_retained(self):
        first = self.authority.publish(self.db, self.policy)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE candidates SET name='second'")
        conn.commit()
        conn.close()
        self.clock.now += 1
        second = self.authority.publish(self.db, self.policy)
        self.assertEqual((first.generation, second.generation), (1, 2))
        manifest = SnapshotManifest.decode(
            self.store.read("database/manifest.json").data
        )
        self.assertEqual([item.generation for item in manifest.snapshots], [2, 1])
        for entry in manifest.snapshots:
            raw = self.store.read(entry.object_key).data
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry.sha256)

    def test_restore_falls_back_from_corrupt_current_and_keeps_local_lkg(self):
        first = self.authority.publish(self.db, self.policy)
        conn = sqlite3.connect(self.db)
        conn.execute("UPDATE candidates SET name='second'")
        conn.commit()
        conn.close()
        self.clock.now += 1
        second = self.authority.publish(self.db, self.policy)
        self.store.overwrite_for_test(second.object_key, b"corrupt")
        destination = self.root / "restored.db"
        create_db(destination, "local-known-good")
        result = self.authority.restore(destination, self.policy)
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.entry.generation, first.generation)
        self.assertEqual(read_value(destination), "first")
        self.assertEqual(read_value(result.last_known_good_path), "local-known-good")

    def test_restore_rejects_unverified_bytes_without_replacing_destination(self):
        entry = self.authority.publish(self.db, self.policy)
        self.store.overwrite_for_test(entry.object_key, b"not sqlite")
        destination = self.root / "destination.db"
        create_db(destination, "preserved")
        with self.assertRaises(SnapshotValidationError):
            self.authority.restore(destination, self.policy)
        self.assertEqual(read_value(destination), "preserved")

    def test_schema_policy_rejects_wrong_database(self):
        with self.assertRaises(SnapshotValidationError):
            self.authority.publish(
                self.db, SchemaPolicy(frozenset({"missing_table"}), min_user_version=14)
            )


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.db = self.root / "source.db"
        create_db(self.db)
        self.store = MemoryAtomicStore()
        lease = WriterLease(self.store, owner_id="writer")
        lease.acquire()
        self.authority = SnapshotAuthority(self.store, lease)
        self.policy = SchemaPolicy(frozenset({"candidates"}), min_user_version=14)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_concurrent_waiters_are_covered_by_one_generation(self):
        coordinator = DurableSnapshotCoordinator(
            self.authority, self.db, self.policy, coalesce_seconds=0.05
        )
        try:
            tickets = [coordinator.notify_commit() for _ in range(12)]
            generations = [ticket.wait(2).generation for ticket in tickets]
            self.assertEqual(generations, [1] * 12)
        finally:
            coordinator.close()

    def test_remote_failure_is_latched_and_future_writes_fail_closed(self):
        self.store.fail_create_prefix = "database/generations/"
        coordinator = DurableSnapshotCoordinator(
            self.authority, self.db, self.policy, coalesce_seconds=0
        )
        try:
            with self.assertRaises(DurabilityError):
                coordinator.flush_commit(2)
            self.assertFalse(coordinator.healthy)
            with self.assertRaises(DurabilityError):
                coordinator.notify_commit()
        finally:
            coordinator.close()


if __name__ == "__main__":
    unittest.main()
