# Aegis skills

Skill pack for the FF Aegis robot dog, written against FF SDK v0.1.0a10.

| Skill | What it does |
|---|---|
| `check` | Health check, battery, state and pose. Doesn't move. |
| `greet` | Stands, nods twice, offers a paw (point-foot dogs only), lies down. |
| `square` | Walks a square, 0.5 m per side by default (`--side` changes it), prints the drift. |
| `nod_dance` | Nods, turns, leans and bobs in place at 100 BPM. |

Every skill refuses to move if the native control link is down, triggers an
emergency stop on any error, and ends with the dog going limp (`damping()`).

## The SDK is not in this repo

The devkit is proprietary to Faraday Future and is git-ignored. Download
`ff_sdk_aegis_devkit.zip` from https://api-docs.ff.com/aegis.html (FF sign-in
needed) and unzip it here, so you have `aegis_devkit/` next to `aegis_skills.py`.

## Running

There is no macOS build. Run on the robot itself, which ships Python 3.10:

```bash
scp aegis_devkit/wheels/ff_sdk-*-linux_aarch64.whl aegis_skills.py <user>@<robot-ip>:/tmp/
ssh <user>@<robot-ip>
python3 -m venv ~/ff_app/venv && ~/ff_app/venv/bin/pip install /tmp/ff_sdk-*.whl
cd /tmp
FF_SDK_DRY_RUN=1 ~/ff_app/venv/bin/python aegis_skills.py greet   # practice run
~/ff_app/venv/bin/python aegis_skills.py check                    # must print READY
```

Then `greet`, `square`, `nod_dance`. For a point-foot dog, set
`FF_SDK_AEGIS_VARIANT=footed` so the paw shake runs.

To dry-run on a Mac, use Docker:

```bash
docker run --rm --platform linux/arm64 -v "$PWD":/w -w /w -e FF_SDK_DRY_RUN=1 python:3.10-slim \
  sh -c 'pip install -q aegis_devkit/wheels/ff_sdk-*-linux_aarch64.whl && python aegis_skills.py greet'
```

## Safety

Keep 1 m of clear, flat floor on every side, and keep someone on the
emergency stop.
# aegis-skill
