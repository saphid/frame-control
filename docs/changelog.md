# Changelog

## Unreleased

- Battery monitoring now selects the Frame fuel gauge predictably, handles
  missing or invalid readings, and shows optional cycle count, full/design
  capacity and estimated capacity health in Control Center. Unknown charging
  status stays explicit. Monitoring is read-only; charge limits remain
  unsupported on Frame. The read-only parser was checked on a real Frame; the UI was not.
