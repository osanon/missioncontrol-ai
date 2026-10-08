-- Reference schema generated from backend/db.py. Use database.bootstrap for setup.


CREATE TABLE agent_runs (
	id VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	question VARCHAR NOT NULL, 
	answer VARCHAR NOT NULL, 
	mode VARCHAR NOT NULL, 
	trace JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE audit_records (
	id VARCHAR NOT NULL, 
	occurred_at VARCHAR NOT NULL, 
	actor VARCHAR NOT NULL, 
	event VARCHAR NOT NULL, 
	details JSON NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE clients (
	id SERIAL NOT NULL, 
	external_id VARCHAR, 
	full_name VARCHAR NOT NULL, 
	birth_date VARCHAR(10), 
	email VARCHAR, 
	review_required BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (external_id)
)

;


CREATE TABLE programs (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE proposed_actions (
	id VARCHAR NOT NULL, 
	issue_key VARCHAR, 
	table_name VARCHAR NOT NULL, 
	record_id INTEGER NOT NULL, 
	before JSON NOT NULL, 
	after JSON NOT NULL, 
	reason VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	created_at VARCHAR NOT NULL, 
	decided_at VARCHAR, 
	decided_by VARCHAR, 
	PRIMARY KEY (id), 
	UNIQUE (issue_key)
)

;


CREATE TABLE assessments (
	id SERIAL NOT NULL, 
	client_id INTEGER NOT NULL, 
	assessment_date VARCHAR(10), 
	kind VARCHAR, 
	score FLOAT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id)
)

;


CREATE TABLE employment (
	id SERIAL NOT NULL, 
	client_id INTEGER NOT NULL, 
	start_date VARCHAR(10) NOT NULL, 
	end_date VARCHAR(10), 
	hourly_wage FLOAT, 
	review_required BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id)
)

;


CREATE TABLE enrollments (
	id SERIAL NOT NULL, 
	client_id INTEGER NOT NULL, 
	program_id INTEGER NOT NULL, 
	start_date VARCHAR(10) NOT NULL, 
	end_date VARCHAR(10), 
	status VARCHAR NOT NULL, 
	review_required BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(program_id) REFERENCES programs (id)
)

;


CREATE TABLE housing (
	id SERIAL NOT NULL, 
	client_id INTEGER NOT NULL, 
	entry_date VARCHAR(10) NOT NULL, 
	exit_date VARCHAR(10), 
	destination VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id)
)

;


CREATE TABLE services (
	id SERIAL NOT NULL, 
	client_id INTEGER NOT NULL, 
	program_id INTEGER NOT NULL, 
	service_date VARCHAR(10) NOT NULL, 
	units FLOAT NOT NULL, 
	review_required BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(client_id) REFERENCES clients (id), 
	FOREIGN KEY(program_id) REFERENCES programs (id)
)

;


CREATE TABLE surveys (
	id SERIAL NOT NULL, 
	program_id INTEGER NOT NULL, 
	response_date VARCHAR(10), 
	rating INTEGER, 
	comment VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(program_id) REFERENCES programs (id)
)

;


CREATE TABLE followups (
	id SERIAL NOT NULL, 
	employment_id INTEGER NOT NULL, 
	due_date VARCHAR(10), 
	completed_date VARCHAR(10), 
	retained BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(employment_id) REFERENCES employment (id)
)

;
