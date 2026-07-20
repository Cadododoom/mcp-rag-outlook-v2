import sqlite3
import os
import monitor_session

def create_mock_db(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE logs (id INTEGER PRIMARY KEY, timestamp TEXT, message TEXT)''')
    
    logs = [
        "Normal operation started",
        "Executing tool: view_file",
        "Executing tool: view_file",
        "Executing tool: view_file", # loop
        "Executing tool: view_file",
        "Subprocess execution exception: segmentation fault", # error
        "System warning: context limit reached, truncation applied", # truncation
        "Normal operation ended"
    ]
    
    for log in logs:
        cursor.execute("INSERT INTO logs (message) VALUES (?)", (log,))
        
    conn.commit()
    conn.close()

def main():
    test_db = '/home/theworks/teamwork_projects/neon_void_monitor/test_state.db'
    test_log = '/home/theworks/teamwork_projects/neon_void_monitor/test_diagnostics.log'
    
    if os.path.exists(test_log):
        os.remove(test_log)
        
    print("Creating mock database...")
    create_mock_db(test_db)
    
    print("Running analyze_logs...")
    logger = monitor_session.setup_logger(test_log)
    monitor_session.analyze_logs(test_db, logger)
    
    print("Verifying log output...")
    with open(test_log, 'r') as f:
        log_content = f.read()
        
    failed = False
    if "Tool loop detected" in log_content:
        print("PASS: Tool loop detected.")
    else:
        print("FAIL: Tool loop NOT detected.")
        failed = True
        
    if "Subprocess issue detected" in log_content:
        print("PASS: Subprocess error detected.")
    else:
        print("FAIL: Subprocess error NOT detected.")
        failed = True
        
    if "System context/truncation issue detected" in log_content:
        print("PASS: Truncation warning detected.")
    else:
        print("FAIL: Truncation warning NOT detected.")
        failed = True

    if failed:
        exit(1)
    else:
        print("All tests passed.")
        exit(0)

if __name__ == "__main__":
    main()
