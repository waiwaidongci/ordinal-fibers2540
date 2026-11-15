import os,sys
os.environ['DATABASE_URL']='sqlite:////tmp/qtest/demo.db'
os.environ['REDIS_URL']='redis://localhost:6399/0'
os.environ['JWT_SECRET']='dev-secret'
os.environ['SEED_DEMO']='true'
os.environ['ARTIFACTS_DIR']='/tmp/qtest/artifacts'
sys.path.insert(0,'/workspace/backend')
import fakeredis,redis as redis_mod
_fake=fakeredis.FakeRedis()
redis_mod.Redis.from_url=classmethod(lambda cls,*a,**k:_fake)
from src.config.database import Base,engine,Session
from src import models
Base.metadata.create_all(engine)
from src.services.quality_service import ensure_quality_lock
with Session() as db:ensure_quality_lock(db)
import uvicorn
uvicorn.run('src.main:app',host='127.0.0.1',port=19231,log_level='warning')
