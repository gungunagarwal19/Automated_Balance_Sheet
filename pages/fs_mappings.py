import streamlit as st
from db import get_db
from lib_ui import require_role

require_role('admin')
st.title('FS Group -> Role Mappings')

st.write('Create mappings from FS grouping values to users for specific roles (reviewer, fc)')

with get_db() as db:
    rows = db.execute('SELECT f.id, f.fs_group, f.role, u.username FROM fs_responsibilities f LEFT JOIN users u ON f.user_id=u.id ORDER BY f.fs_group, f.role').fetchall()

st.table([{k: r[k] for k in r.keys()} for r in rows])

st.header('Add mapping')
fs_group = st.text_input('FS Group (exact match)')
role = st.selectbox('Role', ['reviewer', 'fc'])
user_id = st.number_input('User ID', min_value=1, step=1)

if st.button('Add mapping'):
    with get_db() as db:
        try:
            db.execute('INSERT INTO fs_responsibilities(fs_group, role, user_id) VALUES(?,?,?)', (fs_group, role, user_id))
            st.success('Mapping added')
        except Exception as e:
            st.error(f'Error adding mapping: {e}')

st.markdown('---')
st.header('Delete mapping by ID')
mid = st.number_input('Mapping ID to delete', min_value=0, step=1)
if st.button('Delete mapping'):
    with get_db() as db:
        db.execute('DELETE FROM fs_responsibilities WHERE id=?', (mid,))
        st.success('Deleted (if existed)')
