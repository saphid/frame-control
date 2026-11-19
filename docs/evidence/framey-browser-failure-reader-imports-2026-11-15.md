# Bounded browser failure reader imports

The original accepted-main ARM signed browser run failed readiness: deadline 60.080 s, completion 60.507 s, parent ready progress received 63.978 s. It completed no UI stages; its separate 8 s failure reader reached only the syncthing_browser and hashlib import markers. Source, dedicated packet and owned cleanup were verified. No cause is established.

The candidate executes the unchanged read-only query with its required transport imports, without importing unrelated browser setup. Source extraction counts against the same 8 s deadline; reads and query size are bounded. All startup/driver/cleanup AST outside this failure-only reader is identical. The original fails a controlled unrelated-initialization stall; 41 focused methods pass without skips on Python 3.12 and 3.9, including deadline, original transport-timeout, readiness and actual owned-child controls.

The earlier private revision and an incomplete-snapshot test setup error are retained. No plugin/VM or hosted runtime was repeated, no historical failure or ARM repair was established, and neither failed main nor release is qualified.
