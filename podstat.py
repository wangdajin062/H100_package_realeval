import urllib.request, json
BASE='https://mhypfkvge474n8-8888.proxy.runpod.net'
TOKEN='uv9gowwjyzzqerlwfg58'
H={'User-Agent':'runpod-sync/1.0','Referer':BASE+'/lab'}
def api(p, raw=False):
    q = '?content=1&format=text&token=' if raw else '?token='
    u = BASE + '/api/contents' + p + q + TOKEN
    return json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=15).read())

# Read experiments.log tail
try:
    r = api('/workspace/H100_package_realeval/outputs/logs/experiments.log', raw=True)
    lines = r.get('content','').strip().split('\n')
    print(f'=== experiments.log (last 15 of {len(lines)} lines) ===')
    for l in lines[-15:]:
        print(l[:150])
except Exception as e:
    print(f'log error: {e}')