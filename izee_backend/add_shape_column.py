import sys
from database.connection import engine
import sqlalchemy as sa

def add_shape_column():
    with engine.begin() as conn:
        # Check if column already exists
        insp = sa.inspect(conn)
        columns = [col['name'] for col in insp.get_columns('trip')]
        if 'shape_id' not in columns:
            conn.execute(sa.text('ALTER TABLE trip ADD COLUMN shape_id VARCHAR'))
            print('Added shape_id column to trip')
        else:
            print('shape_id column already exists')

if __name__ == '__main__':
    add_shape_column()
