-- Migration: Add POS order management snapshot fields
-- Description: Persists external item IDs on order snapshots and external payment IDs on POS sync rows.

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Order_Item_Snapshots'
          AND COLUMN_NAME = 'external_item_id_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Snapshots ADD COLUMN external_item_id_snapshot VARCHAR(255) NULL AFTER menu_item_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Order_Item_Snapshots'
          AND INDEX_NAME = 'idx_oi_external_item_snapshot'
    ),
    'DO 0',
    'ALTER TABLE Order_Item_Snapshots ADD INDEX idx_oi_external_item_snapshot (external_item_id_snapshot)'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Order_POS_Sync'
          AND COLUMN_NAME = 'external_payment_id'
    ),
    'DO 0',
    'ALTER TABLE Order_POS_Sync ADD COLUMN external_payment_id VARCHAR(255) NULL AFTER external_order_id'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql = IF(
    EXISTS (
        SELECT 1
        FROM INFORMATION_SCHEMA.STATISTICS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'Order_POS_Sync'
          AND INDEX_NAME = 'idx_external_payment_id'
    ),
    'DO 0',
    'ALTER TABLE Order_POS_Sync ADD INDEX idx_external_payment_id (external_payment_id)'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
