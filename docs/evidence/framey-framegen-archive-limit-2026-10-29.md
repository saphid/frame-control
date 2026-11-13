# Decky-Framegen archive limit, 29 October 2026

The live official Decky feed still listed 116 visible plugins with the same
version and SHA-256 values as the pinned Framey catalog. Its Decky-Framegen
0.11.15 row advertised SHA-256
`14015d5a652c78b2041fd9668685573840530c306e414aabc0d3cebf95be0642`.
The corresponding ZIP downloaded from the official version CDN was
**75,140,408 bytes** and matched that hash. Static ZIP inspection found 27
entries totaling 93,916,143 uncompressed bytes, including Windows DLLs,
an OptiScaler `.7z`, its Python backend and its frontend. No plugin code was
executed in this inspection.

Framey's managed installer reads at most **50 MiB + 1 byte** and accepts ZIPs
of at most 50 MiB (`MAX_ZIP = 50 * 1024 * 1024`). That limit, rather than a
published hash mismatch, explains the recorded fake-Frame rejection. The
catalog's old generic rejection text remains as historical test output; its
current reason now identifies the actual size limit. The installer retains the
same limit and reports size and hash failures separately.

Decky-Framegen remains **broken/blocked** in Framey. Its published backend
extracts OptiScaler under the user's home directory and offers install and
uninstall actions for game launch changes. Those actions, Proton integration,
actual Frame backend behavior, wearer-visible VR and controller use were not
tested. No headset was accessed or changed for this check.
