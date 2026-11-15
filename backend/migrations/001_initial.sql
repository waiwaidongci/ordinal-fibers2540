
CREATE TABLE audits (
	id INTEGER NOT NULL AUTO_INCREMENT,
	actor VARCHAR(160) NOT NULL,
	action VARCHAR(180) NOT NULL,
	status_code INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
)

;


CREATE TABLE grade_studies (
	id INTEGER NOT NULL AUTO_INCREMENT,
	code VARCHAR(40) NOT NULL,
	name VARCHAR(140) NOT NULL,
	protocol VARCHAR(1200) NOT NULL,
	source_file VARCHAR(140) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (code)
)

;


CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT,
	email VARCHAR(160) NOT NULL,
	name VARCHAR(80) NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	password_hash VARCHAR(250) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (email)
)

;


CREATE TABLE rank_test_runs (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(140) NOT NULL,
	study_id INTEGER NOT NULL,
	alpha DOUBLE NOT NULL,
	status VARCHAR(20) NOT NULL,
	snapshot JSON NOT NULL,
	result JSON NOT NULL,
	error VARCHAR(600) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name),
	FOREIGN KEY(study_id) REFERENCES grade_studies (id)
)

;


CREATE TABLE treatments (
	id INTEGER NOT NULL AUTO_INCREMENT,
	study_id INTEGER NOT NULL,
	code VARCHAR(40) NOT NULL,
	name VARCHAR(100) NOT NULL,
	process_note VARCHAR(1000) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (study_id, code),
	FOREIGN KEY(study_id) REFERENCES grade_studies (id)
)

;


CREATE TABLE followup_notes (
	id INTEGER NOT NULL AUTO_INCREMENT,
	name VARCHAR(140) NOT NULL,
	run_id INTEGER NOT NULL,
	rationale VARCHAR(2000) NOT NULL,
	status VARCHAR(20) NOT NULL,
	reviewer_note VARCHAR(1000) NOT NULL,
	reviewed_by VARCHAR(140) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (name),
	FOREIGN KEY(run_id) REFERENCES rank_test_runs (id)
)

;


CREATE TABLE grade_readings (
	id INTEGER NOT NULL AUTO_INCREMENT,
	study_id INTEGER NOT NULL,
	treatment_id INTEGER NOT NULL,
	specimen_code VARCHAR(60) NOT NULL,
	grade DOUBLE NOT NULL,
	source_note VARCHAR(250) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (study_id, specimen_code),
	FOREIGN KEY(study_id) REFERENCES grade_studies (id),
	FOREIGN KEY(treatment_id) REFERENCES treatments (id)
)

;

CREATE TABLE quality_locks (
	id INTEGER NOT NULL AUTO_INCREMENT,
	note VARCHAR(80) NOT NULL,
	PRIMARY KEY (id)
) ;

INSERT INTO quality_locks (id, note) VALUES (1, 'quality-basis-serialization');

CREATE TABLE quality_notices (
	id INTEGER NOT NULL AUTO_INCREMENT,
	title VARCHAR(160) NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	items JSON NOT NULL,
	status VARCHAR(20) NOT NULL,
	issued_by VARCHAR(140) NOT NULL,
	created_at DATETIME NOT NULL,
	revoked_by VARCHAR(140) NOT NULL,
	revocation_reason VARCHAR(1000) NOT NULL,
	revoked_at DATETIME,
	PRIMARY KEY (id)
) ;
CREATE INDEX ix_quality_notices_status ON quality_notices (status);

CREATE TABLE run_quality_bases (
	id INTEGER NOT NULL AUTO_INCREMENT,
	run_id INTEGER NOT NULL,
	study_id INTEGER NOT NULL,
	basis_status VARCHAR(20) NOT NULL,
	exclusion_count INTEGER NOT NULL,
	exclusion_fingerprint VARCHAR(64) NOT NULL,
	applied_notice_ids JSON NOT NULL,
	invalidated_by_notice_ids JSON NOT NULL,
	invalidated_reason VARCHAR(1000) NOT NULL,
	invalidated_by VARCHAR(140) NOT NULL,
	invalidated_at DATETIME,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (run_id),
	FOREIGN KEY(run_id) REFERENCES rank_test_runs (id),
	FOREIGN KEY(study_id) REFERENCES grade_studies (id)
) ;
CREATE INDEX ix_run_quality_bases_study ON run_quality_bases (study_id);

CREATE TABLE specimen_exclusions (
	id INTEGER NOT NULL AUTO_INCREMENT,
	run_id INTEGER NOT NULL,
	study_id INTEGER NOT NULL,
	specimen_code VARCHAR(60) NOT NULL,
	treatment_code VARCHAR(40) NOT NULL,
	treatment_name VARCHAR(100) NOT NULL,
	grade DOUBLE NOT NULL,
	notice_ids JSON NOT NULL,
	notice_titles JSON NOT NULL,
	reason VARCHAR(1000) NOT NULL,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (run_id, specimen_code),
	FOREIGN KEY(run_id) REFERENCES rank_test_runs (id),
	FOREIGN KEY(study_id) REFERENCES grade_studies (id)
) ;
CREATE INDEX ix_specimen_exclusions_run ON specimen_exclusions (run_id);
