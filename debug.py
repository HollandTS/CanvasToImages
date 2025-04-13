import traceback

def log_error():
    """Logs any errors to debug.log"""
    with open("debug.log", "a") as f:
        f.write(traceback.format_exc() + "\n\n")
