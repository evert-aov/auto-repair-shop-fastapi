-- SEED DATA para CU10: Workshops y Specialties
-- Ejecutar después de: alembic upgrade head

-- 1. Crear especialidades
INSERT INTO specialties (name) VALUES
('battery'),
('tire'),
('engine'),
('ac'),
('transmission'),
('towing'),
('locksmith'),
('general')
ON CONFLICT DO NOTHING;

-- 2. Crear usuario dueño de taller (si no existe)
-- Asumir que hay un usuario con id = '12345678-1234-1234-1234-123456789abc'
-- En producción usar un usuario admin o crear uno

-- 3. Crear talleres en ubicación similar a la prueba
INSERT INTO workshops (id, owner_user_id, business_name, latitude, longitude, commission_rate, rating_avg, is_active)
VALUES
  ('11111111-1111-1111-1111-111111111111'::uuid, '12345678-1234-1234-1234-123456789abc'::uuid, 'Taller Especialista en Llantas', -17.75, -63.20, 10.0, 4.8, true),
  ('22222222-2222-2222-2222-222222222222'::uuid, '12345678-1234-1234-1234-123456789abc'::uuid, 'Taller Rápido Servicios', -17.85, -63.25, 12.0, 4.2, true),
  ('33333333-3333-3333-3333-333333333333'::uuid, '12345678-1234-1234-1234-123456789abc'::uuid, 'Taller General "Juan y Cia"', -17.80, -63.15, 10.0, 3.9, true)
ON CONFLICT DO NOTHING;

-- 4. Asignar especialidades a talleres
INSERT INTO workshop_specialties (workshop_id, specialty_id, is_mobile) VALUES
  ('11111111-1111-1111-1111-111111111111'::uuid, (SELECT id FROM specialties WHERE name = 'tire'), false),
  ('22222222-2222-2222-2222-222222222222'::uuid, (SELECT id FROM specialties WHERE name = 'tire'), false),
  ('33333333-3333-3333-3333-333333333333'::uuid, (SELECT id FROM specialties WHERE name = 'general'), true)
ON CONFLICT DO NOTHING;

-- 5. Crear técnicos disponibles
-- Asumir que hay usuarios técnicos con estos ids
INSERT INTO technicians (id, user_id, workshop_id, is_available) VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid, '12345678-1234-1234-1234-123456789bbb'::uuid, '11111111-1111-1111-1111-111111111111'::uuid, true),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'::uuid, '12345678-1234-1234-1234-123456789ccc'::uuid, '22222222-2222-2222-2222-222222222222'::uuid, true),
  ('cccccccc-cccc-cccc-cccc-cccccccccccc'::uuid, '12345678-1234-1234-1234-123456789ddd'::uuid, '33333333-3333-3333-3333-333333333333'::uuid, true)
ON CONFLICT DO NOTHING;

-- Verificación
SELECT COUNT(*) as specialty_count FROM specialties;
SELECT COUNT(*) as workshop_count FROM workshops;
SELECT COUNT(*) as technician_count FROM technicians;
