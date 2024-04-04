import re


def to_pascal_case(s):
    """
    Convert a string to PascalCase.

    This function handles snake_case, camelCase, and PascalCase inputs.
    """
    # Replace underscores with spaces and add spaces before capital letters
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", r" ", s)

    # Capitalize the first letter of each word and join them together
    return "".join(word.capitalize() for word in s.split())
