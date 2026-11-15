import os,json,urllib.request
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:18231'; API='http://127.0.0.1:19231'
OUT='/workspace/test-artifacts/gb-0027'

def call(method,path,token=None,body=None):
    req=urllib.request.Request(API+path,method=method,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    data=json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req,data=data) as r:return r.status,json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:return e.code,json.loads(e.read() or b'{}')
def login_api(email):
    s,b=call('POST','/auth/login',body={'email':email,'password':'Qingnie2026!'});assert s==200,b;return b['token']

admin=login_api('admin@qingnie.local'); analyst=login_api('analyst@qingnie.local'); viewer=login_api('viewer@qingnie.local')
s,runs=call('GET','/runs',viewer); print('runs',[(r['id'],r['status'],r['quality']['basis_status'],len(r['exclusions'])) for r in runs])
valid=[r for r in runs if r['quality']['basis_status']=='current'][0]
invalid=[r for r in runs if r['quality']['basis_status']=='invalidated'][0]

# create and approve a note on the valid run, and one on the invalid run via direct DB-free API should fail
s,n=call('POST','/notes',analyst,{'name':'通告后复检说明','run_id':valid['id'],'rationale':'公告后新建的说明：讨论排除清单与剩余组对。'})
print('note create',s)
if s==201:
    s2,_=call('POST',f"/notes/{n['id']}/review",admin,{'status':'approved','reviewer_note':'同意基于新检验安排独立盲评复检。'})
    print('note approve',s2)

def ui_login(page,email):
    page.goto(BASE+'/#/login');page.fill('input[type=email]',email);page.fill('input[type=password]','Qingnie2026!');page.click('button.primary');page.wait_for_selector('.masthead')

with sync_playwright() as p:
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errs=[]
    page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    ui_login(page,'viewer@qingnie.local')
    # Results page: valid run
    page.goto(BASE+'/#/results');page.wait_for_selector('.result-byline')
    page.evaluate("localStorage.setItem('ordinal-run','%d')"%valid['id']);page.reload();page.wait_for_selector('.result-byline')
    page.screenshot(path=OUT+'/04-results-valid.png',full_page=True)
    # Results page: invalidated run
    page.evaluate("localStorage.setItem('ordinal-run','%d')"%invalid['id']);page.reload();page.wait_for_timeout(700)
    page.screenshot(path=OUT+'/05-results-invalidated.png',full_page=True)
    # Notes page viewer
    page.goto(BASE+'/#/notes');page.wait_for_timeout(900)
    page.screenshot(path=OUT+'/06-notes.png',full_page=True)
    # Runs page admin
    ui_login(page,'admin@qingnie.local');page.goto(BASE+'/#/runs');page.wait_for_selector('.run-form');page.wait_for_timeout(700)
    page.screenshot(path=OUT+'/07-runs.png',full_page=True)
    # Data page final layout
    page.goto(BASE+'/#/data');page.wait_for_selector('.notice-spread');page.wait_for_timeout(500)
    page.screenshot(path=OUT+'/08-data-final.png',full_page=True)
    b.close()
print('console errors',errs[:5]);print('done')
