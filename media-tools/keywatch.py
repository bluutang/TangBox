import struct, time, select
DEV = "/dev/input/event1"
FMT = "llHHi"; SZ = struct.calcsize(FMT)
print("START %s - listening 300s" % time.strftime("%H:%M:%S"), flush=True)
start = time.time(); last = None; n = 0
with open(DEV, "rb") as f:
    while time.time() - start < 300:
        r, _, _ = select.select([f], [], [], 0.5)
        if not r:
            continue
        d = f.read(SZ)
        if not d or len(d) < SZ:
            continue
        sec, usec, et, code, val = struct.unpack(FMT, d)
        if et != 1 or val != 1:
            continue
        t = sec + usec / 1e6; n += 1
        gap = ("%7.0f ms gap" % ((t - last) * 1000)) if last else "      first"
        print("  press %3d  code %3d  %s" % (n, code, gap), flush=True)
        last = t
print("END - %d presses seen by the kernel" % n, flush=True)
