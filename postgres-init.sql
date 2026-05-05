-- 一個 Postgres 實例承載 5 個 service 的 DB（每個 service 自己 schema 沒切，用 separate db）
-- 由 ransim user 統一擁有所有 db
CREATE DATABASE cu_db OWNER ransim;
CREATE DATABASE du_db OWNER ransim;
CREATE DATABASE ru_db OWNER ransim;
CREATE DATABASE physics_db OWNER ransim;
