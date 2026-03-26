-- =========================================
-- USERS TABLE FUNCTIONS
-- =========================================

-- Create User
CREATE OR REPLACE FUNCTION create_user(
    p_username VARCHAR,
    p_email VARCHAR,
    p_password_hash VARCHAR,
    p_role VARCHAR DEFAULT 'reviewer'
)
RETURNS BIGINT AS $$
DECLARE
    new_user_id BIGINT;
BEGIN
    INSERT INTO users (
        username,
        email,
        password_hash,
        role
    )
    VALUES (
        p_username,
        p_email,
        p_password_hash,
        p_role
    )
    RETURNING id INTO new_user_id;

    RETURN new_user_id;
END;
$$ LANGUAGE plpgsql;


-- Get User By ID
CREATE OR REPLACE FUNCTION get_user_by_id(
    p_user_id BIGINT
)
RETURNS TABLE (
    id BIGINT,
    username VARCHAR,
    email VARCHAR,
    role VARCHAR,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.username, u.email, u.role, u.created_at
    FROM users u
    WHERE u.id = p_user_id;
END;
$$ LANGUAGE plpgsql;


-- Get User By Email
CREATE OR REPLACE FUNCTION get_user_by_email(
    p_email VARCHAR
)
RETURNS TABLE (
    id BIGINT,
    username VARCHAR,
    email VARCHAR,
    password_hash VARCHAR,
    role VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT u.id, u.username, u.email, u.password_hash, u.role
    FROM users u
    WHERE u.email = p_email;
END;
$$ LANGUAGE plpgsql;


-- Update User Role
CREATE OR REPLACE FUNCTION update_user_role(
    p_user_id BIGINT,
    p_new_role VARCHAR
)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET role = p_new_role
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;


-- Delete User
CREATE OR REPLACE FUNCTION delete_user(
    p_user_id BIGINT
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM users
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;
