-- Database Migration for Personalized Welcome and Resource Filtering
-- Run this script to update your database schema

-- 1. Add columns to usuarios table for linking to profiles
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS perfil_id INT;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS nombre_completo VARCHAR(255);

-- 2. Add filtering columns to recursos table
ALTER TABLE recursos ADD COLUMN IF NOT EXISTS grupo VARCHAR(10);
ALTER TABLE recursos ADD COLUMN IF NOT EXISTS semestre INT;
ALTER TABLE recursos ADD COLUMN IF NOT EXISTS turno VARCHAR(20);

-- 3. Create table for subject assignments from Excel
CREATE TABLE IF NOT EXISTS materias_asignadas (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nombre_materia VARCHAR(255),
    semestre INT,
    no_empleado INT,
    grupo VARCHAR(10),
    INDEX idx_empleado (no_empleado),
    INDEX idx_grupo (grupo),
    INDEX idx_semestre (semestre)
);

-- 4. Update existing usuarios with their full names
-- For students (alumnos)
UPDATE usuarios u
INNER JOIN alumnos a ON u.usuario = a.no_control
SET u.nombre_completo = CONCAT(a.nombre, ' ', a.apellido_paterno, ' ', a.apellido_materno),
    u.perfil_id = a.id
WHERE u.rol = 'alumno';

-- For teachers (docentes)
UPDATE usuarios u
INNER JOIN docentes d ON u.usuario = d.no_empleado
SET u.nombre_completo = CONCAT(d.nombre, ' ', d.apellido_paterno, ' ', d.apellido_materno),
    u.perfil_id = d.id
WHERE u.rol = 'docente';

-- For orientadores
UPDATE usuarios u
INNER JOIN orientadores o ON u.usuario = o.id
SET u.nombre_completo = CONCAT(o.nombre, ' ', o.apellido_paterno, ' ', o.apellido_materno),
    u.perfil_id = o.id
WHERE u.rol = 'orientador';

-- For directivos
UPDATE usuarios u
INNER JOIN directivos d ON u.usuario = d.id
SET u.nombre_completo = CONCAT(d.nombre, ' ', d.apellido_paterno, ' ', d.apellido_materno),
    u.perfil_id = d.id
WHERE u.rol = 'directivo';

-- Note: Admin users might not have a profile table, set manually if needed
