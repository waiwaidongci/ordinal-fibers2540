from src.services import note_service as service
from src.services.run_service import get_run
from src.services.quality_service import basis_for_run
def index(db):return [_payload(db,n) for n in service.list_notes(db)]
def create(db,data):return _payload(db,service.create_note(db,data))
def review(db,id,data,user):return _payload(db,service.review_note(db,id,data,user))
def export(db,id):return service.export_note(db,id)
def _payload(db,n):
    run=get_run(db,n.run_id)
    return {**{k:getattr(n,k) for k in ('id','name','run_id','rationale','status','reviewer_note','reviewed_by','created_at')},'quality':basis_for_run(db,run)}
