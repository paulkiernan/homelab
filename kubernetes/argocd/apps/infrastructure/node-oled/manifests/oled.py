"""Cycle node identity and basic metrics on a 128x32 SSD1306 OLED.

Standard library only: talks to /dev/i2c-N with ioctls and renders text with a
built-in 5x7 font, so it runs on a stock python:alpine image.

Pages:
  1. node name and IP (double-height)
  2. CPU/temperature, memory, /var disk usage, uptime/load
"""

import fcntl
import os
import signal
import sys
import time

WIDTH, HEIGHT = 128, 32
PAGES = HEIGHT // 8
I2C_SLAVE = 0x0703

NODE_NAME = os.environ.get("NODE_NAME", os.uname().nodename)
NODE_IP = os.environ.get("NODE_IP", "?")
PAGE_SECONDS = float(os.environ.get("PAGE_SECONDS", "5"))
I2C_BUS = int(os.environ.get("I2C_BUS", "1"))
I2C_ADDR = int(os.environ.get("I2C_ADDR", "0x3c"), 0)
FLIP = os.environ.get("FLIP", "false").lower() == "true"
DISK_PATH = os.environ.get("DISK_PATH", "/host/var")

# Classic 5x7 font, ASCII 0x20-0x7e. Five column bytes per glyph, LSB = top row.
FONT = bytes.fromhex(
    "0000000000" "00005f0000" "0007000700" "147f147f14" "242a7f2a12"
    "2313086462" "3649552250" "0005030000" "001c224100" "0041221c00"
    "082a1c2a08" "08083e0808" "0050300000" "0808080808" "0060600000"
    "2010080402" "3e5149453e" "00427f4000" "4261514946" "2141454b31"
    "1814127f10" "2745454539" "3c4a494930" "0171090503" "3649494936"
    "064949291e" "0036360000" "0056360000" "0008142241" "1414141414"
    "4122140800" "0201510906" "324979413e" "7e1111117e" "7f49494936"
    "3e41414122" "7f4141221c" "7f49494941" "7f09090101" "3e41415132"
    "7f0808087f" "00417f4100" "2040413f01" "7f08142241" "7f40404040"
    "7f0204027f" "7f0408107f" "3e4141413e" "7f09090906" "3e4151215e"
    "7f09192946" "4649494931" "01017f0101" "3f4040403f" "1f2040201f"
    "7f2018207f" "6314081463" "0304780403" "6151494543" "00007f4141"
    "0204081020" "41417f0000" "0402010204" "4040404040" "0001020400"
    "2054545478" "7f48444438" "3844444420" "384444487f" "3854545418"
    "087e090102" "081454543c" "7f08040478" "00447d4000" "2040443d00"
    "007f102844" "00417f4000" "7c04180478" "7c08040478" "3844444438"
    "7c14141408" "081414187c" "7c08040408" "4854545420" "043f444020"
    "3c4040207c" "1c2040201c" "3c4030403c" "4428102844" "0c5050503c"
    "4464544c44" "0008364100" "00007f0000" "0041360800" "1008081008"
)


def glyph(ch):
    code = ord(ch)
    if not 0x20 <= code <= 0x7E:
        code = ord("?")
    i = (code - 0x20) * 5
    return FONT[i : i + 5]


class SSD1306:
    def __init__(self, bus, addr, flip):
        self.fd = os.open(f"/dev/i2c-{bus}", os.O_RDWR)
        fcntl.ioctl(self.fd, I2C_SLAVE, addr)
        seg, com = (0xA0, 0xC0) if flip else (0xA1, 0xC8)
        self.command(
            0xAE,             # display off
            0xD5, 0x80,       # clock divide
            0xA8, HEIGHT - 1, # multiplex
            0xD3, 0x00,       # display offset
            0x40,             # start line 0
            0x8D, 0x14,       # charge pump on
            0x20, 0x00,       # horizontal addressing
            seg, com,         # orientation
            0xDA, 0x02,       # COM pins for 128x32
            0x81, 0x8F,       # contrast
            0xD9, 0xF1,       # pre-charge
            0xDB, 0x40,       # VCOMH
            0xA4, 0xA6,       # resume from RAM, normal (not inverted)
            0xAF,             # display on
        )

    def command(self, *cmds):
        os.write(self.fd, bytes([0x00, *cmds]))

    def show(self, buf):
        self.command(0x21, 0, WIDTH - 1, 0x22, 0, PAGES - 1)
        for i in range(0, len(buf), 32):
            os.write(self.fd, b"\x40" + bytes(buf[i : i + 32]))

    def off(self):
        self.show(bytearray(WIDTH * PAGES))
        self.command(0xAE)


def draw_text(buf, page, text, center=False):
    """Draw one 8px-tall line of text into an 8-row page."""
    cols = b"".join(glyph(c) + b"\x00" for c in text)[: WIDTH]
    x0 = (WIDTH - len(cols)) // 2 if center else 0
    start = page * WIDTH + x0
    buf[start : start + len(cols)] = cols


def draw_tall_text(buf, page, text):
    """Draw centered text scaled 2x vertically, spanning `page` and `page + 1`."""
    cols = b"".join(glyph(c) + b"\x00" for c in text)[: WIDTH]
    x0 = (WIDTH - len(cols)) // 2
    for x, col in enumerate(cols):
        tall = 0
        for bit in range(8):
            if col >> bit & 1:
                tall |= 0b11 << (bit * 2)
        buf[page * WIDTH + x0 + x] = tall & 0xFF
        buf[(page + 1) * WIDTH + x0 + x] = tall >> 8


class Metrics:
    def __init__(self):
        self.prev_cpu = self._cpu_times()

    @staticmethod
    def _cpu_times():
        with open("/proc/stat") as f:
            fields = [int(v) for v in f.readline().split()[1:]]
        idle = fields[3] + fields[4]  # idle + iowait
        return idle, sum(fields)

    def cpu_percent(self):
        idle, total = self._cpu_times()
        d_idle, d_total = idle - self.prev_cpu[0], total - self.prev_cpu[1]
        self.prev_cpu = (idle, total)
        return 0.0 if d_total <= 0 else 100.0 * (1 - d_idle / d_total)

    @staticmethod
    def temp_c():
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                return int(f.read()) / 1000
        except OSError:
            return None

    @staticmethod
    def memory():
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, value = line.split(":", 1)
                info[key] = int(value.split()[0]) * 1024
        total = info["MemTotal"]
        return total - info["MemAvailable"], total

    @staticmethod
    def disk():
        try:
            st = os.statvfs(DISK_PATH)
        except OSError:
            return None
        total = st.f_blocks * st.f_frsize
        return total - st.f_bfree * st.f_frsize, total

    @staticmethod
    def uptime():
        with open("/proc/uptime") as f:
            secs = int(float(f.read().split()[0]))
        days, rem = divmod(secs, 86400)
        hours, rem = divmod(rem, 3600)
        return f"{days}d{hours}h" if days else f"{hours}h{rem // 60}m"

    @staticmethod
    def load1():
        with open("/proc/loadavg") as f:
            return f.read().split()[0]


def gib(n):
    return f"{n / 2**30:.1f}"


def identity_page():
    buf = bytearray(WIDTH * PAGES)
    draw_tall_text(buf, 0, NODE_NAME)
    draw_tall_text(buf, 2, NODE_IP)
    return buf


def metrics_page(m):
    buf = bytearray(WIDTH * PAGES)
    temp = m.temp_c()
    temp_s = f"{temp:.0f}C" if temp is not None else "--"
    used, total = m.memory()
    disk = m.disk()
    lines = [
        f"CPU {m.cpu_percent():3.0f}%   TEMP {temp_s}",
        f"MEM {gib(used)}/{gib(total)}G {100 * used / total:.0f}%",
        f"VAR {gib(disk[0])}/{gib(disk[1])}G {100 * disk[0] / disk[1]:.0f}%"
        if disk and disk[1]
        else "VAR --",
        f"UP {m.uptime():<8}LOAD {m.load1()}",
    ]
    for page, line in enumerate(lines):
        draw_text(buf, page, line)
    return buf


def open_display():
    path = f"/dev/i2c-{I2C_BUS}"
    while True:
        try:
            return SSD1306(I2C_BUS, I2C_ADDR, FLIP)
        except OSError as e:
            print(f"waiting for OLED on {path} addr {I2C_ADDR:#x}: {e}", flush=True)
            time.sleep(60)


def main():
    display = open_display()
    print(f"OLED ready on /dev/i2c-{I2C_BUS} addr {I2C_ADDR:#x}", flush=True)

    def stop(*_):
        try:
            display.off()
        finally:
            sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    metrics = Metrics()
    while True:
        try:
            display.show(identity_page())
            time.sleep(PAGE_SECONDS)
            # Refresh metrics every second while their page is up.
            for _ in range(max(1, int(PAGE_SECONDS))):
                display.show(metrics_page(metrics))
                time.sleep(1)
        except OSError as e:
            print(f"I2C error, reopening display: {e}", flush=True)
            time.sleep(5)
            display = open_display()


if __name__ == "__main__":
    main()
