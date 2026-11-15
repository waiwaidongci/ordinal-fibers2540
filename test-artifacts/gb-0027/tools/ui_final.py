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
def login_api(e):
    s,b=call('POST','/auth/login',body={'email':e,'password':'Qingnie2026!'});assert s==200,b;return b['token']
admin=login_api('admin@qingnie.local'); analyst=login_api('analyst@qingnie.local')

# create sample shortage run via API: exclude 26 T1 specimens in QN-NEAR to keep QN-SHIFT intact
readings=call('GET','/readings?study_id=2',admin)[1]
t1=sorted([r['specimen_code'] for r in readings if r['specimen_code'].startswith('QN-NEAR-T1')])
print('t1 count',len(t1))
s,res=call('POST','/notices',admin,{'title':'演示 · 严重批损失','reason':'复核确认大量试样失效，剩余样本不足。','items':[{'study_id':2,'specimen_code':c} for c in t1[:26]]})
print('notice',s)
s,run=call('POST','/runs',analyst,{'name':'演示 · 样本不足失败','study_id':2,'alpha':.05})
print('run',s,run.get('status'),run.get('error','')[:120])

def ui_login(page,email):
    page.goto(BASE+'/#/login');page.fill('input[type=email]',email);page.fill('input[type=password]','Qingnie2026!');page.click('button.primary');page.wait_for_selector('.masthead')

with sync_playwright() as p:
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errs=[]
    page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    ui_login(page,'admin@qingnie.local')
    page.goto(BASE+'/#/');page.wait_for_selector('.opening');page.screenshot(path=OUT+'/12-overview.png',full_page=True)
    page.goto(BASE+'/#/runs');page.wait_for_selector('.run-entry');page.wait_for_timeout(500)
    page.screenshot(path=OUT+'/13-runs-shortage.png',full_page=True)
    # mobile layout check on data page
    m=b.new_context(viewport={'width':390,'height':844},is_mobile=True);mp=m.new_page()
    ui_login(mp,'admin@qingnie.local');mp.goto(BASE+'/#/data');mp.wait_for_selector('.notice-spread');mp.wait_for_timeout(500)
    mp.screenshot(path=OUT+'/14-data-mobile.png',full_page=True)
    b.close()
print('console errors',errs[:5]);print('done')
