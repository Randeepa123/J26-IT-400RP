"""
build_dashboard_html.py - Bundles the live dashboard into a self-contained outputs/run_component3/dashboard.html.
Can be opened directly as file:// or served via api_server.py.
"""
from pathlib import Path
import paths

def build_standalone_dashboard(out_file=None):
    dashboard_dir = paths.SRC_DIR / "dashboard"
    index_path = dashboard_dir / "index.html"
    css_path = dashboard_dir / "dashboard.css"
    js_path = dashboard_dir / "dashboard.js"

    html = index_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8")
    js = js_path.read_text(encoding="utf-8")

    # Replace <link rel="stylesheet" href="dashboard.css"> with <style>...</style>
    html = html.replace('<link rel="stylesheet" href="dashboard.css">', f'<style>\n{css}\n</style>')
    # Replace <script src="dashboard.js"></script> with <script>...</script>
    html = html.replace('<script src="dashboard.js"></script>', f'<script>\n{js}\n</script>')

    target = Path(out_file or (paths.RUN_COMPONENT3_DIR / "dashboard.html"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    print(f"Generated self-contained live dashboard: {target}")
    return target

if __name__ == "__main__":
    build_standalone_dashboard()
