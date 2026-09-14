"""
validation.py
==============
Post-cleaning validation checks. These run AFTER cleaning.py and BEFORE
the data is loaded into MySQL. The goal is a fast, structured report you
can inspect (or fail the pipeline on) before touching the database.

Every check function returns a dict — this makes it trivial to log
results as JSON, assert on them in a test, or fail the pipeline if a
critical check does not pass.
"""

import logging
import pandas as pd

logger = logging.getLogger(__name__)


def check_nulls(df: pd.DataFrame, required_cols: list, table_name: str) -> dict:
    result = {"table": table_name, "check": "required_columns_not_null", "passed": True, "details": {}}
    for col in required_cols:
        n_null = int(df[col].isna().sum())
        result["details"][col] = n_null
        if n_null > 0:
            result["passed"] = False
    return result


def check_unique_key(df: pd.DataFrame, key_cols: list, table_name: str) -> dict:
    dup_count = int(df.duplicated(subset=key_cols).sum())
    return {
        "table": table_name,
        "check": f"unique_key({','.join(key_cols)})",
        "passed": dup_count == 0,
        "details": {"duplicate_rows": dup_count},
    }


def check_referential_integrity(child_df: pd.DataFrame, child_col: str,
                                 parent_ids: set, table_name: str) -> dict:
    orphans = int((~child_df[child_col].isin(parent_ids)).sum())
    return {
        "table": table_name,
        "check": f"fk_integrity({child_col})",
        "passed": orphans == 0,
        "details": {"orphan_rows": orphans},
    }


def check_numeric_range(df: pd.DataFrame, col: str, min_val=None, max_val=None,
                         table_name: str = "") -> dict:
    series = df[col]
    below = int((series < min_val).sum()) if min_val is not None else 0
    above = int((series > max_val).sum()) if max_val is not None else 0
    return {
        "table": table_name,
        "check": f"numeric_range({col})",
        "passed": (below == 0 and above == 0),
        "details": {"below_min": below, "above_max": above},
    }


def check_date_order(df: pd.DataFrame, earlier_col: str, later_col: str,
                      table_name: str) -> dict:
    valid_rows = df[[earlier_col, later_col]].dropna()
    violations = int((valid_rows[later_col] < valid_rows[earlier_col]).sum())
    return {
        "table": table_name,
        "check": f"date_order({earlier_col} <= {later_col})",
        "passed": violations == 0,
        "details": {"violations": violations},
    }


def run_report(checks: list) -> pd.DataFrame:
    """
    Turn a list of check-result dicts into a tidy summary DataFrame and
    log a pass/fail line for each. Returns the DataFrame so the caller
    can decide whether to abort the pipeline (e.g. if any critical
    check failed).
    """
    report = pd.DataFrame(checks)
    for _, row in report.iterrows():
        level = logging.INFO if row["passed"] else logging.WARNING
        logger.log(level, "[%s] %s -> %s | %s",
                   row["table"], row["check"],
                   "PASS" if row["passed"] else "FAIL", row["details"])
    return report


if __name__ == "__main__":
    # Minimal smoke test with synthetic data — proves the functions work
    # in isolation, independent of the real dataset or a DB connection.
    logging.basicConfig(level=logging.INFO)
    sample = pd.DataFrame({
        "order_id": ["a", "a", "b"],
        "customer_id": ["c1", "c1", "c2"],
        "price": [10.0, -5.0, 20.0],
    })
    checks = [
        check_nulls(sample, ["order_id", "customer_id"], "sample"),
        check_unique_key(sample, ["order_id"], "sample"),
        check_numeric_range(sample, "price", min_val=0, table_name="sample"),
    ]
    run_report(checks)
