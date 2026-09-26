from __future__ import annotations

import fap_v87_27_physics_knowledge_gateway as v27
import fap_v87_28_physics_solver_gateway as gateway


def ask(question: str):
    return gateway.CORE.chat(question, "v8728-test")


def test_newton_second_law():
    out = ask("""Answer the following multiple choice question.
A body has mass = 4 kg and acceleration = 3 m/s^2. What net force acts on it?

A) 7 N
B) 12 N
C) 16 N
D) 24 N
""")
    assert out["structured_mcq"]["physics_deterministic"]["solver"] == "newton_second_law"
    assert out["reply"].splitlines()[-1] == "Answer: $B"


def test_momentum():
    out = ask("""Answer the following multiple choice question.
An object has mass = 5 kg and velocity = 4 m/s. What is its momentum?

A) 9 kg m/s
B) 15 kg m/s
C) 20 kg m/s
D) 25 kg m/s
""")
    assert out["reply"].splitlines()[-1] == "Answer: $C"


def test_gravitational_potential_energy():
    out = ask("""Answer the following multiple choice question.
A mass = 2 kg is raised to height = 5 m. What is its gravitational potential energy near Earth?

A) 9.8 J
B) 49 J
C) 98 J
D) 196 J
""")
    assert out["reply"].splitlines()[-1] == "Answer: $C"


def test_wave_speed():
    out = ask("""Answer the following multiple choice question.
A wave has frequency = 20 Hz and wavelength = 3 m. What is its wave speed?

A) 6 m/s
B) 17 m/s
C) 23 m/s
D) 60 m/s
""")
    assert out["reply"].splitlines()[-1] == "Answer: $D"


def test_ideal_gas_pressure():
    out = ask("""Answer the following multiple choice question.
An ideal gas has n = 1 mol, temperature = 300 K, and volume = 0.0249434 m^3. What is its pressure?

A) 1000 Pa
B) 10000 Pa
C) 100000 Pa
D) 1000000 Pa
""")
    assert out["reply"].splitlines()[-1] == "Answer: $C"


def test_wien_law():
    out = ask("""Answer the following multiple choice question.
A blackbody has temperature = 5800 K. Approximately what is its peak wavelength according to Wien's law?

A) 0.050 um
B) 0.500 um
C) 5.00 um
D) 50.0 um
""")
    assert out["reply"].splitlines()[-1] == "Answer: $B"


def test_half_life():
    out = ask("""Answer the following multiple choice question.
A radioactive sample has half-life = 2 hours. What percentage remains after 6 hours?

A) 6.25 %
B) 12.5 %
C) 25 %
D) 50 %
""")
    assert out["reply"].splitlines()[-1] == "Answer: $B"


def test_ohms_law():
    out = ask("""Answer the following multiple choice question.
A resistor has resistance = 10 ohm and current = 2 A. What voltage is across it by Ohm's law?

A) 5 V
B) 10 V
C) 20 V
D) 40 V
""")
    assert out["reply"].splitlines()[-1] == "Answer: $C"


def test_unresolved_delegates_to_v8727(monkeypatch):
    sentinel = {"reply":"legacy-v27","ability":"structured_mcq"}
    def old(self, text, sid):
        return sentinel
    monkeypatch.setattr(v27.FAPV8727, "chat", old)
    core = gateway.FAPV8728()
    out = core.chat("""Answer the following multiple choice question.
Which highly specialized unknown proposition is correct?

A) alpha
B) beta
C) gamma
D) delta
""", "x")
    assert out is sentinel


def test_non_mcq_delegates_to_v8727(monkeypatch):
    sentinel = {"reply":"legacy-chat","ability":"chat"}
    def old(self, text, sid):
        return sentinel
    monkeypatch.setattr(v27.FAPV8727, "chat", old)
    core = gateway.FAPV8728()
    assert core.chat("こんにちは", "x") is sentinel
