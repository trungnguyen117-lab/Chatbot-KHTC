-- Bảng người dùng đã có từ file initdb.sql
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

-- Bảng mới cho các cuộc hội thoại
-- Mối quan hệ: Một người dùng (users) có thể có nhiều cuộc hội thoại (conversations)
CREATE TABLE public.conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE, -- Khóa ngoại liên kết với bảng users
    title VARCHAR(255), -- Tiêu đề cho cuộc hội thoại, có thể do người dùng đặt hoặc tự động tạo
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Tạo một kiểu dữ liệu ENUM để giới hạn giá trị cho cột 'type' trong bảng messages
CREATE TYPE message_type AS ENUM ('user', 'chatbot');

-- Bảng mới cho các tin nhắn
-- Mối quan hệ: Một cuộc hội thoại (conversations) có thể có nhiều tin nhắn (messages)
CREATE TABLE public.messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE, -- Khóa ngoại liên kết với bảng conversations
    content TEXT NOT NULL, -- Nội dung của tin nhắn
    type message_type NOT NULL, -- Loại tin nhắn: 'user' hoặc 'chatbot'
    metadata JSONB, -- Trường tùy chọn để lưu trữ thông tin bổ sung (ví dụ: nguồn dữ liệu, feedback,...)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index để cải thiện hiệu suất truy vấn
-- Index trên khóa ngoại của bảng conversations để tăng tốc độ tìm kiếm các cuộc hội thoại của một người dùng
CREATE INDEX idx_conversations_user_id ON public.conversations(user_id);

-- Index trên khóa ngoại của bảng messages để tăng tốc độ tìm kiếm các tin nhắn trong một cuộc hội thoại
CREATE INDEX idx_messages_conversation_id ON public.messages(conversation_id);
