# Terminal HTTP/browser refresh against main, 2026-11-14

PR #492 integrates refreshed parent #490 (`6658319f`) and main `072e7284`
without rewriting history. All 38 existing non-candidate runtime probe bodies,
the official archive records, case inventory, production installer, candidate
adapter and historical failed evidence remain intact.

The full server suite passed 2,389 tests with 65 skips at integration `e6fd124d`;
103 focused tests also passed. The first new AMD64 VM replay then exposed a
published-frontend initialization failure. Status and four method requests
succeeded, including resize, but no config/subscription/buffer call followed.
The failed raw report is preserved in the companion `*-failure-*.json.gz`.

The exact published Terminal initializer dereferences
`fakeInputRef.current.m_elInput.tabIndex` after resize. Framey's current ref
handle had `.element` and `Focus()` but no `.m_elInput`. Adding the same native
input under that getter fixes the contract while keeping both getters null
after unmount. The new real React/DOM assertion failed before this fix; all
nine TextField browser tests passed after it, retaining TabMaster's published
search behavior, stable handles, callback replacement and retired refs.

The fresh VM replay at `44ff684e` passed. Its 177 frozen source fingerprints,
bootstrap, published Decky 3.3.0 binary pin, CPython 3.14.8 ABI, result packet,
frontend bytes and three captures were independently verified. Captures were
visually inspected: an initialized terminal, actual separate output text and
an empty terminal list after removal. Horizontal overflow remains.

Observed in the disposable, networkless AMD64 VM:

- Twenty successful HTTP requests and seventeen successful synthetic CEF
  calls; the slowest HTTP request took 5.631 seconds. Production deadlines and
  mutation behavior were unchanged.
- Actual native private PTY input/output, 31x97 resize, explicit removal,
  plugin reload, owned-shell reaping, sibling survival and config persistence.
- Browser-created shell ancestry reached the real owned Decky user service.
  Actual output reached the production event dispatcher and rendered in xterm;
  the exact private marker bytes and shell removal were verified.
- The sandbox remained enabled. Request drain, event listener removal,
  browser/HTTP cleanup, service stop, original unit restoration, temporary
  bundle removal, guest user-manager stop and owned QEMU reaping passed.
- The native primary console gate passed with no forced plugin kill or shutdown
  error marker. The generic capture's `cleanShutdownVerified=false` remains
  diagnostic; a complete native descendant shutdown verdict is not claimed.
  The user service stopped successfully in 3.202 seconds. Original missing
  config and pre-facade injector warnings remain in the raw report.

This is a private candidate with synthetic CEF, receipt and input. It does
not verify official managed Terminal installation, real Steam CEF, Frame
pixels, wearer visibility, physical controllers, scrolling or the VR keyboard.
Fresh native ARM64 and full hosted CI still must qualify the refreshed head;
older ARM64 green results are historical only. The earlier ARM64 timeout cause
is not established or excluded by this AMD64 result.
