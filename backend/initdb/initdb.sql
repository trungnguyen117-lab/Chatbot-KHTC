CREATE TABLE public.users (
    id SERIAL PRIMARY KEY,
    email VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR NOT NULL,
    fullname VARCHAR NOT NULL,
    employee_id VARCHAR,
    role VARCHAR,
    department VARCHAR,
    position VARCHAR,
    organization VARCHAR,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

