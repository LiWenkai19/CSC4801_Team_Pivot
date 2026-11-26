# Using Docker for the Final Project

Each team repository **MUST** contain a `Dockerfile` so that anyone can build and
run the complete environment from any commit on `main`. Images are rebuilt from
source: there is **no image tar to upload**. Graders and auditors build from the
repository directly, including after every bug fix.

## What your repository must provide

- A `Dockerfile` at the location documented in `INSTALL.md`.
- Entrypoint scripts, migrations, and seed scripts committed to the repository.
- Exact build, start, migrate, seed, and unit-test commands in `INSTALL.md`.
- Documented images, configuration, and startup commands for any dependencies.

The build **MUST** succeed from a clean checkout without an undocumented command
or secret. The running environment **MUST** reproduce the deterministic seed data.

## Build and run

Example commands (replace the image name, port, and application commands with
those documented by the team):

```bash
docker build -t team-example .
docker run -d --name team-example -p 127.0.0.1:8080:8080 team-example
docker exec team-example <migration-command>
docker exec team-example <seed-command>
docker exec team-example <unit-test-command>
```

`INSTALL.md` must also document how to start any required dependencies and how
to persist or reset local data. Graders must be able to follow that document
without guessing a command, image, or secret.

## Auditing another team

Auditors build from the **latest commit on the target team's `main` branch**.
All developers on the target team publish their changes and fixes to `main`.
Auditors only find and report bugs; the target team is responsible for fixing them.
Always update to the newest commit before auditing to avoid reporting stale bugs:

```bash
git clone <target-repo>
cd <target-repo>
git checkout main
git pull
docker build -t audit-target .
```

Then follow the team's `INSTALL.md` to start, migrate, seed, and run unit tests.
Record the exact commit SHA in each report. Do not modify the target team's
source or repository; see [`PEER_REVIEW.md`](PEER_REVIEW.md) for the safety boundary.
