import os,sys,tempfile,json
db_file=tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL']='sqlite:///'+db_file
os.environ['REDIS_URL']='redis://localhost:6399/0'
os.environ['JWT_SECRET']='test-secret'
os.environ['SEED_DEMO']='true'
os.environ['ARTIFACTS_DIR']=tempfile.mkdtemp(prefix='artifacts-')
sys.path.insert(0,'/workspace/backend')

import fakeredis
import redis as redis_mod
_fake=fakeredis.FakeRedis()
redis_mod.Redis.from_url=classmethod(lambda cls,*a,**k:_fake)
from fastapi.testclient import TestClient
import src.main as main
from src.config.database import Session
from src.models import RankTestRun,QualityNotice,RunQualityBasis,SpecimenExclusion
from src.services.run_service import execute_run

client=TestClient(main.app)
client.__enter__()

def login(email):
    r=client.post('/auth/login',json={'email':email,'password':'Qingnie2026!'})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['token']}

admin=login('admin@qingnie.local'); analyst=login('analyst@qingnie.local'); viewer=login('viewer@qingnie.local')

def studies():
    return client.get('/studies',headers=admin).json()
def study(code):
    return next(s for s in studies() if s['code']==code)
def readings(sid):
    return client.get(f'/readings?study_id={sid}',headers=admin).json()
def run_now(payload):
    r=client.post('/runs',json=payload,headers=analyst)
    assert r.status_code==201,r.text
    body=r.json()
    if body['status']=='queued':
        with Session() as db: execute_run(db,body['id'])
        body=client.get(f"/runs/{body['id']}",headers=admin).json()
    return body

def show(label,value):
    print(f'--- {label}: {json.dumps(value,ensure_ascii=False,default=str)[:1200]}')

qf=study('QN-SHIFT'); near=study('QN-NEAR'); const=study('QN-CONST')

# 1. baseline completed run for QN-SHIFT
base=run_now({'name':'QA baseline shift','study_id':qf['id'],'alpha':0.05})
print('baseline status',base['status'],'exclusions',len(base['exclusions']),'quality',base['quality']['basis_status'])
assert base['status']=='completed',base['error']
assert base['quality']['invalidated'] is False

# 2. create note and approve -> export works
note=client.post('/notes',json={'name':'QA note one','run_id':base['id'],'rationale':'QA rationale with enough characters to pass'},headers=analyst)
print('note create',note.status_code); assert note.status_code==201,note.text
nid=note.json()['id']
rv=client.post(f'/notes/{nid}/review',json={'status':'approved','reviewer_note':'QA approved decision'},headers=admin)
print('note approve',rv.status_code); assert rv.status_code==200,rv.text
exp=client.get(f'/notes/{nid}/export',headers=viewer)
print('export before notice',exp.status_code); assert exp.status_code==200

# 3. publish notice on a specimen in baseline run
spec=readings(qf['id'])[3]['specimen_code']
print('target specimen',spec)
nt=client.post('/notices',json={'title':'QA contamination batch','reason':'Confirmed contaminated by lab QC reference panel','items':[{'study_id':qf['id'],'specimen_code':spec}]},headers=admin)
print('notice create',nt.status_code,nt.text[:300]); assert nt.status_code==201,nt.text
print('invalidated runs',nt.json()['invalidated_run_ids'])
assert base['id'] in nt.json()['invalidated_run_ids']

# 4. old note approval still readable but export 409
d=client.get(f'/runs/{base["id"]}',headers=admin).json()
print('base basis after notice',d['quality']['basis_status'],d['quality']['invalidated_reason'][:120])
assert d['quality']['invalidated'] is True
e2=client.get(f'/notes/{nid}/export',headers=viewer)
print('export after notice',e2.status_code,e2.text[:160]); assert e2.status_code==409
# note still listed and approved
notes=client.get('/notes',headers=viewer).json()
n=next(x for x in notes if x['id']==nid)
assert n['status']=='approved' and n['quality']['invalidated'] is True
# cannot create new note on invalidated run
ntry=client.post('/notes',json={'name':'QA note blocked','run_id':base['id'],'rationale':'QA rationale with enough characters to pass'},headers=analyst)
print('blocked note',ntry.status_code); assert ntry.status_code==409

# 5. new run excludes specimen
newrun=run_now({'name':'QA after notice','study_id':qf['id'],'alpha':0.05})
print('new run',newrun['status'],'excl',len(newrun['exclusions']),'N',newrun['result'].get('n'),'snap N',len(newrun['snapshot']['readings']))
assert newrun['status']=='completed'
assert len(newrun['exclusions'])==1 and newrun['exclusions'][0]['specimen_code']==spec
assert newrun['result']['n']==119
assert newrun['quality']['invalidated'] is False

# 6. revoke notice: old run remains invalid, new run current, new-new run includes specimen
notice_id=nt.json()['notice']['id']
rev=client.post(f'/notices/{notice_id}/revoke',json={'reason':'QC re-check cleared this specimen batch'},headers=admin)
print('revoke',rev.status_code,rev.text[:200]); assert rev.status_code==200
d_old=client.get(f'/runs/{base["id"]}',headers=admin).json()
print('old run after revoke',d_old['quality']['basis_status']); assert d_old['quality']['invalidated'] is True
d_new=client.get(f'/runs/{newrun["id"]}',headers=admin).json()
print('excluded run after revoke',d_new['quality']['basis_status']); assert d_new['quality']['invalidated'] is False
e3=client.get(f'/notes/{nid}/export',headers=viewer); print('old export after revoke',e3.status_code); assert e3.status_code==409
restored=run_now({'name':'QA after revoke','study_id':qf['id'],'alpha':0.05})
print('restored run excl',len(restored['exclusions']),'N',restored['result'].get('n'))
assert len(restored['exclusions'])==0 and restored['result']['n']==120

# 7. overlapping notices: specimen stays excluded until all revoked
spec2=readings(qf['id'])[7]['specimen_code']
n1=client.post('/notices',json={'title':'QA overlap one','reason':'First overlapping QC hold reason text','items':[{'study_id':qf['id'],'specimen_code':spec2}]},headers=admin)
n2=client.post('/notices',json={'title':'QA overlap two','reason':'Second overlapping QC hold reason text','items':[{'study_id':qf['id'],'specimen_code':spec2}]},headers=admin)
print('overlap notices',n1.status_code,n2.status_code); assert n1.status_code==201 and n2.status_code==201
over=run_now({'name':'QA overlap both','study_id':qf['id'],'alpha':0.05})
print('overlap run excl',[(e['specimen_code'],e['notice_ids']) for e in over['exclusions']])
assert len(over['exclusions'])==1 and len(over['exclusions'][0]['notice_ids'])==2
client.post(f'/notices/{n1.json()["notice"]["id"]}/revoke',json={'reason':'Overlap one released after review'},headers=admin)
mid=run_now({'name':'QA overlap one revoked','study_id':qf['id'],'alpha':0.05})
print('after one revoke excl',len(mid['exclusions'])); assert len(mid['exclusions'])==1
client.post(f'/notices/{n2.json()["notice"]["id"]}/revoke',json={'reason':'Overlap two released after review'},headers=admin)
after=run_now({'name':'QA overlap both revoked','study_id':qf['id'],'alpha':0.05})
print('after both revoke excl',len(after['exclusions'])); assert len(after['exclusions'])==0

# 8. cross-study notice: one notice covers two studies
s_a=readings(near['id'])[0]['specimen_code']; s_b=readings(const['id'])[0]['specimen_code']
cross=client.post('/notices',json={'title':'QA cross-study hold','reason':'Cross-study contamination suspected in shared incubator','items':[{'study_id':near['id'],'specimen_code':s_a},{'study_id':const['id'],'specimen_code':s_b}]},headers=admin)
print('cross notice',cross.status_code,cross.text[:300]); assert cross.status_code==201
cross_items=cross.json()['notice']['items']
print('cross items',[(i['study_code'],i['specimen_code']) for i in cross_items])
nr=run_now({'name':'QA cross near','study_id':near['id'],'alpha':0.05})
print('near run excl',[(e['specimen_code'],e['notice_ids']) for e in nr['exclusions']]); assert len(nr['exclusions'])==1
# QN-CONST excludes one of 30 per group? all identical => will fail anyway; check exclusion shortfall path instead with shift
client.post(f'/notices/{cross.json()["notice"]["id"]}/revoke',json={'reason':'Cross-study hold cleared after retest'},headers=admin)

# 9. sample shortage failure: exclude enough from one treatment (30 -> below 5 requires 26 excluded)
codes=[r['specimen_code'] for r in readings(qf['id']) if r['treatment_id']==readings(qf['id'])[0]['treatment_id']]
short_codes=codes[:26]
sn=client.post('/notices',json={'title':'QA severe batch loss','reason':'Severe contamination leaves too few valid specimens','items':[{'study_id':qf['id'],'specimen_code':c} for c in short_codes]},headers=admin)
print('short notice',sn.status_code); assert sn.status_code==201
shortrun=client.post('/runs',json={'name':'QA short sample','study_id':qf['id'],'alpha':0.05},headers=analyst)
print('short run',shortrun.status_code,shortrun.json()['status'],shortrun.json()['error'][:200])
assert shortrun.status_code==201 and shortrun.json()['status']=='failed'
assert '样本不足' in shortrun.json()['error']
# all treatments kept, exclusions frozen
assert len(shortrun.json()['snapshot']['treatments'])==4
assert len(shortrun.json()['exclusions'])==26
assert shortrun.json()['result']=={}
client.post(f'/notices/{sn.json()["notice"]["id"]}/revoke',json={'reason':'Reference panel confirmed remaining specimens usable'},headers=admin)

# 10. invalid notice payloads
bad=client.post('/notices',json={'title':'QA bad specimen','reason':'Specimen does not exist in study at all','items':[{'study_id':qf['id'],'specimen_code':'NOPE-1'}]},headers=admin)
print('bad specimen',bad.status_code,bad.text[:200]); assert bad.status_code==422
bad2=client.post('/notices',json={'title':'QA duplicate','reason':'Duplicate specimen in one notice list','items':[{'study_id':qf['id'],'specimen_code':spec},{'study_id':qf['id'],'specimen_code':spec}]},headers=admin)
print('duplicate',bad2.status_code); assert bad2.status_code==409
denied=client.post('/notices',json={'title':'QA denied','reason':'Analyst should not issue notice here','items':[{'study_id':qf['id'],'specimen_code':spec}]},headers=analyst)
print('analyst issue denied',denied.status_code); assert denied.status_code==403

# 11. invalidated run cannot have note approved / created; re-check late complete does not restore
# simulate a queued run whose specimen is invalidated while running
q=client.post('/runs',json={'name':'QA queued then notice','study_id':qf['id'],'alpha':0.05},headers=analyst).json()
print('q status',q['status']); assert q['status']=='queued'
late_spec=q['snapshot']['readings'][0]['specimen_code']
ln=client.post('/notices',json={'title':'QA late contamination','reason':'Contamination discovered while queued task runs','items':[{'study_id':qf['id'],'specimen_code':late_spec}]},headers=admin)
print('late notice invalidated',ln.json()['invalidated_run_ids']); assert q['id'] in ln.json()['invalidated_run_ids']
with Session() as db: execute_run(db,q['id'])
qq=client.get(f'/runs/{q["id"]}',headers=admin).json()
print('late completed',qq['status'],qq['quality']['basis_status'])
assert qq['status']=='completed' and qq['quality']['invalidated'] is True
# revoke late notice: still invalidated
client.post(f'/notices/{ln.json()["notice"]["id"]}/revoke',json={'reason':'Late hold released but basis stays invalid'},headers=admin)
qq2=client.get(f'/runs/{q["id"]}',headers=admin).json()
print('late after revoke',qq2['quality']['basis_status']); assert qq2['quality']['invalidated'] is True
# export attempt: create note? create should be blocked
blocked=client.post('/notes',json={'name':'QA late note','run_id':q['id'],'rationale':'QA late note rationale long enough'},headers=analyst)
print('late note blocked',blocked.status_code); assert blocked.status_code==409

# 12. trace endpoint
tr=client.get(f'/runs/{base["id"]}/trace',headers=viewer).json()
print('trace keys',tr.keys(),'quality',tr['quality']['basis_status'],'excl',len(tr['exclusions']))
assert 'quality' in tr and 'exclusions' in tr

# 12b. notices expose affected run ids
ns=client.get('/notices',headers=viewer).json()
print('notice list fields',sorted(ns[0].keys()))
assert all('affected_run_ids' in n for n in ns)
by_id={n['id']:n for n in ns}
print('affected for notice1',by_id[1]['affected_run_ids'])
assert 1 in by_id[1]['affected_run_ids']

# 13. audit contains notice actions
audit=client.get('/audit',headers=admin).json()
acts=[a['action'] for a in audit]
print('audit sample',acts[:8])
assert any('/notices' in a for a in acts)

print('\nALL BACKEND CHECKS PASSED')
client.__exit__(None,None,None)
