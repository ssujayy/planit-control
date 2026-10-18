-- Preserve legacy report categories while supporting the shared reporting rules.
ALTER TABLE crew_reports DROP CONSTRAINT IF EXISTS crew_reports_category_check;
ALTER TABLE crew_reports ADD CONSTRAINT crew_reports_category_check
    CHECK (category IN ('wildlife','water','access','fire','other','heat','lightning','flooding','mud'));

ALTER TABLE model_predictions ALTER COLUMN score DROP NOT NULL;
ALTER TABLE model_predictions ADD COLUMN status text NOT NULL DEFAULT 'available'
    CHECK (status IN ('available', 'unavailable'));
ALTER TABLE model_predictions ADD COLUMN probability double precision
    CHECK (probability BETWEEN 0 AND 1);
ALTER TABLE model_predictions ADD COLUMN outside_training_range jsonb NOT NULL DEFAULT '[]'
    CHECK (jsonb_typeof(outside_training_range) = 'array');
ALTER TABLE model_predictions ADD COLUMN outside_training_counties boolean;
ALTER TABLE model_predictions ADD CONSTRAINT model_prediction_availability
    CHECK ((status = 'available' AND score IS NOT NULL) OR (status = 'unavailable' AND score IS NULL));
