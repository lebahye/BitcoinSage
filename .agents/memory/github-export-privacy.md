---
name: GitHub export privacy
description: Prevent local portfolio state from leaking through Git history during GitHub synchronization.
---

Publish the current tracked source tree as a snapshot whose parent is the existing GitHub branch, rather than pushing the full local ancestry.

**Why:** The destination repository is public, and older local commits contain portfolio target state even after that file is removed from the latest tree. Ignoring a file does not remove it from history.

**How to apply:** Fetch the destination first, preserve its code changes, exclude credential and local-state files, then create an export commit from the verified source tree with only the remote tip as its parent. Push without force and verify the remote commit and tree. Keep local checkpoint history intact. Re-check current tracking and visibility before future exports.

## Approved target-price export

The current portfolio target-price file may be tracked and uploaded publicly. This is not approval to publish credentials or all historical local data.

**Why:** On 2026-10-19, after being told that the repository is public and that financial data may remain in Git history after deletion, the user explicitly chose to upload the existing target-price data publicly.

**How to apply:** Include the current target-price file in GitHub synchronization. Keep authentication tokens, environment secrets, caches, and other unapproved local financial state excluded.
