BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001

CREATE EXTENSION IF NOT EXISTS postgis;

INSERT INTO alembic_version (version_num) VALUES ('0001') RETURNING alembic_version.version_num;

-- Running upgrade 0001 -> 0002

CREATE TABLE wells (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    code VARCHAR(64) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    location geometry(POINT,4326) NOT NULL, 
    municipality VARCHAR(120), 
    state VARCHAR(2), 
    depth_m NUMERIC(10, 2), 
    is_active BOOLEAN DEFAULT true NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE INDEX ix_wells_location_gist ON wells USING gist (location);

CREATE TABLE service_sectors (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    code VARCHAR(64) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    description TEXT, 
    boundary geometry(MULTIPOLYGON,4326) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (code)
);

CREATE INDEX ix_service_sectors_boundary_gist ON service_sectors USING gist (boundary);

CREATE TABLE groundwater_measurements (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    well_id UUID NOT NULL, 
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    water_level_m NUMERIC(10, 3) NOT NULL, 
    temperature_c NUMERIC(6, 2), 
    ph NUMERIC(4, 2), 
    conductivity_us_cm NUMERIC(12, 2), 
    source VARCHAR(80), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_groundwater_level_nonnegative CHECK (water_level_m >= 0), 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE
);

CREATE INDEX ix_groundwater_measured_at ON groundwater_measurements (measured_at);

CREATE INDEX ix_groundwater_well_measured_at ON groundwater_measurements (well_id, measured_at);

CREATE TABLE rainfall_measurements (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    service_sector_id UUID, 
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    precipitation_mm NUMERIC(10, 3) NOT NULL, 
    accumulation_minutes INTEGER, 
    station_code VARCHAR(64), 
    source VARCHAR(80), 
    location geometry(POINT,4326) NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_rainfall_nonnegative CHECK (precipitation_mm >= 0), 
    FOREIGN KEY(service_sector_id) REFERENCES service_sectors (id) ON DELETE SET NULL
);

CREATE INDEX ix_rainfall_location_gist ON rainfall_measurements USING gist (location);

CREATE INDEX ix_rainfall_measured_at ON rainfall_measurements (measured_at);

CREATE INDEX ix_rainfall_sector_measured_at ON rainfall_measurements (service_sector_id, measured_at);

CREATE TABLE operational_measurements (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    well_id UUID NOT NULL, 
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    flow_rate_m3_h NUMERIC(12, 3), 
    pumped_volume_m3 NUMERIC(14, 3), 
    runtime_hours NUMERIC(10, 3), 
    operating_status VARCHAR(40), 
    source VARCHAR(80), 
    PRIMARY KEY (id), 
    CONSTRAINT ck_operational_flow_nonnegative CHECK (flow_rate_m3_h IS NULL OR flow_rate_m3_h >= 0), 
    CONSTRAINT ck_operational_volume_nonnegative CHECK (pumped_volume_m3 IS NULL OR pumped_volume_m3 >= 0), 
    CONSTRAINT ck_operational_runtime_nonnegative CHECK (runtime_hours IS NULL OR runtime_hours >= 0), 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE
);

CREATE INDEX ix_operational_measured_at ON operational_measurements (measured_at);

CREATE INDEX ix_operational_well_measured_at ON operational_measurements (well_id, measured_at);

CREATE TABLE well_sectors (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    well_id UUID NOT NULL, 
    sector_id UUID NOT NULL, 
    valid_from TIMESTAMP WITH TIME ZONE NOT NULL, 
    valid_to TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_well_sector_period CHECK (valid_to IS NULL OR valid_to > valid_from), 
    FOREIGN KEY(sector_id) REFERENCES service_sectors (id) ON DELETE CASCADE, 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE, 
    CONSTRAINT uq_well_sector_period UNIQUE (well_id, sector_id, valid_from)
);

CREATE INDEX ix_well_sectors_sector_id ON well_sectors (sector_id);

CREATE INDEX ix_well_sectors_well_validity ON well_sectors (well_id, valid_from, valid_to);

CREATE TABLE risk_assessments (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    well_id UUID NOT NULL, 
    assessed_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    score NUMERIC(5, 2) NOT NULL, 
    risk_level VARCHAR(16) NOT NULL, 
    methodology_version VARCHAR(40) NOT NULL, 
    valid_until TIMESTAMP WITH TIME ZONE, 
    notes TEXT, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_risk_score_range CHECK (score >= 0 AND score <= 100), 
    CONSTRAINT ck_risk_level CHECK (risk_level IN ('low', 'medium', 'high', 'critical')), 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE
);

CREATE INDEX ix_risk_assessments_assessed_at ON risk_assessments (assessed_at);

CREATE INDEX ix_risk_assessments_level ON risk_assessments (risk_level);

CREATE INDEX ix_risk_assessments_well_assessed_at ON risk_assessments (well_id, assessed_at);

CREATE TABLE risk_factors (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    risk_assessment_id UUID NOT NULL, 
    code VARCHAR(64) NOT NULL, 
    name VARCHAR(160) NOT NULL, 
    raw_value NUMERIC(16, 4), 
    normalized_value NUMERIC(10, 6), 
    weight NUMERIC(10, 6), 
    contribution NUMERIC(10, 6), 
    details JSONB, 
    PRIMARY KEY (id), 
    FOREIGN KEY(risk_assessment_id) REFERENCES risk_assessments (id) ON DELETE CASCADE, 
    CONSTRAINT uq_risk_factor_code UNIQUE (risk_assessment_id, code)
);

CREATE INDEX ix_risk_factors_assessment_id ON risk_factors (risk_assessment_id);

CREATE TABLE alerts (
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    well_id UUID NOT NULL, 
    risk_assessment_id UUID, 
    alert_type VARCHAR(64) NOT NULL, 
    severity VARCHAR(16) NOT NULL, 
    status VARCHAR(16) DEFAULT 'open' NOT NULL, 
    title VARCHAR(255) NOT NULL, 
    message TEXT NOT NULL, 
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    acknowledged_at TIMESTAMP WITH TIME ZONE, 
    resolved_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_alert_severity CHECK (severity IN ('info', 'warning', 'critical')), 
    CONSTRAINT ck_alert_status CHECK (status IN ('open', 'acknowledged', 'resolved')), 
    FOREIGN KEY(risk_assessment_id) REFERENCES risk_assessments (id) ON DELETE SET NULL, 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE
);

CREATE INDEX ix_alerts_risk_assessment_id ON alerts (risk_assessment_id);

CREATE INDEX ix_alerts_status_triggered_at ON alerts (status, triggered_at);

CREATE INDEX ix_alerts_well_triggered_at ON alerts (well_id, triggered_at);

UPDATE alembic_version SET version_num='0002' WHERE alembic_version.version_num = '0001';

-- Running upgrade 0002 -> 0003

ALTER TABLE groundwater_measurements ADD COLUMN data_classification VARCHAR(16);

DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM groundwater_measurements LIMIT 1) THEN
                        RAISE EXCEPTION
                            'classifique explicitamente as linhas existentes de groundwater_measurements antes da migration 0003';
                    END IF;
                END
                $$;

ALTER TABLE groundwater_measurements ADD CONSTRAINT ck_groundwater_data_classification CHECK (data_classification IN ('REAL', 'PUBLIC', 'SIMULATED'));

ALTER TABLE groundwater_measurements ALTER COLUMN data_classification SET NOT NULL;

ALTER TABLE rainfall_measurements ADD COLUMN data_classification VARCHAR(16);

DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM rainfall_measurements LIMIT 1) THEN
                        RAISE EXCEPTION
                            'classifique explicitamente as linhas existentes de rainfall_measurements antes da migration 0003';
                    END IF;
                END
                $$;

ALTER TABLE rainfall_measurements ADD CONSTRAINT ck_rainfall_data_classification CHECK (data_classification IN ('REAL', 'PUBLIC', 'SIMULATED'));

ALTER TABLE rainfall_measurements ALTER COLUMN data_classification SET NOT NULL;

ALTER TABLE operational_measurements ADD COLUMN data_classification VARCHAR(16);

DO $$
                BEGIN
                    IF EXISTS (SELECT 1 FROM operational_measurements LIMIT 1) THEN
                        RAISE EXCEPTION
                            'classifique explicitamente as linhas existentes de operational_measurements antes da migration 0003';
                    END IF;
                END
                $$;

ALTER TABLE operational_measurements ADD CONSTRAINT ck_operational_data_classification CHECK (data_classification IN ('REAL', 'PUBLIC', 'SIMULATED'));

ALTER TABLE operational_measurements ALTER COLUMN data_classification SET NOT NULL;

UPDATE alembic_version SET version_num='0003' WHERE alembic_version.version_num = '0002';

-- Running upgrade 0003 -> 0004

ALTER TABLE wells ADD COLUMN source VARCHAR(80);

ALTER TABLE wells ADD COLUMN data_classification VARCHAR(16) DEFAULT 'UNKNOWN' NOT NULL;

ALTER TABLE service_sectors ADD COLUMN source VARCHAR(80);

ALTER TABLE service_sectors ADD COLUMN data_classification VARCHAR(16) DEFAULT 'UNKNOWN' NOT NULL;

ALTER TABLE well_sectors ADD COLUMN source VARCHAR(80);

ALTER TABLE well_sectors ADD COLUMN data_classification VARCHAR(16) DEFAULT 'UNKNOWN' NOT NULL;

ALTER TABLE groundwater_measurements ADD COLUMN dynamic_level_m NUMERIC(10, 3);

ALTER TABLE groundwater_measurements ADD CONSTRAINT ck_groundwater_dynamic CHECK (dynamic_level_m IS NULL OR dynamic_level_m >= water_level_m);

ALTER TABLE operational_measurements ADD COLUMN daily_demand_m3 NUMERIC(14, 3);

ALTER TABLE operational_measurements ADD COLUMN utilization NUMERIC(14, 5);

ALTER TABLE operational_measurements ADD COLUMN operational_failure BOOLEAN;

ALTER TABLE operational_measurements ADD CONSTRAINT ck_operational_demand CHECK (daily_demand_m3 IS NULL OR daily_demand_m3 >= 0);

ALTER TABLE operational_measurements ADD CONSTRAINT ck_operational_utilization CHECK (utilization IS NULL OR utilization >= 0);

UPDATE alembic_version SET version_num='0004' WHERE alembic_version.version_num = '0003';

-- Running upgrade 0004 -> 0005

ALTER TABLE wells ADD COLUMN source_record_id VARCHAR(64);

ALTER TABLE wells ADD COLUMN source_metadata JSONB;

ALTER TABLE wells ADD CONSTRAINT uq_wells_source_record UNIQUE (source, source_record_id);

ALTER TABLE wells ALTER COLUMN is_active DROP NOT NULL;

UPDATE alembic_version SET version_num='0005' WHERE alembic_version.version_num = '0004';

-- Running upgrade 0005 -> 0006

CREATE TABLE groundwater_observations (
    id UUID NOT NULL, 
    well_id UUID NOT NULL, 
    measured_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    observed_level_m NUMERIC(12, 4) NOT NULL, 
    unit VARCHAR(8) NOT NULL, 
    source VARCHAR(80) NOT NULL, 
    data_classification VARCHAR(16) NOT NULL, 
    dataset VARCHAR(40) NOT NULL, 
    station_code VARCHAR(64) NOT NULL, 
    source_record_id VARCHAR(64) NOT NULL, 
    pumping VARCHAR(1), 
    source_metadata JSONB NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT uq_observation_source_record UNIQUE (source, dataset, station_code, source_record_id), 
    CONSTRAINT ck_observation_origin CHECK (source = 'RIMAS' AND data_classification = 'PUBLIC'), 
    CONSTRAINT ck_observation_unit CHECK (unit = 'm'), 
    FOREIGN KEY(well_id) REFERENCES wells (id) ON DELETE CASCADE
);

CREATE INDEX ix_observation_well_measured_at ON groundwater_observations (well_id, measured_at);

UPDATE alembic_version SET version_num='0006' WHERE alembic_version.version_num = '0005';

-- Running upgrade 0006 -> 0007

CREATE TABLE climate_stations (
    official_code VARCHAR(32) NOT NULL, 
    name VARCHAR(255) NOT NULL, 
    source VARCHAR(80) NOT NULL, 
    observation_type VARCHAR(32) NOT NULL, 
    location geometry(POINT,4326) NOT NULL, 
    source_metadata JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_climate_station_origin CHECK (source = 'INMET' AND observation_type = 'STATION_OBSERVATION'), 
    CONSTRAINT uq_climate_station_identity UNIQUE (source, official_code)
);

CREATE INDEX ix_climate_station_location ON climate_stations USING gist (location);

CREATE TABLE rainfall_observations (
    station_id UUID NOT NULL, 
    measured_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    value_mm NUMERIC(12, 4), 
    unit VARCHAR(8) NOT NULL, 
    source VARCHAR(80) NOT NULL, 
    availability VARCHAR(16) NOT NULL, 
    source_metadata JSONB NOT NULL, 
    id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_rainfall_observation_value CHECK ((availability = 'OBSERVED' AND value_mm >= 0 AND value_mm < 10000000) OR (availability = 'MISSING' AND value_mm IS NULL)), 
    CONSTRAINT ck_rainfall_observation_origin CHECK (source = 'INMET' AND unit = 'mm'), 
    FOREIGN KEY(station_id) REFERENCES climate_stations (id) ON DELETE RESTRICT, 
    CONSTRAINT uq_rainfall_observation_interval UNIQUE (station_id, measured_at)
);

CREATE INDEX ix_rainfall_observation_station_time ON rainfall_observations (station_id, measured_at);

UPDATE alembic_version SET version_num='0007' WHERE alembic_version.version_num = '0006';

-- Running upgrade 0007 -> 0008

ALTER TABLE rainfall_observations DROP CONSTRAINT ck_rainfall_observation_value;

ALTER TABLE rainfall_observations ADD CONSTRAINT ck_rainfall_observation_value CHECK ((availability = 'OBSERVED' AND value_mm IS NOT NULL AND value_mm >= 0 AND value_mm < 10000000) OR (availability = 'MISSING' AND value_mm IS NULL));

UPDATE alembic_version SET version_num='0008' WHERE alembic_version.version_num = '0007';

COMMIT;

