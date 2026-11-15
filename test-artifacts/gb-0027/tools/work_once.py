import os,sys
os.environ['DATABASE_URL']='sqlite:////tmp/qtest/demo.db'
os.environ['REDIS_URL']='redis://localhost:6399/0'
os.environ['SEED_DEMO']='false'
os.environ['ARTIFACTS_DIR']='/tmp/qtest/artifacts'
sys.path.insert(0,'/workspace/backend')
from sqlalchemy import select
from src.config.database import Session
from src.models import RankTestRun
from src.services.run_service import execute_run
from src.services.quality_service import ensure_quality_lock
with Session() as db:ensure_quality_lock(db)
with Session() as db:
    for r in db.scalars(select(RankTestRun).where(RankTestRun.status=='queued')).all():execute_run(db,r.id)
print('worker pass done')
