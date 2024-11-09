import os

def format_str_table(left, right, sp=30):
    spaces = " " * (sp - len(left) - len(right))

    return left + spaces + right

def ensure_dir(file_path):
    directory = os.path.dirname(file_path)
    if not os.path.exists(directory):
        os.makedirs(directory)