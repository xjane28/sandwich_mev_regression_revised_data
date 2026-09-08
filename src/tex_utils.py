import os
import pandas as pd
import numpy as np

def escape_tex(text):
    if not isinstance(text, str):
        return str(text)
    # Don't escape if it already looks like a latex command or math
    # But for standard notes and headers, replace %, $, _
    # To be safe and clean, let's replace % with \%, _ with \_, $ with \$ where appropriate
    # However, if text contains math like $p_{90}$, we shouldn't blindly replace $ and _ inside math!
    # Let's do a smart escape or let callers pass clean tex strings for notes.
    # For headers and cell values that are pure strings without math:
    return text

def format_num(val, decimals=2, sig_digits=4, is_int=False, is_se=False, stars=""):
    if pd.isna(val):
        return ""
    if isinstance(val, (int, np.integer)) or is_int:
        res = f"{int(val):,}"
    elif isinstance(val, (float, np.floating)):
        if abs(val) >= 1e6 or (abs(val) > 0 and abs(val) < 1e-4):
            # Scientific or large formatted
            if abs(val) >= 1e6:
                res = f"{val:,.{decimals}f}"
            else:
                res = f"{val:.4e}"
        else:
            res = f"{val:.{decimals}f}"
    else:
        res = str(val)
    if is_se:
        return f"({res})"
    return res + stars

def write_table(df, name, caption, label, notes, col_align=None, col_headers=None):
    os.makedirs("output/tables", exist_ok=True)
    csv_path = f"output/tables/{name}.csv"
    tex_path = f"output/tables/{name}.tex"
    
    # Save CSV
    df.to_csv(csv_path, index=False)
    
    # Save TEX
    n_cols = len(df.columns)
    if col_align is None:
        col_align = "l" + "r" * (n_cols - 1)
    if col_headers is None:
        col_headers = [c.replace("_", "\\_").replace("%", "\\%") for c in df.columns]
    
    lines = [
        "\\begin{table}[htbp]",
        "\\centering",
        f"\\caption{{{caption}}}",
        f"\\label{{{label}}}",
        f"\\begin{{tabular}}{{{col_align}}}",
        "\\toprule",
        " & ".join(col_headers) + " \\\\",
        "\\midrule"
    ]
    
    for _, row in df.iterrows():
        row_strs = []
        for val in row:
            if pd.isna(val):
                row_strs.append("")
            elif isinstance(val, (int, np.integer)):
                row_strs.append(f"{val:,}")
            elif isinstance(val, (float, np.floating)):
                # If it's already formatted or we format it cleanly
                if abs(val) >= 1000:
                    row_strs.append(f"{val:,.2f}")
                elif abs(val) < 0.0001 and val != 0:
                    row_strs.append(f"{val:.4e}")
                else:
                    row_strs.append(f"{val:.4f}".rstrip("0").rstrip(".") if val == int(val) else f"{val:.4f}")
            else:
                row_strs.append(str(val))
        lines.append(" & ".join(row_strs) + " \\\\")
        
    lines.extend([
        "\\bottomrule",
        "\\end{tabular}",
        "\\vspace{0.2cm}",
        "\\begin{minipage}{\\linewidth}",
        "\\small",
        f"\\textit{{Notes:}} {notes}",
        "\\end{minipage}",
        "\\end{table}"
    ])
    
    with open(tex_path, "w") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"[PASS] Generated {csv_path} and {tex_path}")
