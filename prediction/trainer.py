"""
Offline XGBoost training script. Run once after collecting session data.
Usage: python -m prediction.trainer
Output: models/mistake_predictor.pkl
"""
import os
import glob
import pickle
import time

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from prediction.features import extract_features_from_df
from prediction.labels import label_dataframe, MISTAKE_CLASSES, CLASS_TO_INT

SESSIONS_DIR = os.path.join("data", "sessions")
MODEL_PATH = os.path.join("models", "mistake_predictor.pkl")


def load_sessions() -> pd.DataFrame:
    files = glob.glob(os.path.join(SESSIONS_DIR, "*.csv"))
    if not files:
        raise FileNotFoundError(f"No session CSVs found in {SESSIONS_DIR}")
    print(f"Loading {len(files)} session file(s)...")
    dfs = []
    for f in files:
        df = pd.read_csv(f)
        dfs.append(df)
        print(f"  {os.path.basename(f)}: {len(df)} frames")
    combined = pd.concat(dfs, ignore_index=True)
    print(f"Total frames: {len(combined)}")
    return combined


def train():
    df = load_sessions()

    print("\nExtracting features...")
    features = extract_features_from_df(df)
    print(f"Feature rows: {len(features)}")

    print("Auto-labeling...")
    labels = label_dataframe(df, features)

    counts = labels.value_counts().sort_index()
    for idx, count in counts.items():
        print(f"  {MISTAKE_CLASSES[idx]}: {count} frames ({count/len(labels)*100:.1f}%)")

    X = features.values
    y_raw = labels.values

    # Remap to contiguous class indices (handles sparse class presence, e.g. only CLEAN + SNAP_RISK)
    present_classes = sorted(np.unique(y_raw).tolist())
    remap = {old: new for new, old in enumerate(present_classes)}
    class_names = [MISTAKE_CLASSES[i] for i in present_classes]
    y = np.array([remap[v] for v in y_raw])
    print(f"  Classes in training data: {class_names}")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Upweight minority classes to counter 98%+ CLEAN dominance
    # Moderate upweighting — full inverse weighting caused too many false positives
    class_counts = np.bincount(y_train)
    max_count = class_counts.max()
    sample_weights = np.array([np.sqrt(max_count / class_counts[label]) for label in y_train])

    print(f"\nTraining XGBoost on {len(X_train)} samples...")
    n_classes = len(class_names)
    xgb_params = dict(
        n_estimators=100,
        max_depth=5,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        n_jobs=-1,
        random_state=42,
    )
    if n_classes == 2:
        xgb_params["objective"] = "binary:logistic"
        xgb_params["eval_metric"] = "logloss"
    else:
        xgb_params["objective"] = "multi:softprob"
        xgb_params["num_class"] = n_classes
        xgb_params["eval_metric"] = "mlogloss"
    model = XGBClassifier(**xgb_params)
    model.fit(X_train, y_train, sample_weight=sample_weights)

    print("\nEvaluating on test set...")
    y_pred = model.predict(X_test)
    print(classification_report(y_test, y_pred, target_names=class_names, zero_division=0))

    # Inference speed check
    sample = X_test[:1]
    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        model.predict(sample)
        times.append((time.perf_counter() - t0) * 1000)
    avg_ms = np.mean(times)
    status = "OK" if avg_ms < 5 else "WARNING: exceeds 5ms target"
    print(f"Inference time (avg over 100 runs): {avg_ms:.2f}ms [{status}]")

    os.makedirs("models", exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump({"model": model, "class_names": class_names}, f)
    print(f"\nModel saved to: {os.path.abspath(MODEL_PATH)}")


if __name__ == "__main__":
    train()
