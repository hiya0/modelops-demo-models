from sklearn import metrics
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay
from teradataml import DataFrame, copy_to_sql
from aoa import (
    record_evaluation_stats,
    save_plot,
    aoa_create_context,
    ModelContext
)

import joblib
import json
import numpy as np
import pandas as pd


def evaluate(context: ModelContext, **kwargs):

    aoa_create_context()

    model = joblib.load(f"{context.artifact_input_path}/model.joblib")

    feature_names = context.dataset_info.feature_names
    target_name = context.dataset_info.target_names[0]

    test_df = DataFrame.from_query(context.dataset_info.sql)
    test_pdf = test_df.to_pandas(all_rows=True)

    X_test = test_pdf[feature_names]
    y_test = test_pdf[target_name]

    print("Scoring")
    y_pred = model.predict(X_test)

    y_pred_tdf = pd.DataFrame(y_pred, columns=[target_name])
    y_pred_tdf["PatientId"] = test_pdf["PatientId"].values

    evaluation = {
        'Accuracy': '{:.2f}'.format(metrics.accuracy_score(y_test, y_pred)),
        'Recall': '{:.2f}'.format(metrics.recall_score(y_test, y_pred)),
        'Precision': '{:.2f}'.format(metrics.precision_score(y_test, y_pred)),
        'f1-score': '{:.2f}'.format(metrics.f1_score(y_test, y_pred))
    }

    with open(f"{context.artifact_output_path}/metrics.json", "w+") as f:
        json.dump(evaluation, f)

    ConfusionMatrixDisplay.from_estimator(model, X_test, y_test)
    save_plot('Confusion Matrix', context=context)

    RocCurveDisplay.from_estimator(model, X_test, y_test)
    save_plot('ROC Curve', context=context)

    from xgboost import plot_importance
    model["xgb"].get_booster().feature_names = feature_names
    plot_importance(model["xgb"].get_booster(), max_num_features=10)
    save_plot("feature_importance.png", context=context)

    feature_importance = model["xgb"].get_booster().get_score(importance_type="weight")

    predictions_table = "predictions_tmp"
    copy_to_sql(df=y_pred_tdf, table_name=predictions_table, index=False, if_exists="replace", temporary=True)

    record_evaluation_stats(features_df=test_df,
                            predicted_df=DataFrame.from_query(f"SELECT * FROM {predictions_table}"),
                            feature_importance=feature_importance,
                            context=context)

    print("All done!")
