# Superseded: Music Control bound-method fixture

The #335 result was incorrect. Its test instantiated `module.Plugin()`, while
actual Decky 3.3.0 uses the class `module.Plugin` for this legacy manifest and
supplies the class as `self`. The published backend's explicit-self calls are
correct in that runtime. Removing those arguments breaks actual Decky discovery
and transport.

The follow-up [real runtime checks](framey-mpris-runtime-2026-10-26.md) reproduce
the regression, remove the incorrect transformation and replace the test with
the actual legacy calling convention. They also identify and repair a separate
Frame OS system-command library-path failure. Existing copies installed with
`music-control-bound-methods` must be removed/reinstalled or explicitly updated.
Both official Music Control entries remain partial; the follow-up describes
exactly what passed and what remains unverified.
