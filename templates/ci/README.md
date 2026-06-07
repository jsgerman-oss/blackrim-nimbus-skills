# Standard CI templates for blackrim rigs

Copy these into every rig repo you own under jsgerman-oss so the fleet shares
one security baseline.

- `rafter-security.yml` goes to `.github/workflows/rafter-security.yml`.
  An offline secret-scanning gate (Raftersecurity/rafter-cli). No credentials,
  no sign-up. It runs on push to the default branch, on pull requests, weekly,
  and on manual dispatch. Exit 1 means a secret was found and the check fails.

- `rafter.yml` goes to the repo root as `.rafter.yml`.
  The scan policy. It excludes dependency lockfiles, whose integrity hashes look
  like high-entropy keys. Add a path here only after confirming a finding is a
  false positive (a public test vector, a documented placeholder, and the like).

- `dependabot.yml` goes to `.github/dependabot.yml`.
  It watches the github-actions ecosystem weekly and opens one grouped version
  bump PR, which keeps the pinned Rafter action (and the others) current without
  a flood of one-per-action PRs.

New rig checklist: copy all three files, commit, and confirm the first scan is
green.
