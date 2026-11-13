# psutil 7.2.2

Unmodified upstream PyPI wheels, retrieved 26 October 2026. BSD-3-Clause;
see LICENSE.txt and the license retained in each wheel.
Source: https://github.com/giampaolo/psutil/tree/release-7.2.2
Release metadata: https://pypi.org/pypi/psutil/7.2.2/json

| Local file | Upstream wheel | SHA-256 |
| --- | --- | --- |
| x86_64.whl | psutil-7.2.2-cp36-abi3-manylinux2010_x86_64.manylinux_2_12_x86_64.manylinux_2_28_x86_64.whl | 076a2d2f923fd4821644f5ba89f059523da90dc9014e85f8e45a5774ca5bc6f9 |
| aarch64.whl | psutil-7.2.2-cp36-abi3-manylinux2014_aarch64.manylinux_2_17_aarch64.manylinux_2_28_aarch64.whl | b0726cecd84f9474419d67252add4ac0cd9811b04d61123054b9fb6f57df6e9e |

Only exact ID 89 / DeckySpy 0.6.7 receives this missing dependency, isolated
inside its py_modules directory, alongside Framey’s battery-name fallback.
The fallback reads only Linux power_supply files identified as type Battery;
it leaves native psutil results intact and never writes sysfs. The host and remote installer both verify
these digests, and the remote selects the native ELF architecture. No pip or
runtime download runs on the Frame. The stable ABI is exercised with actual
Decky 3.3.0 rather than assuming compatibility with its bundled Python.
Existing plugin copies require an explicit managed update or reinstall.
