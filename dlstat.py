import os, glob
fs = glob.glob('/app/output/.vverify/*')
for f in sorted(fs):
    print(os.path.basename(f), os.path.getsize(f) if os.path.isfile(f) else '<dir>')
log = '/app/output/.vverify/dl.log'
if os.path.exists(log):
    with open(log) as f:
        t = f.read()
    print('--- dl.log tail:')
    print(t[-600:])