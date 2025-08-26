-- Crea workflow de ejemplo
INSERT INTO discovery_workflows(id, name, mode)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'Workflow Demo', 'manual');

-- Crea steps
INSERT INTO discovery_steps(id, workflow_id, name, "order", max_visits)
VALUES
  ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'step_1_add_valor', 1, 3),
  ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'step_2_loop_or_next', 2, 1),
  ('10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000001', 'step_3_finish', 3, 1);
