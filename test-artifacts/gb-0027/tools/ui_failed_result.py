import os
from playwright.sync_api import sync_playwright
BASE='http://127.0.0.1:18231';OUT='/workspace/test-artifacts/gb-0027'
def ui_login(page,email):
    page.goto(BASE+'/#/login');page.fill('input[type=email]',email);page.fill('input[type=password]','Qingnie2026!');page.click('button.primary');page.wait_for_selector('.masthead')
with sync_playwright() as p:
    b=p.chromium.launch();ctx=b.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errs=[]
    page.on('console',lambda m: errs.append(m.text) if m.type=='error' else None)
    ui_login(page,'viewer@qingnie.local')
    page.evaluate("localStorage.setItem('ordinal-run','3')")
    page.goto(BASE+'/#/results');page.wait_for_selector('.failed-spread');page.wait_for_timeout(400)
    page.screenshot(path=OUT+'/15-results-failed.png',full_page=True)
    b.close()
print('errors',errs[:3]);print('done')
