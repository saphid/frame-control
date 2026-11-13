# UTF-8 pipes for the timeout-output fixture

PR #535's Windows server suite failed only its new timeout test: 1,958 tests,
one failure, 308 platform/optional skips. The stderr length and ASCII stdout
sentinel passed; the Unicode stderr sentinel failed. Job `124729794442` checked
out GitHub merge `22c5a4818de85ef5bd6d841462f243ff566eaab0`; its full tree equals publication `8dab576a871e0ce04f403d87c21547217b665e51`.

Commit `16940e8b2e0f9bdcb305a0eed6630a1721ee3a48` changes only the test's observed real-child Popen wrapper to
set `encoding='utf-8'`, matching the Linux guest's text pipes independently of
the host's locale. All original Unicode, 10,000-character bounds, timeout,
pressured output and child-reaping assertions remain. The complete test AST
returns to the published AST when that one assignment is removed. Guest
implementation, deadlines, return values, failure checks and cleanup are unchanged.

A local control uses real children and Windows subprocess.run's **string-valued
timeout-output contract**, with cp1252 as the ambient default. The published
fixture fails the same Unicode sentinel; the explicit UTF-8 fixture passes.
This runs on Linux, **not Windows**. The actual hosted Windows code page was not
recorded; the control demonstrates a matching decoding failure, not a direct
observation of that setting. A fresh actual Windows run remains required.
All 100 package-related tests also pass locally with zero skips.

The original ARM64 migration/service shutdown hang is not fixed or qualified.
This local change is prepared while sibling #535 jobs are live; it will not be
pushed until every existing job is terminal. After publication, all fresh exact-head
hosted gates remain required. No actual package VM, Steam CEF or real Frame was
contacted; schedules and compatibility policies are unchanged. No release.

Raw packet SHA-256: `167dafddcbec78b61f3bbbb90cb5fde94b3d1965f2441af2f81c552a9b37d92b`. It retains both fixture sources, control
program/logs, package test log, failed job/checkout/tree bindings and failure excerpt.
