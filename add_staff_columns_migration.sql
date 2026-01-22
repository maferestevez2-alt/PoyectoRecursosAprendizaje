-- Migración para agregar columnas necesarias al sistema de registro automático

-- Agregar no_empleado a orientadores si no existe
ALTER TABLE orientadores 
ADD COLUMN IF NOT EXISTS no_empleado VARCHAR(50) AFTER id;

-- Agregar grupos_encargado a orientadores si no existe
ALTER TABLE orientadores 
ADD COLUMN IF NOT EXISTS grupos_encargado VARCHAR(255) AFTER apellido_materno;

-- Agregar no_empleado a directivos si no existe
ALTER TABLE directivos 
ADD COLUMN IF NOT EXISTS no_empleado VARCHAR(50) AFTER id;

-- Agregar puesto a directivos si no existe  
ALTER TABLE directivos 
ADD COLUMN IF NOT EXISTS puesto VARCHAR(100) AFTER apellido_materno;

-- Nota: Si las columnas telefono, correo, cargo ya existen en las tablas pero no se usan,
-- puedes eliminarlas después de verificar que no afecten otros sistemas
