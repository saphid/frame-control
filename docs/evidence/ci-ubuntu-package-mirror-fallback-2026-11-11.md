# Bounded Ubuntu CI package installation

Repeated hosted jobs failed before application tests: Ubuntu mirror DNS errors
prevented zsh or QEMU installation, and the ARM64 ownership job reached its
25-minute job limit during installation. A later unchanged ARM64 package retry
passed QEMU installation, demonstrating that this preparation failure can recover
without a product change.

The CI helper uses private source and index files for two bounded attempts:
Ubuntu's archive/ports endpoint, then MIT's Ubuntu mirror. Each attempt has a
90-second update limit and a 180-second install limit, with process-group cleanup.
A partial index update is an error; fallback starts with fresh lists. Both mirrors
use the runner's Ubuntu archive keyring. APT's signature, expiry and package-hash
verification remain enabled, and APT retains its native architecture selection
(including Ubuntu 26.04's amd64v3). Runner repository configuration is unchanged.

Validation:

- Six regression tests cover primary success, DNS/command timeout fallback,
  failed archive downloads, fail-closed signature errors, separate index state,
  unchanged trust policy, native architecture selection and invalid arguments.
- The existing four runtime-input cache tests pass.
- MIT's noble ARM64 and resolute x86 release, updates and security InRelease files
  all verify with the existing Ubuntu archive keyring (six signed metadata files).
- A disposable Ubuntu 24.04 x86 container with a deliberately unavailable primary
  installs zsh through the fallback with normal APT authentication. The existing
  source configuration is checked unchanged. The final source is retested before
  submission; native hosted validation remains required on both architectures.

This verifies CI dependency preparation. It does not establish the historical
ARM64 shutdown cause or qualify an application release. No real Frame, worn UI,
physical controller or VR keyboard was tested.
