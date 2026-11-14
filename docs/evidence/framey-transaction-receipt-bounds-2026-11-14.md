# Transaction ownership receipt bounds

The store transaction now reads at most 16 KiB plus one overflow byte for target and peer ownership receipts. Oversized targets cannot authorize Update or Remove. Refusal preserves installed data and receipt bytes, releases the lock and occurs before stopping Decky. Exact-limit receipts and repair/retry remain supported.

The unchanged production APPLY failed four target subcases and the peer I/O-budget regression. The exact source commit `a716af1a78c520c33966e1d9d12ec8af98f78985` passes all 122 store tests; the final receipt subset passes seven. The companion JSON binds source and compressed red/green logs by SHA-256.

Tests execute the transaction script against disposable synthetic homes and service commands. They do not prove headset or worn VR behavior.
