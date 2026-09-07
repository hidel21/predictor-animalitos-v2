-- Ejecutar cada bloque por separado si el cliente no admite varias sentencias.
-- Conserva variantes de ranking/probabilidades; no modifica emisiones previas.
CREATE INDEX IF NOT EXISTS idx_predicciones_sorteo_modelo
ON public.predicciones (sorteo_id, modelo);

-- SIGUIENTE BLOQUE
CREATE OR REPLACE FUNCTION public.evitar_prediccion_repetida()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public
AS $$
BEGIN
    IF NEW.sorteo_id IS NULL THEN
        RETURN NEW;
    END IF;
    -- Misma clave usada por guardar_prediccion en la aplicación.
    PERFORM pg_advisory_xact_lock(72842, NEW.sorteo_id);
    IF EXISTS (
        SELECT 1 FROM public.predicciones p
        WHERE p.sorteo_id = NEW.sorteo_id
          AND p.modelo IS NOT DISTINCT FROM NEW.modelo
          AND p.top1 IS NOT DISTINCT FROM NEW.top1
          AND p.top3 IS NOT DISTINCT FROM NEW.top3
          AND p.top5 IS NOT DISTINCT FROM NEW.top5
          AND p.probs IS NOT DISTINCT FROM NEW.probs
    ) THEN
        RETURN NULL;
    END IF;
    RETURN NEW;
END;
$$;

-- SIGUIENTE BLOQUE
CREATE OR REPLACE TRIGGER prevenir_predicciones_repetidas
BEFORE INSERT ON public.predicciones
FOR EACH ROW EXECUTE FUNCTION public.evitar_prediccion_repetida();
