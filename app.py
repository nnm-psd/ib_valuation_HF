
# app.py  (root level, just re-exports the real app)
import runpy
runpy.run_path("src/app/streamlit_app.py", run_name="__main__")