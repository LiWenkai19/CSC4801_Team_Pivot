-- Review artifact only. Teammate employer_profile and job must exist before owned_flow_002.
BEGIN;

CREATE TABLE alembic_owned_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_owned_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> owned_core_001

CREATE TABLE "user" (
    id UUID NOT NULL,
    email VARCHAR NOT NULL,
    hashed_password VARCHAR NOT NULL,
    role VARCHAR(9) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT user_role CHECK (role IN ('candidate', 'employer'))
);

CREATE UNIQUE INDEX ix_user_email ON "user" (email);

CREATE TABLE candidate_profile (
    user_id UUID NOT NULL,
    display_name VARCHAR NOT NULL,
    resume_text TEXT DEFAULT '' NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id),
    CONSTRAINT ck_candidate_display_name CHECK (length(trim(display_name)) > 0),
    FOREIGN KEY(user_id) REFERENCES "user" (id)
);

CREATE TABLE candidate_skill (
    candidate_id UUID NOT NULL,
    name VARCHAR NOT NULL,
    PRIMARY KEY (candidate_id, name),
    CONSTRAINT ck_candidate_skill_normalized_name CHECK (length(name) > 0 AND name = lower(trim(name))),
    FOREIGN KEY(candidate_id) REFERENCES candidate_profile (user_id)
);

CREATE TABLE company (
    id UUID NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT DEFAULT '' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_company_name CHECK (length(trim(name)) > 0)
);

CREATE FUNCTION owned_set_updated_at() RETURNS trigger AS $$
            BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END;
            $$ LANGUAGE plpgsql;

CREATE TRIGGER owned_candidate_profile_updated_at
            BEFORE UPDATE ON candidate_profile FOR EACH ROW
            EXECUTE FUNCTION owned_set_updated_at();

CREATE TRIGGER owned_company_updated_at
            BEFORE UPDATE ON company FOR EACH ROW
            EXECUTE FUNCTION owned_set_updated_at();

INSERT INTO alembic_owned_version (version_num) VALUES ('owned_core_001') RETURNING alembic_owned_version.version_num;

-- Running upgrade owned_core_001 -> owned_flow_002

CREATE TABLE application (
    id UUID NOT NULL,
    candidate_id UUID NOT NULL,
    job_id UUID NOT NULL,
    status VARCHAR(12) DEFAULT 'Pending' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_application_candidate_job UNIQUE (candidate_id, job_id),
    FOREIGN KEY(candidate_id) REFERENCES candidate_profile (user_id),
    FOREIGN KEY(job_id) REFERENCES job (id),
    CONSTRAINT application_status CHECK (status IN ('Pending', 'Interviewing', 'Rejected', 'Accepted'))
);

CREATE INDEX ix_application_candidate_id ON application (candidate_id);

CREATE INDEX ix_application_job_id ON application (job_id);

CREATE TABLE interview_slot (
    id UUID NOT NULL,
    employer_id UUID NOT NULL,
    job_id UUID,
    starts_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ends_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_slot_time_order CHECK (ends_at > starts_at),
    CONSTRAINT ck_slot_duration CHECK ((ends_at - starts_at) = INTERVAL '30 minutes'),
    FOREIGN KEY(employer_id) REFERENCES employer_profile (user_id),
    FOREIGN KEY(job_id) REFERENCES job (id)
);

CREATE INDEX ix_interview_slot_employer_id ON interview_slot (employer_id);

CREATE TRIGGER owned_application_updated_at
            BEFORE UPDATE ON application FOR EACH ROW
            EXECUTE FUNCTION owned_set_updated_at();

UPDATE alembic_owned_version SET version_num='owned_flow_002' WHERE alembic_owned_version.version_num = 'owned_core_001';

-- Running upgrade owned_flow_002 -> owned_booking_003

CREATE TABLE booking (
    id UUID NOT NULL,
    application_id UUID NOT NULL,
    slot_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_booking_application UNIQUE (application_id),
    CONSTRAINT uq_booking_slot UNIQUE (slot_id),
    FOREIGN KEY(application_id) REFERENCES application (id),
    FOREIGN KEY(slot_id) REFERENCES interview_slot (id)
);

UPDATE alembic_owned_version SET version_num='owned_booking_003' WHERE alembic_owned_version.version_num = 'owned_flow_002';

COMMIT;
