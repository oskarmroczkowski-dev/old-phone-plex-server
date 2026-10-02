# One-off CPU load measurement on the phone (read-only), same method as in status-server.py.
# Run on the phone (e.g. `ssh -p 8022 <phone> python - < cpu_once.py`); prints the load in percent over 8 s.
import glob
import time

D = '/sys/devices/system/cpu'


def num(p):
    with open(p) as f:
        return int(f.read())


def snap():
    s = {}
    for c in glob.glob(D + '/cpu[0-9]*'):
        idle = usage = 0
        for st in glob.glob(c + '/cpuidle/state*'):
            try:
                idle += num(st + '/time'); usage += num(st + '/usage')
            except (OSError, ValueError):
                pass
        try:
            at_min = num(c + '/cpufreq/scaling_cur_freq') <= num(c + '/cpufreq/cpuinfo_min_freq')
        except (OSError, ValueError):
            at_min = True
        s[c] = (idle, usage, at_min)
    return s


a = snap(); t0 = time.monotonic()
time.sleep(8)
b = snap(); dt = (time.monotonic() - t0) * 1e6
loads = []
for k, (idle, usage, at_min) in b.items():
    di, du = idle - a[k][0], usage - a[k][1]
    loads.append((0.0 if at_min else 1.0) if di == 0 and du == 0 else 1 - min(1.0, di / dt))
print(round(100 * sum(loads) / len(loads)))
