import os
for j in sorted(os.listdir('/app/output')):
    if j == 'thumbnails':
        continue
    p = os.path.join('/app/output', j)
    if not os.path.isdir(p):
        continue
    fs = sorted(os.listdir(p))
    print(j, len(fs), fs[:8])