import pandas as pd
import mysql.connector

# Database connection
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)

# Read Excel file
df = pd.read_excel('Libro2.xlsx')

# Clean column names (remove extra spaces/newlines)
df.columns = df.columns.str.strip()

print("Columns found:", df.columns.tolist())
print(f"\nTotal rows: {len(df)}")
print("\nFirst few rows:")
print(df.head())

# Insert data into database
cursor = conexion.cursor()

# Clear existing data
cursor.execute("DELETE FROM materias_asignadas")
print("\nCleared existing data from materias_asignadas table")

# Insert new data
inserted = 0
for index, row in df.iterrows():
    try:
        cursor.execute("""
            INSERT INTO materias_asignadas (nombre_materia, semestre, no_empleado, grupo)
            VALUES (%s, %s, %s, %s)
        """, (
            row['NOMBRE_MATERIA'],
            row['SEMESTRE'],
            row['NO_EMPLEADO'],
            row['GRUPO']
        ))
        inserted += 1
    except Exception as e:
        print(f"Error inserting row {index}: {e}")
        print(f"Data: {row.to_dict()}")

conexion.commit()
cursor.close()
conexion.close()

print(f"\n✓ Successfully imported {inserted} subject assignments!")
