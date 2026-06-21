-- 企业用工与社保合规智能平台 MySQL 初始化参考
-- 实际开发启动会由 SQLAlchemy 自动建表；本文件用于交付审阅、DBA 核验或手工重建。

CREATE DATABASE IF NOT EXISTS employment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE employment;

CREATE TABLE IF NOT EXISTS slc_tenants (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(64) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  industry VARCHAR(80),
  region VARCHAR(80) NOT NULL DEFAULT '陕西',
  contact_name VARCHAR(80),
  contact_email VARCHAR(120),
  contact_phone VARCHAR(40),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  data_scope VARCHAR(30) NOT NULL DEFAULT 'tenant',
  dify_api_key TEXT,
  dify_app_id VARCHAR(120),
  ragflow_dataset_id VARCHAR(120),
  notes TEXT,
  is_demo BOOLEAN NOT NULL DEFAULT FALSE,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_slc_tenants_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_admins (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NULL,
  username VARCHAR(50) NOT NULL,
  password_hash VARCHAR(200) NOT NULL,
  role VARCHAR(20) NOT NULL DEFAULT 'operator',
  display_name VARCHAR(80),
  email VARCHAR(120),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  last_login_at DATETIME,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_slc_admin_tenant_username (tenant_id, username),
  INDEX ix_slc_admins_username (username),
  INDEX ix_slc_admins_tenant_id (tenant_id),
  CONSTRAINT fk_slc_admins_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_sources (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  source_code VARCHAR(40),
  title VARCHAR(200) NOT NULL,
  url VARCHAR(500),
  doc_type VARCHAR(20),
  issuer VARCHAR(120) NOT NULL DEFAULT '',
  region VARCHAR(50),
  publish_date DATE,
  effective_date DATE,
  validity_status VARCHAR(30) NOT NULL DEFAULT '有效',
  review_status VARCHAR(30) NOT NULL DEFAULT '待人工复核',
  reviewed_at DATETIME,
  reviewed_by VARCHAR(80),
  captured_at DATE,
  owner VARCHAR(80),
  local_file VARCHAR(500),
  note TEXT,
  description TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_slc_sources_tenant_source_code (tenant_id, source_code),
  UNIQUE KEY uq_slc_sources_tenant_url (tenant_id, url),
  UNIQUE KEY uq_slc_sources_tenant_title_issuer (tenant_id, title, issuer),
  INDEX ix_slc_sources_tenant_id (tenant_id),
  INDEX ix_slc_sources_source_code (source_code),
  CONSTRAINT fk_slc_sources_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_chat_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  user_id VARCHAR(64),
  session_id VARCHAR(64),
  conversation_id VARCHAR(128),
  language VARCHAR(12) NOT NULL DEFAULT 'zh-CN',
  question TEXT NOT NULL,
  answer TEXT,
  sources JSON,
  related_tasks JSON,
  provider VARCHAR(30) NOT NULL DEFAULT 'kb_no_match',
  risk_level VARCHAR(20) NOT NULL DEFAULT 'medium',
  response_time INT,
  status VARCHAR(20) DEFAULT 'success',
  client_ip_hash VARCHAR(128),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_slc_chat_logs_tenant_id (tenant_id),
  INDEX ix_slc_chat_logs_user_id (user_id),
  INDEX ix_slc_chat_logs_session_id (session_id),
  CONSTRAINT fk_slc_chat_logs_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_feedbacks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  question_id INT NULL,
  user_id VARCHAR(64),
  is_helpful BOOLEAN,
  remark TEXT,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_slc_feedbacks_tenant_id (tenant_id),
  INDEX ix_slc_feedbacks_user_id (user_id),
  CONSTRAINT fk_slc_feedbacks_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE,
  CONSTRAINT fk_slc_feedbacks_chat FOREIGN KEY (question_id) REFERENCES slc_chat_logs(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_knowledge_packages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  name VARCHAR(100) NOT NULL,
  region VARCHAR(50),
  version VARCHAR(40) NOT NULL DEFAULT 'v1.0',
  description TEXT,
  categories JSON,
  dify_dataset_id VARCHAR(120),
  ragflow_dataset_id VARCHAR(120),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX ix_slc_knowledge_packages_tenant_id (tenant_id),
  CONSTRAINT fk_slc_packages_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS slc_test_questions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  tenant_id INT NOT NULL,
  question VARCHAR(500) NOT NULL,
  expected_points JSON,
  category VARCHAR(60),
  region VARCHAR(80) NOT NULL DEFAULT '陕西',
  difficulty VARCHAR(20) NOT NULL DEFAULT 'normal',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX ix_slc_test_questions_tenant_id (tenant_id),
  CONSTRAINT fk_slc_tests_tenant FOREIGN KEY (tenant_id) REFERENCES slc_tenants(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
