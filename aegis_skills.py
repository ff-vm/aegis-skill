"""
Aegis robot-dog skill pack (FF SDK v0.1.0a10)

Written against https://api-docs.ff.com/aegis.html. Uses only calls the docs
mark as hardware-verified ("live"): stand, damping, stop, cmd_vel,
attitude_control, do_preset, battery, status, pose.

Run without a robot (dry-run):
    FF_SDK_DRY_RUN=1 python aegis_skills.py greet

There is no macOS build. From a Mac, run it on the robot itself (it ships
Python 3.10); see aegis_devkit/docs/deployment.md:
    scp aegis_devkit/wheels/ff_sdk-*-linux_aarch64.whl aegis_skills.py <user>@<robot-ip>:/tmp/
    ssh <user>@<robot-ip>
    python3 -m venv ~/ff_app/venv && ~/ff_app/venv/bin/pip install /tmp/ff_sdk-*.whl
    cd /tmp && FF_SDK_DRY_RUN=1 ~/ff_app/venv/bin/python aegis_skills.py greet

Run on hardware (on the robot, or Linux x86_64 on the robot hotspot):
    python aegis_skills.py check      # always first
    python aegis_skills.py greet
    python aegis_skills.py square --side 0.5
    python aegis_skills.py nod_dance

Safety: 1 m of clear, flat floor on every side, a person on the e-stop,
and every skill ends in damping().
"""

import argparse
import asyncio
import os
import sys

import ff_sdk
from ff_sdk.capabilities.types import RobotStatus
from ff_sdk.core.exceptions import CapabilityNotSupported
from ff_sdk.platforms.base import HealthStatus

TARGET = os.environ.get("AEGIS_TARGET", "aegis://DEMO")
DRY_RUN = os.environ.get("FF_SDK_DRY_RUN") == "1"


# ---------------------------------------------------------------- helpers

async def hold_velocity(dog, seconds, linear=0.0, angular=0.0, lateral=0.0, hz=20):
    """cmd_vel is a velocity, not a distance: resend it at 10-50 Hz, then stop."""
    steps = int(seconds * hz)
    for _ in range(steps):
        await dog.motion.cmd_vel(linear=linear, angular=angular, lateral=lateral)
        await asyncio.sleep(1 / hz)
    await dog.motion.stop()


async def hold_attitude(dog, seconds, hz=20, **vel):
    """attitude_control is a velocity too: the dog keeps the last frame, so resend it."""
    for _ in range(max(1, int(seconds * hz))):
        await dog.motion.attitude_control(**vel)
        await asyncio.sleep(1 / hz)


async def stand_up(dog, extra_s=4.0):
    """stand() returns immediately; wait for the measured stand time (~4 s).

    The robot can accept stand() and then not stand (seen on a wheeled unit
    with "sdk is dismatch"), so confirm STANDING via status() and raise if
    not, rather than sending moves the dog will reject or silently ignore.
    """
    res = await dog.motion.stand()
    print("stand:", res.message or "ok")
    await asyncio.sleep(dog.motion.preset_timeout("stand"))
    if DRY_RUN:
        return
    status = None
    for _ in range(int(extra_s / 0.5)):
        status = await dog.state.status()
        if status is RobotStatus.STANDING:
            return
        await asyncio.sleep(0.5)
    raise RuntimeError(f"dog did not stand (status {status}); "
                       "power-cycle the robot and run check again")


async def wait_settled(dog, floor_s, extra_s=10.0):
    """Sleep the suggested time as a floor, then confirm via status()."""
    await asyncio.sleep(floor_s)
    for _ in range(int(extra_s / 0.5)):
        if await dog.state.status() in (RobotStatus.STANDING, RobotStatus.IDLE):
            return True
        await asyncio.sleep(0.5)
    return False


def native_link_ok(dog) -> bool:
    """Docs: if only the fallback link is up, commands can silently do nothing.

    summary() prints statuses as ✓/⚠/✗ marks, not words, so read the
    "aegis SDK" check itself. A missing check counts as down.
    """
    report = dog.diagnose()
    print(report.summary())
    if DRY_RUN:
        return True
    native = [c for c in report.checks if c.name.startswith("aegis SDK")]
    return bool(native) and all(c.status is HealthStatus.OK for c in native)


# ---------------------------------------------------------------- skills

async def skill_check(dog):
    """Health check + battery. Run this before every hardware session."""
    ok = native_link_ok(dog)
    print("capabilities:", sorted(dog.capabilities()))
    batt = await dog.state.battery()
    print(f"battery: {batt.percent:.0%}")
    print("status:", await dog.state.status())
    print("pose:", await dog.state.pose())
    if DRY_RUN:
        print("DRY RUN - link check skipped")
    else:
        print("READY" if ok else "NOT READY - native link down, fix before moving")


async def skill_greet(dog):
    """Stand, nod hello, offer a paw (footed chassis), lie down."""
    await stand_up(dog)

    # nod twice using in-place attitude (velocity, clamped to ±0.5)
    for _ in range(2):
        await hold_attitude(dog, 0.6, pitch_vel=-0.3)
        await hold_attitude(dog, 0.6, pitch_vel=0.3)
    await dog.motion.attitude_control()  # neutral

    # known_presets() still lists shake_hand when the chassis isn't known yet
    try:
        await dog.motion.do_preset("shake_hand")  # measured ~10 s
        await wait_settled(dog, dog.motion.preset_timeout("shake_hand"))
    except CapabilityNotSupported:
        print("shake_hand: footed chassis only, skipped on this wheeled dog (not an error)")

    await dog.motion.do_preset("lie_down")
    await asyncio.sleep(dog.motion.preset_timeout("lie_down"))


async def skill_square(dog, side=0.5, speed=0.25):
    """Walk an approximate square (open-loop timing, not odometry)."""
    await stand_up(dog)
    start = await dog.state.pose()
    for _ in range(4):
        await hold_velocity(dog, side / speed, linear=speed)
        await asyncio.sleep(0.5)
        await hold_velocity(dog, (3.1416 / 2) / 0.6, angular=0.6)  # ~90° left
        await asyncio.sleep(0.5)
    end = await dog.state.pose()
    print(f"start {start}\nend   {end}  (drift shows how open-loop timing behaves)")


async def skill_nod_dance(dog, beats=8, bpm=100):
    """Rhythmic in-place dance: nod / sway / bounce on a beat."""
    await stand_up(dog)
    beat = 60 / bpm
    moves = [
        dict(pitch_vel=-0.3), dict(pitch_vel=0.3),
        dict(yaw_vel=0.3), dict(yaw_vel=-0.3),
        dict(roll_vel=0.4), dict(roll_vel=-0.4),
        dict(height_vel=-0.2), dict(height_vel=0.2),
    ]
    res = await dog.motion.attitude_control()
    print("attitude backend:", res.details.get("backend"))
    for i in range(beats):
        await hold_attitude(dog, beat, **moves[i % len(moves)])
    await dog.motion.attitude_control()


SKILLS = {
    "check": skill_check,
    "greet": skill_greet,
    "square": skill_square,
    "nod_dance": skill_nod_dance,
}


# ---------------------------------------------------------------- runner

async def main():
    p = argparse.ArgumentParser()
    p.add_argument("skill", choices=SKILLS)
    p.add_argument("--side", type=float, default=0.5, help="square side, metres")
    args = p.parse_args()

    dog = await ff_sdk.connect(TARGET)
    try:
        if args.skill != "check" and not native_link_ok(dog):
            print("Refusing to move: native control link is not up.")
            return 2
        kwargs = {"side": args.side} if args.skill == "square" else {}
        await SKILLS[args.skill](dog, **kwargs)
    except Exception as e:
        print(f"error: {e!r} - emergency stop")
        await dog.e_stop(str(e))
        raise
    finally:
        if args.skill != "check":
            try:
                await dog.motion.damping()  # always end limp
            except Exception:
                pass
        await dog.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
