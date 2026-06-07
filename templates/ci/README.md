# Standard CI templates for blackrim rigs

Copy these into every rig repo so the fleet shares one security baseline.

- `rafter-security.yml` goes to `.github/workflows/rafter-security.yml`.
  An offline secret-scanning gate (Raftersecurity/rafter-cli). No credentials,
  no sign-up. It runs on push to the default branch, on pull requests, weekly,
  and on manual dispatch. Exit 1 means a secret was found and the check fails.

- `dependabot.yml` goes to `.github/dependabot.yml`.
  It watches the github-actions ecosystem weekly and opens version-bump PRs,
  which keeps the pinned Rafter action (and the others) current.

New rig checklist: copy both files, commit, and confirm the first scan is green.
