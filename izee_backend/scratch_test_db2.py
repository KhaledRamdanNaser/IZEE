import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
conn = sqlite3.connect('izee.db')
c = conn.cursor()
try:
    c.execute('SELECT stop_id, name FROM stop WHERE name LIKE "%شبرا الخيمة%"')
    print('Stops with شبرا الخيمة:', c.fetchall())
except sqlite3.OperationalError as e:
    print('No stop table', e)

try:
    c.execute('SELECT route_id, route_name FROM route WHERE route_name LIKE "%شبرا الخيمة%"')
    print('Routes with شبرا الخيمة:', c.fetchall())
except sqlite3.OperationalError as e:
    print('No route table', e)

try:
    c.execute('SELECT stop_id, name FROM stop WHERE name LIKE "%التحرير%"')
    print('Stops with التحرير:', c.fetchall())
except sqlite3.OperationalError as e:
    print('No stop table', e)

try:
    c.execute('SELECT route_id, route_name FROM route WHERE route_name LIKE "%التحرير%"')
    print('Routes with التحرير:', c.fetchall())
except sqlite3.OperationalError as e:
    print('No route table', e)
