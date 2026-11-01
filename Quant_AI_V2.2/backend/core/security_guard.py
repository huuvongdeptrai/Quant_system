"""
Security Guard Module - AST-Based Strategy Linter
================================================
Static screening for common dangerous operations before executing trusted strategies.
This is not an OS sandbox and does not make untrusted Python safe to execute.
"""

import ast
from typing import Tuple

# Danh sách các thư viện bị cấm tiệt (Truy cập hệ điều hành, mạng, tiến trình, đánh cắp file)
BANNED_MODULES = {
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "telnetlib",
    "pty",
    "ctypes",
    "winreg",
    "_winapi",
    "posix",
    "platform",
    "pathlib",
    "tempfile",
    "inspect",
    "importlib",
    "multiprocessing",
    "threading",
    "signal",
}

# Danh sách các hàm / thuộc tính nội tại nguy hiểm
BANNED_CALLS = {
    "eval",
    "exec",
    "open",
    "__import__",
    "compile",
    "globals",
    "locals",
    "vars",
    "exit",
    "quit",
    "input",
    "breakpoint",
    "getattr", "setattr", "delattr", "read_pickle", "to_pickle",
    "read_csv", "to_csv", "read_json", "to_json", "to_sql", "read_sql",
    "load", "save", "dump", "dumps", "system", "popen",
}

# Các kỹ thuật vượt rào Sandbox qua thuộc tính Dunder (Python Sandbox Escape)
BANNED_ATTRIBUTES = {
    "__subclasses__",
    "__bases__",
    "__mro__",
    "__code__",
    "__globals__",
    "__builtins__",
    "__import__",
    "__dict__", "__getattribute__",
}


class StrategySecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations = []

    def visit_Import(self, node):
        for alias in node.names:
            root_mod = alias.name.split(".")[0]
            if root_mod in BANNED_MODULES:
                self.violations.append(
                    f"Không được phép import thư viện nguy hiểm '{alias.name}' (Dòng {node.lineno})"
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            root_mod = node.module.split(".")[0]
            if root_mod in BANNED_MODULES:
                self.violations.append(
                    f"Không được phép import từ thư viện nguy hiểm '{node.module}' (Dòng {node.lineno})"
                )
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in BANNED_CALLS:
                self.violations.append(
                    f"Không được phép gọi hàm nhạy cảm '{node.func.id}()' (Dòng {node.lineno})"
                )
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in BANNED_CALLS:
                self.violations.append(
                    f"Không được phép gọi phương thức '{node.func.attr}()' (Dòng {node.lineno})"
                )
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in BANNED_ATTRIBUTES:
            self.violations.append(
                f"Phát hiện hành vi Sandbox Escape qua thuộc tính dunder '{node.attr}' (Dòng {node.lineno})"
            )
        self.generic_visit(node)


def validate_strategy_code(code_str: str) -> Tuple[bool, str]:
    """
    Phân tích AST để tìm các thao tác bị cấm trước khi chạy mã tin cậy.

    Returns:
        (is_safe: bool, reason: str)
    """
    if not code_str or not code_str.strip():
        return True, ""

    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return False, f"Lỗi cú pháp Python tại dòng {e.lineno}: {e.msg}"
    except Exception as e:
        return False, f"Không thể phân tích cú pháp mã nguồn: {str(e)}"

    visitor = StrategySecurityVisitor()
    visitor.visit(tree)

    if visitor.violations:
        return False, "; ".join(visitor.violations)

    return True, "Static checks passed; execute trusted strategy code only"
