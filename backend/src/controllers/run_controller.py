from src.services import run_service as service


def _payload(db,r):
    return {**{k:getattr(r,k) for k in ('id','name','study_id','alpha','status','snapshot','result','error','created_at')},**service.run_trace(db,r)}


def index(db):return [_payload(db,r) for r in service.list_runs(db)]
def create(db,data,user=None):return _payload(db,service.create_run(db,data,user))
def detail(db,id):return _payload(db,service.get_run(db,id))
def trace(db,id):
    r=service.get_run(db,id)
    return service.run_trace(db,r)
