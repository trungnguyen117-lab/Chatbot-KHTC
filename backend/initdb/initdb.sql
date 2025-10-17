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

-- PostgreSQL tự động tạo index cho khóa chính (PRIMARY KEY) và ràng buộc duy nhất (UNIQUE)
-- nên bạn không cần tạo lại index cho cột 'id' và 'email' một cách tường minh.