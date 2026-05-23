# flashbot
flash bot repo

Showcased: Highlight Delft 2026 & MakerFaire Delft 2026

# Arduino ↔ ROS2 Serial Protocol

## Overview

The Raspberry Pi runs the main ROS2 behavior FSM. The Arduino acts as a low-level hardware interface for motors, wings, lights, hall sensors, and limit switches.

Communication happens over USB serial using newline-terminated ASCII messages.

Each message follows this format:

```text
<TYPE>,<NAME>[,<ARG1>,<ARG2>,...]\n
