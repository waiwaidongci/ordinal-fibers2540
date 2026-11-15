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
admin=login_api('admin@qingnie.local')

def ui_login(page,email):
    page.goto(BASE+'/#/login');page.fill('input[type=email]',email);page.fill('input[type=password]','Qingnie2026!');page.click('button.primary');page.wait_for_selector('.masthead')

with sync_playwright() as p:
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errs=[]
    page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    ui_login(page,'admin@qingnie.local')
    page.goto(BASE+'/#/data');page.wait_for_selector('.notice-spread')
    page.click('summary:has-text("按试样清单发布通告")')
    page.fill('input[name=title]','跨研究通告 · 共享培养箱')
    page.fill('textarea[name=codes]','QN-SHIFT-T2-011\nQN-NEAR/QN-NEAR-T2-002')
    page.fill('textarea[name=reason]','共享培养箱异常，两个研究的试样同时失效。')
    page.click('button:has-text("发布通告并停用受影响依据")')
    page.wait_for_selector('.success:has-text("质量通告已发布")')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT+'/09-data-cross-study.png',full_page=True)
    # revoke via UI: click the specific notice's revoke button (notice #2 is the overlap row)
    row=page.locator('.notice-spread table tbody tr',has_text='#2 · 重叠通告')
    row.locator('button:has-text("撤销此通告")').click()
    row.locator('textarea[name=reason]').fill('复检确认该重叠通告可撤销，另一个仍有效。')
    row.locator('button:has-text("确认撤销")').click()
    page.wait_for_selector('.success:has-text("已撤销")')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT+'/10-data-revoked.png',full_page=True)
    # notes page as admin on invalidated note
    page.goto(BASE+'/#/notes');page.wait_for_timeout(800)
    page.screenshot(path=OUT+'/11-notes-admin.png',full_page=True)
    b.close()
print('console errors',errs[:5]);print('done')
