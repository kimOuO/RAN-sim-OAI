-- 一個 Postgres 實例承載 4 個 service 的 DB（cu/du/ru/physics，各自 separate db；omniver_db 在另一台）
-- 由 ransim user 統一擁有所有 db
CREATE DATABASE cu_db OWNER ransim;
CREATE DATABASE du_db OWNER ransim;
CREATE DATABASE ru_db OWNER ransim;
CREATE DATABASE physics_db OWNER ransim;
