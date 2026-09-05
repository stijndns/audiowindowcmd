import os
import glob
import shlex

def tab_completion(text, allowed_filetypes, current_os, completion_type) -> list[str]:
    # Expand relative paths relative to parent folder
    if completion_type == 'image':
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../assets/images"))
    elif completion_type == 'audio':
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../assets/audio"))
    elif completion_type == 'combatant_image':
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../assets/images/combatants"))
    else:
        return []

    pattern = os.path.join(base_dir, text + '*')
    matches = glob.glob(pattern)
    results: list[str] = []
    for m in matches:
        # Windows vs. POSIX Paths...
        rel = os.path.relpath(m, base_dir).replace("\\", "/")
        if os.path.isdir(m):
            # Keep directories so user can dive into them
            if current_os == "Linux":
                rel = rel.split("/")[-1]+"/"
            else:
                rel += "/"
            results.append(rel)
        else:
            # Only allow supported extensions
            ext = os.path.splitext(m)[1].lower()
            if ext in allowed_filetypes:
                if current_os == "Linux":
                    rel = rel.split("/")[-1]
                results.append(rel)
    return results


def get_arg_parts(arg) -> list[str]:
    """Tokenise, respecting quoted strings"""
    try:
        return shlex.split(arg.strip())
    except ValueError:
        return arg.strip().split()