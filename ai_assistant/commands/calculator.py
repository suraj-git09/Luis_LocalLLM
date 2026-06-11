import ast
import operator
import re

from commands.base import Command


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


class _SafeEvaluator(ast.NodeVisitor):
    def visit(self, node):
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            op_type = type(node.op)
            if op_type not in _ALLOWED_OPERATORS:
                raise ValueError("Unsupported operator")
            return _ALLOWED_OPERATORS[op_type](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_OPERATORS:
            return _ALLOWED_OPERATORS[type(node.op)](self.visit(node.operand))
        raise ValueError("Unsupported expression")


def _safe_eval(expression: str) -> float:
    tree = ast.parse(expression, mode="eval")
    return _SafeEvaluator().visit(tree)


class CalculatorCommand(Command):
    name = "calculate"
    description = "Performs basic math calculations"

    async def execute(self, user_input: str, context: dict) -> str | None:
        lower_input = user_input.lower()
        had_explicit_math_intent = any(
            w in lower_input for w in ["calculate", "solve", "compute"]
        )

        text = lower_input
        for word in ["calculate", "what is", "solve"]:
            text = text.replace(word, "")

        expression = text.strip()
        expression = re.sub(r"[^0-9+\-*/().%\s]", "", expression)
        expression = expression.strip()  # clean leftover whitespace after removing letters/words

        if not expression:
            if had_explicit_math_intent:
                return "Please provide a math expression to calculate."
            return None

        has_digit = bool(re.search(r"\d", expression))
        has_op = bool(re.search(r"[\+\-\*/%]", expression))

        if not (has_digit and has_op):
            # No plausible math expression remains.
            # Only show calculator error if the user explicitly said "calculate ...".
            if had_explicit_math_intent:
                return "Please provide a math expression to calculate."
            return None

        try:
            result = _safe_eval(expression)

            # Even if it parsed, be conservative when user did not explicitly ask for calculation.
            # Avoid hijacking year ranges, ratings (4/5 → 0.8), ticket ranges, etc.
            if not had_explicit_math_intent:
                cleaned_no_space = expression.replace(" ", "")
                # Year range
                if re.match(r"^\d{4}\s*-\s*\d{4}$", cleaned_no_space):
                    return None
                # Rating-like X/Y that evaluated to a small decimal (typical for / division of small ints)
                if re.match(r"^\d+/\d+$", cleaned_no_space) and isinstance(result, float) and 0 < result < 2:
                    return None
                # Very short math fragment inside a longer natural language question
                if len(user_input) > 25 and len(expression) <= 10:
                    return None

            return f"Result: {result}"
        except Exception:
            if had_explicit_math_intent:
                return "Sorry, I could not calculate that. Use numbers and +, -, *, /, %, or parentheses."
            return None