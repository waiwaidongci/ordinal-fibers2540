"""并发验证：通告发布/撤销 vs 新建检验、worker 完成、说明分发。

不经过 HTTP 层，直接调用服务函数与独立 Session，模拟两个事务交错。
"""
import os,sys,tempfile,threading,time,json
DB=tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL']='sqlite:///'+DB
os.environ['REDIS_URL']='redis://localhost:6399/0'
os.environ['JWT_SECRET']='test-secret'
os.environ['SEED_DEMO']='false'
os.environ['ARTIFACTS_DIR']=tempfile.mkdtemp(prefix='artifacts-')
sys.path.insert(0,'/workspace/backend')
from src.config.database import Base,engine,Session
from src import models
from src.models import User,GradeStudy,Treatment,GradeReading,RankTestRun,FollowupNote
from src.utils.security import hash_password
from src.services.quality_service import ensure_quality_lock,create_notice,revoke_notice,lock_quality,basis_for_run
from src.services.run_service import create_run,execute_run
from src.services.note_service import create_note,review_note,export_note
from src.schemas.run import RunInput
from src.schemas.note import NoteInput,ReviewInput
from src.schemas.quality import NoticeInput,NoticeItemInput
from src.constants.enums import RunStatus,NoteStatus
from fastapi import HTTPException

Base.metadata.create_all(engine)
with Session() as db:
    ensure_quality_lock(db)
    admin=User(email='a@x',name='A',role='admin',password_hash=hash_password('x'))
    analyst=User(email='b@x',name='B',role='analyst',password_hash=hash_password('x'))
    db.add_all([admin,analyst]);db.flush()
    s=GradeStudy(code='C1',name='并发研究',protocol='',source_file='')
    db.add(s);db.flush()
    for g in range(3):
        t=Treatment(study_id=s.id,code=f'T{g+1}',name=f'工艺{g+1}',process_note='')
        db.add(t);db.flush()
        for i in range(10):db.add(GradeReading(study_id=s.id,treatment_id=t.id,specimen_code=f'S{g+1}-{i+1:02}',grade=float((i%5)+1),source_note=''))
    db.commit()
    admin_id,analyst_id,sid=admin.id,analyst.id,s.id
T1=Treatment.__table__

def run_payload(name):return RunInput(name=name,study_id=sid,alpha=.05)

def worker_complete(run_id):
    with Session() as db:execute_run(db,run_id)

def scenario_publish_vs_create():
    # A publishes notice while B creates a run for the same study.
    barrier=threading.Barrier(2);results={}
    spec='S1-01'
    def publisher():
        with Session() as db:
            user=db.get(User,admin_id)
            barrier.wait()
            try:
                n,_=create_notice(db,NoticeInput(title='并发通告',reason='并发发布，用于验证顺序一致性',items=[NoticeItemInput(study_id=sid,specimen_code=spec)]),user)
                results['notice']=n.id
            except HTTPException as e:results['notice_error']=(e.status_code,e.detail)
    def creator():
        with Session() as db:
            user=db.get(User,analyst_id)
            barrier.wait()
            try:
                r=create_run(db,run_payload('并发新建检验'),user);results['run']=r.id
            except HTTPException as e:results['run_error']=(e.status_code,e.detail)
    ts=[threading.Thread(target=publisher),threading.Thread(target=creator)]
    for t in ts:t.start()
    for t in ts:t.join()
    assert 'notice' in results,results
    with Session() as db:
        run=db.get(RankTestRun,results['run'])
        # The run must have either excluded S1-01 or been invalidated; never both "clean".
        excluded={e['specimen_code'] for e in run.snapshot['exclusions']}
        basis=basis_for_run(db,run)
        assert (spec in excluded) or basis['invalidated'],(excluded,basis)
        print('publish-vs-create ok: excluded=',spec in excluded,'invalidated=',basis['invalidated'])
    return results['run']

def scenario_revoke_vs_create():
    # Revoke the notice above while creating another run; new run should include the specimen only if revoke committed first.
    with Session() as db:
        nid=db.query(models.QualityNotice).filter_by(title='并发通告').one().id
    barrier=threading.Barrier(2);results={}
    def revoker():
        with Session() as db:
            user=db.get(User,admin_id);barrier.wait()
            revoke_notice(db,nid,'并发撤销，验证只影响新检验',user);results['revoked']=True
    def creator():
        with Session() as db:
            user=db.get(User,analyst_id);barrier.wait()
            r=create_run(db,run_payload('并发撤销后新建'),user);results['run']=r.id
    ts=[threading.Thread(target=revoker),threading.Thread(target=creator)]
    for t in ts:t.start()
    for t in ts:t.join()
    with Session() as db:
        run=db.get(RankTestRun,results['run'])
        excluded={e['specimen_code'] for e in run.snapshot['exclusions']}
        # Both orders are valid, but never a half state: exclusion and notice status must agree.
        n=db.get(models.QualityNotice,nid)
        was_active_at_snapshot=not refetch_revoked(n)
        if 'S1-01' in excluded:
            assert n.status=='revoked',('run excluded specimen but notice still active',n.status)
        print('revoke-vs-create ok: excluded=', 'S1-01' in excluded,'notice=',n.status)
    return results['run']

def refetch_revoked(n):return n.status=='revoked'

def scenario_notice_vs_worker():
    # Queue a run, then publish a notice on a specimen it froze, then complete the worker.
    with Session() as db:
        r=create_run(db,RunInput(name='并发计算前发布通告',study_id=sid,alpha=.05),db.get(User,analyst_id));rid=r.id
    barrier=threading.Barrier(2);results={}
    def publisher():
        with Session() as db:
            user=db.get(User,admin_id);barrier.wait()
            n,_=create_notice(db,NoticeInput(title='计算中通告',reason='worker 计算期间发布的并发通告',items=[NoticeItemInput(study_id=sid,specimen_code='S2-01')]),user)
            results['notice']=n.id
    def worker():
        barrier.wait();worker_complete(rid);results['done']=True
    ts=[threading.Thread(target=publisher),threading.Thread(target=worker)]
    for t in ts:t.start()
    for t in ts:t.join()
    with Session() as db:
        r=db.get(RankTestRun,rid);basis=basis_for_run(db,r)
        # 冻结输入包含 S2-01，所以无论先后，依据最终必须停用。
        assert basis['invalidated'],('worker completion restored an invalid basis',basis)
        assert r.status=='completed'
        print('notice-vs-worker ok: status=',r.status,'invalidated=',basis['invalidated'])
    return rid,results['notice']

def scenario_revoke_after_worker():
    rid,nid=scenario_notice_vs_worker()
    with Session() as db:revoke_notice(db,nid,'计算后撤销，旧依据仍必须停用',db.get(User,admin_id))
    with Session() as db:
        r=db.get(RankTestRun,rid);basis=basis_for_run(db,r)
        assert basis['invalidated'],'revoke restored invalidated basis'
        print('revoke-after-worker ok: still invalidated')
    return rid

def scenario_notice_vs_dispatch():
    # Approved note on a valid run; publish notice then attempt export.
    with Session() as db:
        r=create_run(db,RunInput(name='并发分发前发布通告',study_id=sid,alpha=.05),db.get(User,analyst_id));rid=r.id
    worker_complete(rid)
    with Session() as db:
        n=create_note(db,NoteInput(name='分发说明',run_id=rid,rationale='用于验证并发分发停用行为'))
        review_note(db,n.id,ReviewInput(status=NoteStatus.APPROVED,reviewer_note='同意并发分发验证'),db.get(User,admin_id))
        nid=n.id
    with Session() as db:
        assert export_note(db,nid).startswith('﻿')
    barrier=threading.Barrier(2);results={}
    def publisher():
        with Session() as db:
            user=db.get(User,admin_id);barrier.wait()
            create_notice(db,NoticeInput(title='分发时通告',reason='分发并发时发布的失效通告',items=[NoticeItemInput(study_id=sid,specimen_code='S3-01')]),user)
            results['published']=True
    def exporter():
        barrier.wait()
        with Session() as db:
            try:export_note(db,nid);results['export']='ok'
            except HTTPException as e:results['export']=e.status_code
    ts=[threading.Thread(target=publisher),threading.Thread(target=exporter)]
    for t in ts:t.start()
    for t in ts:t.join()
    with Session() as db:
        r=db.get(RankTestRun,rid);basis=basis_for_run(db,r)
        assert basis['invalidated']
        # After both threads, export must be refused regardless of interleaving.
        with Session() as db2:
            try:export_note(db2,nid);assert False,'export allowed after invalidation'
            except HTTPException as e:assert e.status_code==409,e.status_code
        print('notice-vs-dispatch ok: concurrent export=',results.get('export'),'final basis invalidated')
    return rid

def scenario_legacy_run_without_basis():
    # A run created before this feature has no RunQualityBasis row; active notices must still block dispatch.
    with Session() as db:
        r=create_run(db,RunInput(name='旧版无依据行',study_id=sid,alpha=.05),db.get(User,analyst_id));rid=r.id
    worker_complete(rid)
    with Session() as db:
        basis=db.query(models.RunQualityBasis).filter_by(run_id=rid).one();db.delete(basis);db.commit()
    with Session() as db:
        create_notice(db,NoticeInput(title='旧任务命中',reason='验证旧任务无依据行时仍会停用',items=[NoticeItemInput(study_id=sid,specimen_code='S1-02')]),db.get(User,admin_id))
    with Session() as db:
        r=db.get(RankTestRun,rid);basis=basis_for_run(db,r)
        assert basis['invalidated'],'legacy run without basis row was not invalidated'
        print('legacy-run ok: invalidated without basis row')
    with Session() as db2:
        nid=db2.query(models.QualityNotice).filter_by(title='旧任务命中').one().id
        revoke_notice(db2,nid,'旧任务通告撤销后仍不得恢复',db2.get(User,admin_id))
    with Session() as db3:
        r=db3.get(RankTestRun,rid);basis=basis_for_run(db3,r)
        assert basis['invalidated'],'revoke restored a legacy run that had no basis row'
        print('legacy-run ok: revoke did not restore persisted invalidation')
    with Session() as db:
        n=create_note(db,NoteInput(name='旧任务说明',run_id=rid,rationale='旧任务说明创建应被拒绝'))
        assert False,'note created on invalidated legacy run'

scenario_publish_vs_create()
scenario_revoke_vs_create()
scenario_revoke_after_worker()
scenario_notice_vs_dispatch()
try:scenario_legacy_run_without_basis()
except HTTPException as e:
    assert e.status_code==409,e.status_code
    print('legacy-run ok: invalidated without basis row; note creation refused 409')
print('\nALL CONCURRENCY CHECKS PASSED')
