import os,json,time,threading
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:18231'; API='http://127.0.0.1:19231'
OUT='/workspace/test-artifacts/gb-0027'
os.makedirs(OUT,exist_ok=True)
LD=os.environ.get('LD_LIBRARY_PATH','')

import urllib.request

def call(method,path,token=None,body=None):
    req=urllib.request.Request(API+path,method=method,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    data=json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req,data=data) as r:return r.status,json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read() or b'{}')

def login_api(email):
    s,b=call('POST','/auth/login',body={'email':email,'password':'Qingnie2026!'})
    assert s==200,b
    return b['token']

admin=login_api('admin@qingnie.local'); analyst=login_api('analyst@qingnie.local'); viewer=login_api('viewer@qingnie.local')

def login(page,email):
    page.goto(BASE+'/#/login')
    page.fill('input[type=email]',email); page.fill('input[type=password]','Qingnie2026!')
    page.click('button.primary'); page.wait_for_selector('.masthead')

with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={'width':1440,'height':1000})
    page=ctx.new_page(); errs=[]
    page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    login(page,'admin@qingnie.local')

    # --- Data page with existing notices
    page.goto(BASE+'/#/data'); page.wait_for_selector('.notice-spread')
    page.screenshot(path=OUT+'/01-data-notices.png',full_page=True)

    # Issue a second overlapping notice via UI on same specimen
    page.click('summary:has-text("按试样清单发布通告")')
    page.fill('input[name=title]','重叠通告 · 复检未结')
    page.fill('textarea[name=codes]','QN-SHIFT-T1-004')
    page.fill('textarea[name=reason]','同一试样的第二份重叠通告，复检尚未闭合。')
    page.click('button:has-text("发布通告并停用受影响依据")')
    page.wait_for_selector('.success:has-text("质量通告已发布")')
    page.screenshot(path=OUT+'/02-data-overlap.png',full_page=True)

    # --- Runs page: create a run after notice via UI
    page.goto(BASE+'/#/runs'); page.wait_for_selector('.run-form')
    page.fill('input', '演示 · 通告后冻结') if False else None
    page.fill('input[required][maxlength="140"]','演示 · 通告后冻结')
    page.click('button.primary')
    page.wait_for_timeout(800)
    page.screenshot(path=OUT+'/03-runs-queued.png',full_page=True)
    b.close()

print('console errors:',errs[:5])
print('done')
