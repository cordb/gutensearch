import os
import psycopg2
from psycopg2 import OperationalError

# change this path according to your setup
os.chdir('/path/to/gutensearch/gutenberg-dammit-files-v002/gutenberg-dammit-files')
print("Current working directory: {0}".format(os.getcwd()))

def create_connection(db_name, db_user, db_password, db_host, db_port):
    connection = None
    try:
        connection = psycopg2.connect(
            database=db_name,
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
        )
        print("Connection to PostgreSQL DB successful")
    except OperationalError as e:
        print(f"The error '{e}' occurred")
    return connection

# change this according to your database read-only user.
connection = create_connection(
    "gutensearch", "user", "password", "127.0.0.1", "port"
)

def execute_read_query(connection, query):
    cursor = connection.cursor()
    result = None
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        return result
    except Error as e:
        print(f"The error '{e}' occurred")

complete_select = """select (string_to_array(gd_path, '/'))[1]::text as directory, num, gd_path from gutenberg_raw.metadata_columns;"""

# change these paths according to your setup
f=open("/path/to/gutensearch/content_insert.sql", "a+")
files_complete = execute_read_query(connection, complete_select)
for file in files_complete:
    num =file[1]
    gd_path = file[2]
    f.write("""\set content `cat /path/to/gutensearch/gutenberg-dammit-files-v002/gutenberg-dammit-files/""" + gd_path + """`
insert into gutenberg_raw.content_raw values (""" + str(num) + """, (:'content'));
""")