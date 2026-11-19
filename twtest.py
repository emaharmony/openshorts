import urllib.request
h = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
r = urllib.request.urlopen('https://www.twitch.tv/videos/2901089887', timeout=30)
body = r.read().decode('utf-8', 'replace')
print('HTTP', r.status, 'len', len(body))
i = body.find('2901089887')
print(body[max(0, i-300):i+300] if i > 0 else 'id not mentioned')