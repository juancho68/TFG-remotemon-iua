# ml_utils.py (esta implementación considera muestras cada 30 segundos)

import numpy as np
from sklearn.ensemble import IsolationForest

# Modelos entrenados dinámicamente
models = {
    "temperature": None,
    "humidity": None
}

# Buffers circulares (últimos ~150 minutos)
MAX_BUF = 300
buffers = {
    "temperature": [],
    "humidity": []
}

# Estadística incremental (EWMA + EWVAR)
stats = {
    "temperature": {"ewma": None, "ewvar": None},
    "humidity": {"ewma": None, "ewvar": None}
}

ALPHA = 0.15           # suavizado
RETRAIN_EVERY = 20     # cada 10 minutos

###############################################################
# EWMA + varianza exponencial
###############################################################
def ewma_update(name, x):
    st = stats[name]

    if st["ewma"] is None:
        st["ewma"] = x
        st["ewvar"] = 0.0
    else:
        prev_mean = st["ewma"]
        st["ewma"] = ALPHA * x + (1 - ALPHA) * st["ewma"]
        st["ewvar"] = (1 - ALPHA) * (st["ewvar"] + ALPHA * (x - prev_mean) ** 2)

    mean = st["ewma"]
    std = np.sqrt(st["ewvar"]) if st["ewvar"] > 0 else 0.001
    return mean, std

###############################################################
# Isolation Forest
###############################################################
def train_iforest(var_name: str, values: list[float]):
    if len(values) < 20:
        return None

    X = np.array(values).reshape(-1, 1)

    model = IsolationForest(
        n_estimators=150,
        contamination=0.02,
        max_features=1,
        random_state=42
    )
    model.fit(X)
    models[var_name] = model
    return model

def predict_anomaly(var_name: str, value: float):
    model = models.get(var_name)
    if model is None:
        return False, 0.0

    pred = model.predict([[value]])[0]
    score = model.score_samples([[value]])[0]
    return pred == -1, float(score)

###############################################################
# Proceso Principal
###############################################################
def update_and_predict(temp: float, hum: float):
    result = {}

    ###########################################################
    # Temperatura
    ###########################################################
    if temp is not None:
        buf = buffers["temperature"]
        buf.append(temp)
        buffers["temperature"] = buf[-MAX_BUF:]

        # Estadístico incremental
        mean_t, std_t = ewma_update("temperature", temp)
        dyn_min_t = mean_t - 3 * std_t
        dyn_max_t = mean_t + 3 * std_t

        # Reentrenar IF cada 20 muestras
        if len(buf) % RETRAIN_EVERY == 0 or models["temperature"] is None:
            train_iforest("temperature", buf)

        ml_anom_t, ml_score_t = predict_anomaly("temperature", temp)
    else:
        ml_anom_t = False
        ml_score_t = 0.0
        mean_t = std_t = dyn_min_t = dyn_max_t = None

    ###########################################################
    # Humedad
    ###########################################################
    if hum is not None:
        buf = buffers["humidity"]
        buf.append(hum)
        buffers["humidity"] = buf[-MAX_BUF:]

        mean_h, std_h = ewma_update("humidity", hum)
        dyn_min_h = mean_h - 3 * std_h
        dyn_max_h = mean_h + 3 * std_h

        if len(buf) % RETRAIN_EVERY == 0 or models["humidity"] is None:
            train_iforest("humidity", buf)

        ml_anom_h, ml_score_h = predict_anomaly("humidity", hum)
    else:
        ml_anom_h = False
        ml_score_h = 0.0
        mean_h = std_h = dyn_min_h = dyn_max_h = None

    ###########################################################
    # Resultado final
    ###########################################################
    return {
        "ml_temp_anomaly": ml_anom_t,
        "ml_hum_anomaly": ml_anom_h,
        "ml_score_temp": ml_score_t,
        "ml_score_hum": ml_score_h,

        "expected_temp": float(mean_t) if mean_t else None,
        "expected_hum": float(mean_h) if mean_h else None,

        "calculated_thresholds": {
            "temp_min": float(dyn_min_t) if dyn_min_t else None,
            "temp_max": float(dyn_max_t) if dyn_max_t else None,
            "hum_min": float(dyn_min_h) if dyn_min_h else None,
            "hum_max": float(dyn_max_h) if dyn_max_h else None,
        }
    }
