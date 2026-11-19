# Failure-reader test budget accounting

The original #742 head 551d26de failed the same existing unit assertion in three original Server tests jobs. Each expected an eight-second subprocess timeout after query preparation had already consumed part of that same eight-second budget. The original local test reproduces that assertion failure. No runtime deadline violation is inferred.

The corrected test fixes the monotonic clock at 100 and 100.25 seconds, then checks a 7.75-second transport timeout while retaining the report's eight-second total budget, partial parent snapshot, import phases, timeout and incomplete-line assertions. All AST outside this one existing method is identical; production and runtime probes are unchanged.

Sixty focused methods passed with no skips. The full suite passed 2548 tests with 71 skips in 417.719 seconds. Initial sandbox loopback denials are retained separately from the permitted loopback run.

Original CI failures remain failed. Eight of fourteen original-head runtime artifacts are approved; ARM Terminal browser artifact 14182162961 remains held because its removal screenshot retains a row while the canonical DOM report is empty. Its bytes are unchanged. This test correction establishes no screenshot, startup or historical ARM repair. The new head requires its own original checks and artifacts; main and release remain unqualified. No plugin/VM or hosted runtime was repeated.
