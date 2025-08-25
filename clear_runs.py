import sqlite3
conn = sqlite3.connect('database/irrigation_data.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM scheduled_runs')
conn.commit()
print('Cleared scheduled runs')
cursor.execute('SELECT COUNT(*) FROM zones')
zones = cursor.fetchone()[0]
cursor.execute('SELECT COUNT(*) FROM scheduled_runs')
runs = cursor.fetchone()[0]
print(f'Database ready: {zones} zones, {runs} scheduled runs')
conn.close()
