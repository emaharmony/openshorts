import subprocess, os
os.makedirs('/app/output/.vverify', exist_ok=True)
for t in (477, 482, 484.35, 488, 490):
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(t),'-i','/tmp/windwaker_src.mp4','-frames:v','1','-y','/app/output/.vverify/z%s.jpg' % int(t*10)], check=True)
print('ok')