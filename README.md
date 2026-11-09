# SP400_Sim

Firmware simulator for the SP 400 instrument. It lets you develop and test
host software without the hardware.

> **Status:** The command set, parameters and sensors are **placeholders**.
> They follow a generic SCPI style and are not the real SP 400 protocol yet.
> Edit `src/sp400_sim/profiles/default.json` and `src/sp400_sim/protocol.py`
> to match the actual instrument.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
sp400-sim                      # interactive console (stdin/stdout)
sp400-sim --tcp 5025           # TCP server on 127.0.0.1:5025
sp400-sim --pty                # virtual serial port, prints /dev/pts/N
sp400-sim --pty --link /tmp/sp400   # also symlink it to a fixed path
sp400-sim --profile my.json --seed 1   # custom profile, reproducible noise
```

Talk to it over TCP with `nc localhost 5025`, or over the virtual serial port
with pyserial: `serial.Serial("/tmp/sp400", 9600)`.

## Commands (placeholder)

Commands are case-insensitive and newline-terminated. Errors reply with
`ERR <code>` and go into the error queue (read it with `ERR?`).

| Command | Reply | Description |
|---|---|---|
| `*IDN?` | `mfr,model,serial,fw` | Identity |
| `*RST` | `OK` | Reset to defaults, go IDLE |
| `*CLS` | `OK` | Clear fault and error queue |
| `START` / `STOP` | `OK` | Start/stop acquisition |
| `STAT?` | `IDLE` / `RUNNING` / `ERROR` | Device state |
| `SET <param> <value>` | `OK` | Set a parameter (range-checked) |
| `GET <param>` | value | Read a parameter |
| `MEAS? [sensor]` | value, or `NAME=val,...` | Read one or all sensors |
| `ERR?` | `code,"message"` | Pop the oldest error |
| `SIM:FAULT [reason]` | `OK` | Simulator only: force the ERROR state |
| `HELP` | command list | |

Error codes: `-100` unknown command, `-101` bad parameter/arguments,
`-102` out of range, `-200` wrong state, `-300` fault.

## Customising for the real SP 400

- **Parameters and sensors:** edit the JSON profile. Sensors support
  `base`, `noise` (Gaussian std dev), `scale_by` (multiply by a parameter) and
  `track` + `tau_s` (first-order approach toward a parameter, e.g. a
  temperature setpoint).
- **Commands:** register handlers on `CommandProcessor`:

  ```python
  proc.register("ZERO", lambda dev, args: "OK")
  ```

- **Line terminator:** set `line_terminator` in the profile (for example `"\r\n"`).

## Layout

```
src/sp400_sim/
  device.py       state machine, parameters, sensors, error queue
  protocol.py     command parser and command set
  profile.py      profile loading and validation
  profiles/       bundled default profile
  transports/     TCP server and virtual serial port (pty)
  cli.py          sp400-sim entry point
tests/
```

## Test

```bash
pytest
```
