from src.services import reading_service as service
def index(db,study_id):return service.decorate(db,service.list_readings(db,study_id),study_id)
def create(db,data):
    r=service.create_reading(db,data)
    return service.decorate(db,[r],data.study_id)[0]
def update(db,id,data):
    r=service.update_reading(db,id,data)
    return service.decorate(db,[r],data.study_id)[0]
