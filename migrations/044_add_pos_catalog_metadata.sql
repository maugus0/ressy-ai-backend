-- Migration: Add POS catalog metadata to internal catalog tables
-- Description: Adds source metadata, active flags, text customizations, and item-level selection overrides.

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'is_active'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER is_available'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN catalog_source VARCHAR(32) NOT NULL DEFAULT ''INTERNAL'' AFTER is_active'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'source_name'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN source_name VARCHAR(255) NULL AFTER catalog_source'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'source_description'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN source_description TEXT NULL AFTER source_name'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'source_category'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN source_category VARCHAR(100) NULL AFTER source_description'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND COLUMN_NAME = 'source_sub_category'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD COLUMN source_sub_category VARCHAR(100) NULL AFTER source_category'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND INDEX_NAME = 'idx_restaurant_active_available'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD INDEX idx_restaurant_active_available (restaurant_id, is_active, is_available)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menus' AND INDEX_NAME = 'idx_catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menus ADD INDEX idx_catalog_source (catalog_source)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'is_active'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER is_available'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN catalog_source VARCHAR(32) NOT NULL DEFAULT ''INTERNAL'' AFTER is_active'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'source_name'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN source_name VARCHAR(150) NULL AFTER catalog_source'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'source_description'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN source_description TEXT NULL AFTER source_name'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'input_type'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN input_type VARCHAR(20) NOT NULL DEFAULT ''SELECT'' AFTER source_description'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'text_required'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN text_required BOOLEAN NOT NULL DEFAULT FALSE AFTER input_type'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND COLUMN_NAME = 'max_text_length'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD COLUMN max_text_length INT NULL AFTER text_required'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND INDEX_NAME = 'idx_mog_active'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD INDEX idx_mog_active (restaurant_id, is_active, is_available)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND INDEX_NAME = 'idx_mog_catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD INDEX idx_mog_catalog_source (catalog_source)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Groups' AND INDEX_NAME = 'idx_mog_input_type'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Groups ADD INDEX idx_mog_input_type (input_type)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Values' AND COLUMN_NAME = 'is_active'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Values ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER is_available'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Values' AND COLUMN_NAME = 'catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Values ADD COLUMN catalog_source VARCHAR(32) NOT NULL DEFAULT ''INTERNAL'' AFTER is_active'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Values' AND COLUMN_NAME = 'source_name'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Values ADD COLUMN source_name VARCHAR(150) NULL AFTER catalog_source'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Values' AND INDEX_NAME = 'idx_mov_active'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Values ADD INDEX idx_mov_active (group_id, is_active, is_available)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Option_Values' AND INDEX_NAME = 'idx_mov_catalog_source'
    ),
    'DO 0',
    'ALTER TABLE Menu_Option_Values ADD INDEX idx_mov_catalog_source (catalog_source)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Menu_Item_Option_Groups' AND COLUMN_NAME = 'selection_type_override'
    ),
    'DO 0',
    'ALTER TABLE Menu_Item_Option_Groups ADD COLUMN selection_type_override VARCHAR(20) NULL AFTER group_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND COLUMN_NAME = 'option_group_id'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD COLUMN option_group_id INT NULL AFTER order_item_id'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND COLUMN_NAME = 'input_type_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD COLUMN input_type_snapshot VARCHAR(20) NULL AFTER option_group_name_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND COLUMN_NAME = 'free_text_value'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD COLUMN free_text_value TEXT NULL AFTER option_value_name_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND COLUMN_NAME = 'external_group_id_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD COLUMN external_group_id_snapshot VARCHAR(255) NULL AFTER free_text_value'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND COLUMN_NAME = 'external_value_id_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD COLUMN external_value_id_snapshot VARCHAR(255) NULL AFTER external_group_id_snapshot'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Order_Item_Options_Snapshots'
          AND CONSTRAINT_NAME = 'fk_order_item_option_group_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD CONSTRAINT fk_order_item_option_group_snapshot FOREIGN KEY (option_group_id) REFERENCES Menu_Option_Groups(id) ON DELETE SET NULL ON UPDATE CASCADE'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Order_Item_Options_Snapshots' AND INDEX_NAME = 'idx_oio_option_group'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Options_Snapshots ADD INDEX idx_oio_option_group (option_group_id)'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
