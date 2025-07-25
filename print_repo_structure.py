from pathlib import Path

def print_tree(arg_root_dp, arg_output_fp, arg_prefix='', arg_exclude=None, arg_exclude_content=None):
    if arg_exclude is None:
        arg_exclude = {'.git', '__pycache__', 'venv', '.venv', '.local'}
    if arg_exclude_content is None:
        arg_exclude_content = {'dist', 'tests'}

    entries = sorted(
        [e for e in arg_root_dp.iterdir() if e.name not in arg_exclude],
        key=lambda x: (not x.is_dir(), x.name.lower())
    )

    for i, entry in enumerate(entries):
        connector = '└── ' if i == len(entries) - 1 else '├── '
        arg_output_fp.write(f"{arg_prefix}{connector}{entry.name}\n")
        if entry.is_dir() and entry.name not in arg_exclude_content:
            extension = '    ' if i == len(entries) - 1 else '│   '
            print_tree(entry, arg_output_fp, arg_prefix + extension, arg_exclude, arg_exclude_content)

# Usage
repo_root = Path('.')  # or replace with the explicit root path
output_fp = Path('repo_structure.txt')

with output_fp.open('w', encoding='utf-8') as f:
    f.write(f"{repo_root.resolve().name}\n")
    print_tree(repo_root.resolve(), f)
