-- Migration to remove estadisticas column from recursos table
-- This migration makes the estadisticas column optional by allowing NULL values
-- If you want to completely remove the column, uncomment the ALTER TABLE DROP COLUMN statement

-- Option 1: Make estadisticas nullable (safer, preserves existing data)
ALTER TABLE recursos MODIFY COLUMN estadisticas VARCHAR(255) NULL;

-- Option 2: Completely remove the column (uncomment if you want to remove it entirely)
-- ALTER TABLE recursos DROP COLUMN estadisticas;
