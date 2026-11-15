import os,json,time
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:18231'
OUT=os.environ.get('OUT','/workspace/test-artifacts/gb-0027')
os.makedirs(OUT,exist_ok=True)

def login(page,email):
    page.goto(BASE+'/#/login')
    page.fill('input[type=email]',email)
    page.fill('input[type=password]','Qingnie2026!')
    page.click('button.primary')
    page.wait_for_selector('.masthead')

with sync_playwright() as p:
    b=p.chromium.launch()
    ctx=b.new_context(viewport={'width':1440,'height':1000},device_scale_factor=1)
    page=ctx.new_page()
    errors=[]
    page.on('console',lambda m: errors.append(m.text) if m.type=='error' else None)
    login(page,'admin@qingnie.local')
    page.goto(BASE+'/#/data')
    page.wait_for_selector('.data-spread')
    page.screenshot(path=OUT+'/01-data-before.png',full_page=True)
    # issue notice for two specimens from QN-SHIFT (study 1)
    page.click('summary:has-text("按试样清单发布通告")')
    page.fill('input[name=title]','2026-11-15 批次污染')
    page.fill('textarea[name=codes]','QN-SHIFT-T1-004\nQN-SHIFT-T1-008')
    page.fill('textarea[name=reason]','上游确认该批试样受污染，等级不得作为有效证据。')
    page.click('button:has-text("发布通告并停用受影响依据")')
    page.wait_for_selector('.success:has-text("质量通告已发布")')
    page.wait_for_timeout(600)
    page.screenshot(path=OUT+'/02-data-notice.png',full_page=True)
    q=page.evaluate("fetch('/api/notices').then(r=>r.json())")
    print('notices',json.dumps(q,ensure_ascii=False)[:300])
    print('console errors',errors[:5])
    b.close()
print('done')
