# Wrapped route merge, 14 November 2026

PR #704 merged as `c764040d` after all 23 exact-head hosted checks passed. The
actual-main integration after #698 passes 38 panel checks and five unchanged
browser fixtures through CDP. GitHub's merge tree and both parents exactly
match that tested integration.

The original hosted browser test actually ran and passed memo/forwardRef,
nested wrappers, retained element props/refs, replacement cleanup, history and
invalid-type cases. The old host fails the new fixture with its expected route
validation error. Both native architectures' full runtime and Terminal-candidate
artifacts pass independent source, pinned-loader and console audits.

The two local standard dump-DOM command timeouts remain beside the CDP passes
and original hosted success. Synthetic local routes do not prove published
plugin wrapper use, backend effects, physical input or worn visibility.
