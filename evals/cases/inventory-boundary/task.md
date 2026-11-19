# Inventory reservation issue

Users report that a legitimate reservation is sometimes refused even though
enough stock is available.

The public operation `reserve(available, requested)` receives nonnegative integer
available stock and a positive integer request. Success returns the stock
remaining. A request exceeding stock returns `None`. Zero or negative requests
raise `ValueError`. Callers validate non-integer inputs and negative available
stock; changing those responsibilities is out of scope.

Investigate the reported behavior, make the smallest correction, add a
discriminating public-behavior regression, and verify the complete local suite.
Preserve the public API and the existing tests. Use at most three diagnosis probes
and two repair attempts. Return diagnosis, change-set, and verification-report
artifacts with actual evidence, current source identity, and coverage limits.

The host grants read/write access and local Python execution only in the isolated
candidate directory. No network, external publication, tracker changes, messages,
integration, deployment, or skill-library edits are part of this task.
