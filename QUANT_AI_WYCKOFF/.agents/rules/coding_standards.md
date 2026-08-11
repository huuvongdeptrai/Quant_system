# Pragmatic Clean Code & Modern Python Standards

All Python code written in this project must strictly adhere to the following 5 principles:

## 1. Self-documenting Code via Type Hints
- Use strict type hinting for all function arguments and return types.
- Example: `def smart_fetch(self, symbol: str, timeframe: int, is_boot: bool = False) -> pd.DataFrame | None:`
- Rely on language syntax instead of verbose docstrings to explain what a function receives and returns.

## 2. Contextual Comments (Why, not What)
- Code should explain *what* it does. Comments must only explain *why* it does it.
- Use comments to explain external factors, specific domain knowledge (like DST handling), or technical workarounds.

## 3. Early Return & Defensive Programming
- Avoid deep `if...else` nesting (Anti-pattern).
- Validate inputs early. If invalid, log the error and `return None` or raise an exception immediately.
- Example:
  ```python
  if rates is None or len(rates) == 0:
      logger.error("No rates received from MT5")
      return None
  ```

## 4. K.I.S.S (Keep It Simple, Stupid)
- Do not reinvent the wheel.
- Use `loguru` for all logging instead of the built-in `logging` module or raw `print()` statements. Import it via `from loguru import logger`.

## 5. Actionable TODOs
- Leave breadcrumbs for future complex logic using `# TODO: [description]`.
- This ensures the current code flow is not interrupted while keeping track of technical debt.
