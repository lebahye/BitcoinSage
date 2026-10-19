---
name: GitHub export privacy
description: Prevent local portfolio state from leaking through Git history during GitHub synchronization.
---

Publish the current tracked source tree as a snapshot whose parent is the existing GitHub branch, rather than pushing the full local ancestry.

**Why:** The destination repository is public, and older local commits contain portfolio target state even after that file is removed from the latest tree. Ignoring a file does not remove it from history.

**How to apply:** Fetch the destination first, preserve its code changes, exclude credential and local-state files, then create an export commit from the verified source tree with only the remote tip as its parent. Push without force and verify the remote commit and tree. Keep local checkpoint history intact. Re-check current tracking and visibility before future exports.
