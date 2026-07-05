"""
Textbook-quality matplotlib defaults for academic HTML notes.

Drop the rcParams block at the top of gen_plots.py:

    import matplotlib.pyplot as plt
    from matplotlib_setup import apply_textbook_style
    apply_textbook_style()

Or paste the rcParams.update() call directly if you don't want a separate
file. The colours below match the box-style CSS in template.html:

    accent (dark blue)  #1f3a5f   — primary line / training band
    warn  (red)         #c0392b   — emphasis / forecast errors / rejection
    good  (green)       #1e7e34   — secondary / pass / approved
    purple              #8e44ad   — third series / theorem highlight
    orange              #e67e22   — seasonal / cycle
"""
import matplotlib.pyplot as plt

# Standard colour palette — keep these in sync with template.html CSS variables
COLORS = {
    "accent":   "#1f3a5f",
    "warn":     "#c0392b",
    "good":     "#27ae60",     # slightly brighter than CSS --good for plot lines
    "purple":   "#8e44ad",
    "orange":   "#e67e22",
    "blue2":    "#2980b9",
    "gray":     "#7f8c8d",
}


def apply_textbook_style():
    """Apply the standard rcParams for academic notes figures."""
    plt.rcParams.update({
        # Typography — serif to match the document body
        'font.family': 'serif',
        'font.size': 10,
        'axes.labelsize': 10,
        'axes.titlesize': 11,
        'legend.fontsize': 8,
        # Light grid, no top/right spines (clean academic look)
        'axes.spines.top':   False,
        'axes.spines.right': False,
        'axes.grid':         True,
        'grid.alpha':        0.25,
        'grid.linestyle':    '--',
        # Output quality — figure.dpi 110 sizes the on-screen canvas;
        # savefig.dpi 130 is the retina/file-size sweet spot for the saved PNG.
        'figure.dpi':        110,
        'savefig.dpi':       130,
        'savefig.bbox':      'tight',
        'savefig.pad_inches': 0.08,
        # $ in titles/labels is a LITERAL dollar, not mathtext (learnings §3).
        # If you *want* mathtext in one label, wrap that call:
        #   with plt.rc_context({'text.parse_math': True}): ax.set_title(r'$x^2$')
        'text.parse_math':   False,
    })


# Convenience: import-time setup so callers can just `import matplotlib_setup`.
apply_textbook_style()


# ---------------------------------------------------------------------------
# Helpers for common layout decisions
# ---------------------------------------------------------------------------

def figsize_for(kind: str):
    """
    Pre-set figure sizes that fit the 920px page width.

    'wide'    – full-width single panel,        ~8.4 x 3.0 in
    'square'  – square single panel,            ~6.0 x 6.0 in
    'twocol'  – two side-by-side panels,        ~9.0 x 3.0 in
    'fourcol' – four stacked panels,            ~9.0 x 2.4 in
    'tall'    – full-width tall (decomposition) ~8.4 x 5.8 in
    """
    return {
        'wide':    (8.4, 3.0),
        'square':  (6.0, 6.0),
        'twocol':  (9.0, 3.0),
        'fourcol': (9.0, 2.4),
        'tall':    (8.4, 5.8),
    }[kind]
