import pytest

from sp400_sim import CommandProcessor, Device, DeviceState, load_profile
from sp400_sim.device import E_BAD_STATE, E_OUT_OF_RANGE, E_UNKNOWN_CMD


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def proc(clock):
    return CommandProcessor(Device(load_profile(), clock=clock, seed=1))


def test_idn(proc):
    assert proc.handle("*IDN?") == "PLACEHOLDER,SP400,SIM0001,0.1.0-sim"


def test_commands_are_case_insensitive(proc):
    assert proc.handle("stat?") == "IDLE"


def test_blank_line_returns_nothing(proc):
    assert proc.handle("   ") is None


def test_start_stop(proc):
    assert proc.handle("START") == "OK"
    assert proc.handle("STAT?") == "RUNNING"
    assert proc.handle("START") == f"ERR {E_BAD_STATE}"
    assert proc.handle("STOP") == "OK"
    assert proc.handle("STAT?") == "IDLE"


def test_set_get_and_range_check(proc):
    assert proc.handle("SET GAIN 2.5") == "OK"
    assert proc.handle("GET gain") == "2.5"
    assert proc.handle("SET GAIN 1000") == f"ERR {E_OUT_OF_RANGE}"
    assert proc.handle("GET GAIN") == "2.5"


def test_unknown_command_goes_to_error_queue(proc):
    assert proc.handle("FOO") == f"ERR {E_UNKNOWN_CMD}"
    assert proc.handle("ERR?").startswith(f"{E_UNKNOWN_CMD},")
    assert proc.handle("ERR?") == '0,"No error"'


def test_gain_scales_signal(proc):
    proc.handle("SET GAIN 10")
    value = float(proc.handle("MEAS? SIGNAL"))
    assert 9.5 < value < 10.5


def test_temperature_tracks_setpoint(proc, clock):
    proc.handle("SET SETPOINT 100")
    t0 = float(proc.handle("MEAS? TEMPERATURE"))
    assert abs(t0 - 25.0) < 1.0
    clock.t = 300.0  # 10 time constants later
    t1 = float(proc.handle("MEAS? TEMPERATURE"))
    assert abs(t1 - 100.0) < 1.0


def test_measure_all(proc):
    reply = proc.handle("MEAS?")
    keys = {kv.split("=")[0] for kv in reply.split(",")}
    assert keys == {"SIGNAL", "TEMPERATURE"}


def test_fault_injection_and_clear(proc):
    assert proc.handle("SIM:FAULT overheat") == "OK"
    assert proc.handle("STAT?") == "ERROR"
    assert proc.handle("MEAS? SIGNAL") == f"ERR {E_BAD_STATE}"
    assert proc.handle("START") == f"ERR {E_BAD_STATE}"
    assert proc.handle("*CLS") == "OK"
    assert proc.handle("STAT?") == "IDLE"


def test_reset_restores_defaults(proc):
    proc.handle("SET CHANNEL 3")
    proc.handle("START")
    proc.handle("*RST")
    assert proc.handle("GET CHANNEL") == "1"
    assert proc.device.state is DeviceState.IDLE


def test_seed_makes_noise_reproducible(clock):
    a = Device(load_profile(), clock=clock, seed=42).read_sensor("SIGNAL")
    b = Device(load_profile(), clock=clock, seed=42).read_sensor("SIGNAL")
    assert a == b
