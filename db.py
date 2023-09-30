import sqlite3

conn = sqlite3.connect("database.db")
print('open database successfully ')

conn.execute("CREATE TABLE users (name TXT,funt TEXT,oriText TEXT ,resText TEXT)")

print('table created successfully')

conn.close()

