# Surround macOS temporary-path fixture repair

The exact PR head `cfa6a54415c3f858e2d2659d99ce9d9241c8c7d8` failed
macOS server-tests in job 124777797268: its temporary directory contained the
platform's symlink alias. The production audio directory guard correctly
refused that path. Resolve only the disposable test root before passing it to
the runtime. Production code, native checker/probe, archive and all catalog
policies remain byte-identical to that head; the symlink guard stays intact.

A private Linux temporary-root alias reproduces all **14 original errors**
across nine tests. The repaired fixture passes **all nine / zero skips** in the
same alias environment, including source/destination/runtime symlink refusals.
Raw old/new logs and exact source hashes are retained. The first local wrapper
checked cleanup before sandbox's registered atexit cleanup; it was repaired to
remove only its own sandbox before checking. This wrapper failure does not
invalidate the separately retained old/new test results.

This is a fixture reproduction, not a completed macOS-hosted rerun. Prior
native and full-unit evidence keeps its original source attribution. Fresh
exact-head hosted CI, native AMD64/ARM64, e2e and applicable ownership/package
gates remain required. No headset or schedule was touched. No merge or release
is qualified by this fixture check.
