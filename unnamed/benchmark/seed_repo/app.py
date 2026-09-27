import subprocess
import time

API_KEY = "super-secret-production-value"

def dangerous(command, conn, users):
    subprocess.run(command, shell=True)
    for user in users:
        conn.execute(f"SELECT * FROM orders WHERE user_id = {user['id']}")
    time.sleep(1)
    try:
        return eval(command)
    except:
        return None
