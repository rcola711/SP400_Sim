# SP400 Firmware Board Simulator — Plan

Status: draft, waiting on hardware/protocol documentation.

## Goal

Replace the SP400 firmware board (and every sensor/motor behind it) with a PC.
Plug a cable from the PC into the base PCB, boot the Apalis iMX8, and have the
instrument software run normally — homing, moves, measurements, errors —
without knowing it is talking to a simulator.

## System as understood

```
 Real instrument                         Simulated
 ───────────────                         ─────────
 [Apalis iMX8 + base PCB]                [Apalis iMX8 + base PCB]   (unchanged)
   Toradex embedded Linux                  same image, same app
   instrument application                  same app
   M.2 SSD (database)                      same SSD
        │ Ethernet ("serial")                    │ Ethernet cable
        ▼                                        ▼
 [Firmware board]                        [PC running sp400-sim]
   motors, sensors, I/O                    firmware protocol + hardware models
```

The Apalis side is not modified. The simulator only has to look exactly like
the firmware board on the wire.

## What the simulator must match

1. **Network identity** — the IP address, port, and transport (TCP/UDP) the
   Apalis expects for the firmware board, plus who opens the connection.
   The PC takes over that IP (static address on its Ethernet adapter).
2. **Protocol** — framing, encoding (ASCII or binary), checksums/CRC,
   command set, replies, unsolicited messages (move done, limit hit, alarms),
   heartbeat/watchdog, startup handshake (version check, serial number).
3. **Behaviour and timing** — moves take realistic time, sensors change
   realistically, homing finds switches, timeouts in the Apalis app are not
   tripped.
4. **Anything else the Apalis expects from the firmware board** — e.g.
   firmware-update path, discovery broadcasts, time sync. To be confirmed.

## Architecture changes from the current scaffold

The current code is a synchronous request/reply loop with placeholder SCPI
commands. It will be restructured into:

| Layer | Purpose |
|---|---|
| `net/` | TCP/UDP server or client matching the real board; raw byte logging |
| `codec/` | Framing + encode/decode of the real protocol (pluggable) |
| `firmware/` | Command dispatch, state machine, handshake, heartbeat, error codes — mirrors the real firmware's logic |
| `hw/` | Hardware models: stepper/servo motors (accel, velocity, position, encoder, home/limit switches), analog sensors, digital I/O, heaters (thermal model), pumps/valves — configured per instrument in a profile |
| `sim/` | Simulation clock (real-time or accelerated), tick loop, event bus for unsolicited messages |
| `control/` | Separate side-channel (HTTP or 2nd port) to inject faults, force sensor values, jam a motor, drop the link — kept out of the instrument protocol |
| `record/` | Timestamped log of every frame both ways; replay of captured traffic for regression tests |

Core becomes asyncio-based so motors move and events fire independently of
incoming commands.

## Phases

**0. Discovery (now)**
- Collect firmware board protocol docs, schematics for the Ethernet link,
  list of all motors/sensors/I/O with ranges and units.
- Capture real traffic between Apalis and firmware board (see "Capture"
  below). This is the most reliable source of truth, docs or not.

**1. Network bring-up + listen mode**
- `sp400-sim --listen`: take the firmware board's IP/port, accept the
  Apalis connection, log every byte, reply nothing (or a fixed reply).
- `sp400-sim --proxy`: sit between a real Apalis and real firmware board
  (PC with two Ethernet ports) and log both directions. Produces captures for
  later phases.
- Deliverable: Apalis connects to the PC; we see its first messages.

**2. Protocol codec + handshake**
- Implement framing/checksum from docs/captures.
- Implement the startup sequence so the Apalis app reports the firmware board
  as connected and healthy.
- Deliverable: instrument app boots to its idle screen against the simulator.

**3. Hardware models**
- Motor model (trapezoidal profile, limits, homing, stall), sensor models
  (noise, drift, first-order response), digital I/O, thermal model.
- Instrument profile listing every device with real parameters.
- Deliverable: homing and basic moves complete with correct timing.

**4. Full command coverage**
- Every command in the protocol, every unsolicited event, every error code.
- Deliverable: a full instrument run (start to finish) completes.

**5. Faults and scenarios**
- Control API + scripted scenarios (e.g. "motor 2 stalls at step 4000",
  "temperature sensor open-circuit", "link drops for 3 s").
- Deliverable: error handling in the Apalis app can be tested on demand.

**6. Validation**
- Replay real captures against the simulator and diff the replies.
- Optional: live dashboard showing motor positions, sensor values, traffic.

## Capture (do this as early as possible)

Options, easiest first:
1. On the Apalis (root shell over SSH/serial console):
   `tcpdump -i <iface> -w /tmp/fw.pcap host <firmware-board-ip>` while running
   a normal instrument cycle. Copy the pcap off and send it.
2. A managed switch with port mirroring between Apalis and firmware board,
   Wireshark on the PC.
3. Phase 1 proxy mode on a PC with two Ethernet adapters.

A capture of: power-on → idle → homing → one full run → one error → shutdown
covers most of what is needed.

## Open questions

1. **Link details:** firmware board IP and port? TCP or UDP? Does the Apalis
   connect to the board, or the other way round? Is "Ethernet serial port" a
   serial protocol tunnelled over TCP (e.g. a serial-to-Ethernet device server
   on the firmware board), or a native Ethernet protocol?
2. **Protocol docs:** is there an interface control document (ICD) or
   command reference for the firmware board?
3. **Source code:** do you have source for the Apalis application and/or the
   firmware board firmware? Either makes the protocol unambiguous.
4. **Device list:** all motors (type, steps/rev, travel, speed, home/limit
   switches, encoders), sensors (type, range, units), heaters, pumps, valves,
   digital I/O.
5. **Other traffic:** does the Apalis talk to anything else on that link
   (second board, update server, NTP, DHCP)? Does the board get its IP from
   DHCP or static?
6. **Root access:** can you get a shell on the Apalis (for tcpdump and
   checking its network config)?
7. **PC OS:** Windows, Linux, or macOS? Affects network setup instructions
   and whether the virtual serial port (pty) transport is relevant.
8. **Timing sensitivity:** known timeouts in the Apalis app (heartbeat
   interval, reply timeout)?

## Risks

- **Undocumented protocol details** (checksums, sequence numbers, timing)
  cause the Apalis app to reject the simulator silently. Mitigated by captures.
- **Hidden dependencies** — the Apalis may check something beyond the main
  link (firmware version, board serial, a GPIO/power-good line on the base
  PCB that the firmware board normally drives). A missing hardware signal
  cannot be simulated over Ethernet; check the base PCB schematic.
- **Real-time behaviour** — if the app expects tight timing, Python asyncio is
  usually adequate at millisecond scale; sub-millisecond would need a
  different approach.
