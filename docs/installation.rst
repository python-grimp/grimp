============
Installation
============

At the command line::

    pip install grimp

Windows Application Control
===========================

Grimp requires a native Rust extension, ``grimp._rustgrimp``. On Windows this is
a ``.pyd`` file. Smart App Control or another Windows Application Control policy
may prevent Python from loading it, with an error such as::

    ImportError: DLL load failed while importing _rustgrimp:
    An Application Control policy has blocked this file.

The current Windows wheel release process does not publisher-sign the native
extension. Publisher signing would require a trusted code-signing certificate or
signing service and changes to the release process; no signed release date is
currently committed. A wheel's PyPI SHA-256 hash and its ``RECORD`` metadata
can help verify file integrity, but are not Windows code signatures and do not
establish that Windows will allow the extension to load.

There is no Grimp setting or pure-Python fallback that resolves an Application
Control block. Upgrading or building from source does not guarantee that the
resulting extension will be accepted by the policy. Even a valid code signature
does not guarantee acceptance under every policy.

If your policy blocks the extension, there is currently no supported Grimp-only
fix for running it in that Windows environment while retaining the policy.
You can instead run Grimp and Import Linter in a Linux environment, such as a
Linux CI runner, with the same source tree and architecture contracts. This
leaves the Windows protections in place. Do not disable or bypass them to load
the extension.

When reporting a block, please include the Grimp and Python versions, Windows
version and architecture, the wheel filename and hash, and sanitized Code
Integrity event details (for example, events 3077 and 3033). A block reported
for one version does not establish whether another version will be blocked.
