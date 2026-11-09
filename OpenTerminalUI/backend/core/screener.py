from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


@dataclass(frozen=True)
class Rule:
    """
    Represents a single screening condition/filter rule to be evaluated against a data series.

    Attributes:
        field (str): The column name or field identifier to evaluate in the data row.
        op (str): The comparison operator (e.g., '>', '<', '>=', '<=', '==', '!=').
        value (Any): The threshold or value to compare the field's value against.
    """
    field: str
    op: str
    value: Any

    def evaluate(self, row: pd.Series) -> bool:
        """
        Evaluates whether a single row (pandas Series) satisfies this rule.

        Args:
            row (pd.Series): A row of stock data or metrics.

        Returns:
            bool: True if the row satisfies the comparison, False otherwise.
                  Returns False if the field is missing, null, or if evaluation errors out.
        """
        if self.op not in _OPS:
            raise ValueError(f"Unsupported operator: {self.op}")
        lhs = row.get(self.field)
        if lhs is None or pd.isna(lhs):
            return False
        try:
            return _OPS[self.op](lhs, self.value)
        except (TypeError, ValueError):
            return False


class ScreenerEngine:
    """
    Engine to apply filtering rules and ranking on stock datasets (pandas DataFrames).
    """
    def __init__(self, dataframe: pd.DataFrame) -> None:
        """
        Initializes the ScreenerEngine with a copy of the target DataFrame.

        Args:
            dataframe (pd.DataFrame): The input dataset to screen.
        """
        self.df = dataframe.copy()

    def apply_rules(self, rules: list[Rule]) -> pd.DataFrame:
        """
        Applies a list of filtering Rules sequentially to filter rows in the DataFrame.

        Args:
            rules (list[Rule]): A list of Rule instances representing filters.

        Returns:
            pd.DataFrame: A new DataFrame containing only rows that passed all filters.
        """
        if self.df.empty:
            return self.df
        mask = pd.Series([True] * len(self.df), index=self.df.index)
        for rule in rules:
            mask &= self.df.apply(rule.evaluate, axis=1)
        return self.df[mask].copy()

    def rank(self, df: pd.DataFrame, by: str, ascending: bool = False, top_n: int = 25) -> pd.DataFrame:
        """
        Sorts the filtered DataFrame by a specified metric and returns the top N rows.

        Args:
            df (pd.DataFrame): The DataFrame to rank.
            by (str): The column name to sort by.
            ascending (bool): Sort direction. Defaults to False (descending).
            top_n (int): The maximum number of rows to return. Defaults to 25.

        Returns:
            pd.DataFrame: A sorted copy of the DataFrame limited to top_n records.
        """
        if by not in df.columns:
            return df.head(top_n)
        return df.sort_values(by=by, ascending=ascending).head(top_n).copy()
