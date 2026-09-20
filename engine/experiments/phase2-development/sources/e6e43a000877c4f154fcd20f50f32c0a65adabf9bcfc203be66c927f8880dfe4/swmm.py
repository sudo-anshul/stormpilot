"""Small standard-library ctypes binding to the pinned EPA SWMM public API."""
import ctypes as C
from pathlib import Path
from build import build


class Simulation:
    def __init__(self, model, report, output):
        self.lib = C.CDLL(str(build()))
        for name, args, result in [
            ("swmm_open", [C.c_char_p] * 3, C.c_int),
            ("swmm_start", [C.c_int], C.c_int),
            ("swmm_step", [C.POINTER(C.c_double)], C.c_int),
            ("swmm_getCount", [C.c_int], C.c_int),
            ("swmm_getIndex", [C.c_int, C.c_char_p], C.c_int),
            ("swmm_getName", [C.c_int, C.c_int, C.c_char_p, C.c_int], None),
            ("swmm_getValue", [C.c_int, C.c_int], C.c_double),
            ("swmm_setValue", [C.c_int, C.c_int, C.c_double], None),
            ("swmm_getError", [C.c_char_p, C.c_int], C.c_int),
            ("swmm_getMassBalErr", [C.POINTER(C.c_float)] * 3, C.c_int),
            ("stormpilot_time_seconds", [], C.c_double),
            ("stormpilot_duration_seconds", [], C.c_double),
            ("stormpilot_node_flood_volume_m3", [C.c_int], C.c_double),
            ("stormpilot_node_overflow_m3s", [C.c_int], C.c_double),
            ("stormpilot_node_volume_m3", [C.c_int], C.c_double),
            ("stormpilot_link_flow_m3s", [C.c_int], C.c_double),
            ("stormpilot_link_volume_m3", [C.c_int], C.c_double),
            ("stormpilot_init_instrumentation", [], None),
            ("stormpilot_set_max_step_s", [C.c_double], None),
        ]:
            fn = getattr(self.lib, name)
            fn.argtypes, fn.restype = args, result
        self.started = False
        self.opened = False
        self.check(self.lib.swmm_open(*(str(p).encode() for p in (model, report, output))))
        self.opened = True
        self.check(self.lib.swmm_start(0))
        self.started = True
        self.lib.stormpilot_init_instrumentation()
        self.nodes = self.names(2)
        self.links = self.names(3)
        self.duration_s = self.lib.stormpilot_duration_seconds()

    def check(self, code):
        if code:
            message = C.create_string_buffer(1024)
            self.lib.swmm_getError(message, len(message))
            raise RuntimeError(f"EPA SWMM error {code}: {message.value.decode(errors='replace')}")

    def names(self, kind):
        result = {}
        for index in range(self.lib.swmm_getCount(kind)):
            name = C.create_string_buffer(256)
            self.lib.swmm_getName(kind, index, name, len(name))
            result[name.value.decode()] = index
        return result

    def get(self, prop, index=0):
        return self.lib.swmm_getValue(prop, index)

    def set(self, prop, index, value):
        self.lib.swmm_setValue(prop, index, value)

    @property
    def time_s(self):
        return self.lib.stormpilot_time_seconds()

    def step(self):
        elapsed = C.c_double()
        self.check(self.lib.swmm_step(C.byref(elapsed)))
        return elapsed.value > 0

    def native_flood_volumes(self):
        return {name: self.lib.stormpilot_node_flood_volume_m3(index)
                for name, index in self.nodes.items()}

    def finish(self):
        if self.started:
            self.check(self.lib.swmm_end())
            self.started = False
        values = [C.c_float() for _ in range(3)]
        self.check(self.lib.swmm_getMassBalErr(*(C.byref(v) for v in values)))
        continuity = {"runoff_error_pct": values[0].value, "routing_error_pct": values[1].value,
                      "quality_error_pct": values[2].value}
        self.lib.swmm_close()
        self.opened = False
        return continuity

    def close(self):
        if self.started:
            self.lib.swmm_end()
            self.started = False
        if self.opened:
            self.lib.swmm_close()
            self.opened = False
