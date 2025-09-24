import os
import glob

def tab_completion(text, allowed_filetypes, current_os):
    # Expand relative paths relative to parent folder
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pattern = os.path.join(base_dir, text + '*')
    matches = glob.glob(pattern)
    results = []
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
