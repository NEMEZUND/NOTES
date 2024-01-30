import PySimpleGUI as sg
import psycopg2
from datetime import datetime
from PIL import Image, ImageTk
import io
from base64 import b64encode
import os

# Подключение к базе данных PostgreSQL
conn = psycopg2.connect(
    dbname='Notes',
    user='postgres',
    password='Pwd000',
    host='localhost',
    port='5432'
)

# Создание таблицы для заметок
create_table_query = """
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    image BYTEA
);
"""
with conn.cursor() as cursor:
    cursor.execute(create_table_query)
conn.commit()

# Функция для вставки заметки в базу данных
def insert_note(title, content, image_path=None):
    if not title.strip():  # Проверка на пустой заголовок
        sg.popup('Title cannot be empty!')
        return None

    image_bytes = image_to_bytes(image_path) if image_path else None
    insert_query = """
    INSERT INTO notes (title, content, created_at, updated_at, image)
    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s)
    RETURNING id, created_at, updated_at;
    """
    with conn.cursor() as cursor:
        cursor.execute(insert_query, (title, content, image_bytes))
        result = cursor.fetchone()
    conn.commit()
    return result

# Функция для преобразования изображения в байты
def image_to_bytes(image_path):
    if image_path and image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        with open(image_path, 'rb') as f:
            return f.read()
    elif image_path:
        sg.popup('Invalid image format! Please select a valid image file.')
        return None
    else:
        return None

# Остальной код остается без изменений
def delete_note(note_id):
    delete_query = """
    DELETE FROM notes
    WHERE id = %s;
    """
    with conn.cursor() as cursor:
        cursor.execute(delete_query, (note_id,))
    conn.commit()
def search_notes(search_type, search_value):
    if search_type == 'Date':
        search_query = """
        SELECT id, title, content, created_at, updated_at, image
        FROM notes
        WHERE created_at::date = %s::date OR updated_at::date = %s::date
        """
        params = (search_value, search_value)
    elif search_type == 'Title':
        search_query = """
        SELECT id, title, content, created_at, updated_at, image
        FROM notes
        WHERE title ILIKE %s
        """
        params = (f"%{search_value}%",)
    elif search_type == 'Text':
        search_query = """
        SELECT id, title, content, created_at, updated_at, image
        FROM notes
        WHERE content ILIKE %s
        """
        params = (f"%{search_value}%",)
    else:
        return []

    with conn.cursor() as cursor:
        cursor.execute(search_query, params)
        return cursor.fetchall()

# Функция для обновления заметки в базе данных
def update_note(note_id, title, content, image_path):
    image_bytes = image_to_bytes(image_path) if image_path else None
    update_query = """
    UPDATE notes
    SET title = %s, content = %s, image = %s, updated_at = CURRENT_TIMESTAMP
    WHERE id = %s
    RETURNING updated_at;
    """
    with conn.cursor() as cursor:
        cursor.execute(update_query, (title, content, image_bytes, note_id))
        updated_at = cursor.fetchone()[0]
    conn.commit()

    # Добавлено обновление данных в окне в реальном времени
    window_main.write_event_value('update_note', (note_id, title, content, image_path, updated_at))

    return updated_at

# Функция для отображения списка заметок
def display_notes_with_pagination(notes):
    if not notes:
        sg.popup('No notes found!')
        return

    page_size = 2
    current_page = 1

    while True:
        notes_to_display = notes[(current_page - 1) * page_size:current_page * page_size]

        layout = []
        for note in notes_to_display:
            note_id, title, content, created_at, updated_at, image_bytes = note
            created_at_str = created_at.strftime('%Y-%m-%d %H:%M:%S')
            updated_at_str = updated_at.strftime('%Y-%m-%d %H:%M:%S') if updated_at else ''

            # Изменение этой строки
            image_data = b64encode(image_bytes).decode() if image_bytes else None
            image_elem = sg.Image(data=image_data, size=(100, 100), key=f'image_{note_id}')

            layout.append([sg.Text(f'Title: {title}')])
            layout.append([sg.Text(f'Content: {content}')])
            layout.append([sg.Text(f'Created At: {created_at_str}')])
            layout.append([sg.Text(f'Updated At: {updated_at_str}')])
            layout.append([image_elem])
            layout.append([sg.Button(f'Edit {note_id}'), sg.Button(f'Delete {note_id}')])

        layout.append([sg.Text(f'Page {current_page}')])
        layout.append([sg.Button('Prev Page'), sg.Button('Next Page')])

        window_notes = sg.Window('Notes', layout, resizable=True)

        event, values = window_notes.read()

        if event == sg.WINDOW_CLOSED:
            break
        elif event == 'Prev Page':
            if current_page > 1:
                current_page -= 1
        elif event == 'Next Page':
            if current_page < len(notes) // page_size + 1:
                current_page += 1

        elif event.startswith('Edit'):
            note_id = int(event.split()[-1])
            edit_note_window(note_id)
        elif event.startswith('Delete'):
            note_id = int(event.split()[-1])
            delete_note(note_id)
            sg.popup(f'Note {note_id} deleted!')
            # Очистим макет, чтобы избежать повторного использования элементов
            window_notes.close()
            break

        window_notes.close()


# Функция для отображения окна редактирования заметки
def edit_note_window(note_id):
    note_query = """
    SELECT title, content, image
    FROM notes
    WHERE id = %s;
    """
    with conn.cursor() as cursor:
        cursor.execute(note_query, (note_id,))
        result = cursor.fetchone()

    title, content, image_bytes = result
    image_path = None
    if image_bytes:
        temp_image_path = f'temp_image_{note_id}.png'
        with open(temp_image_path, 'wb') as f:
            f.write(image_bytes)
        image_path = temp_image_path

    layout_edit = [
        [sg.Text('Title:'), sg.InputText(default_text=title, key='title')],
        [sg.Text('Content:'), sg.Multiline(default_text=content, key='content')],
        [sg.Text('Image:'), sg.InputText(default_text=image_path, key='image_path'), sg.FileBrowse()],
        [sg.Button('Update'), sg.Button('Cancel')],
    ]

    window_edit = sg.Window(f'Edit Note ID: {note_id}', layout_edit, resizable=True)

    while True:
        event_edit, values_edit = window_edit.read()

        if event_edit == sg.WINDOW_CLOSED or event_edit == 'Cancel':
            break
        elif event_edit == 'Update':
            title_edit = values_edit['title']
            content_edit = values_edit['content']
            image_path_edit = values_edit['image_path']

            update_note(note_id, title_edit, content_edit, image_path_edit)

            sg.popup(f'Note {note_id} updated!')
            window_edit.close()
            break

    window_edit.close()
    if image_path:
        os.remove(image_path)

# Графический интерфейс PySimpleGUI
sg.theme('LightGrey1')

layout_main = [
    [sg.Text('Title:'), sg.InputText(key='title')],
    [sg.Text('Content:'), sg.Multiline(key='content')],
    [sg.Text('Image:'), sg.InputText(key='image_path'), sg.FileBrowse()],
    [sg.Button('Add'), sg.Button('Search'), sg.Button('View All')],
]

window_main = sg.Window('Note App', layout_main, resizable=True)

while True:
    event_main, values_main = window_main.read()

    if event_main == sg.WINDOW_CLOSED:
        break
    elif event_main == 'Add':
        title = values_main['title']
        content = values_main['content']
        image_path = values_main['image_path']
        result = insert_note(title, content, image_path)
        if result:
            note_id, created_at, updated_at = result
            sg.popup(f'Note added! ID: {note_id}\nCreated At: {created_at}\nUpdated At: {updated_at}')
    elif event_main == 'Search':
        search_layout = [
            [sg.Text('Select Search Type:')],
            [sg.Radio('Date', 'SEARCH_TYPE', default=True, key='search_type_date'), sg.Radio('Title', 'SEARCH_TYPE', key='search_type_title'), sg.Radio('Text', 'SEARCH_TYPE', key='search_type_text')],
            [sg.Text('Enter Search Value:')],
            [sg.InputText(key='search_value')],
            [sg.Button('Search'), sg.Button('Cancel')],
        ]

        window_search = sg.Window('Search Notes', search_layout)

        while True:
            event_search, values_search = window_search.read()

            if event_search == sg.WINDOW_CLOSED or event_search == 'Cancel':
                break
            elif event_search == 'Search':
                search_type_date = values_search['search_type_date']
                search_type_title = values_search['search_type_title']
                search_type_text = values_search['search_type_text']

                if search_type_date:
                    search_type = 'Date'
                elif search_type_title:
                    search_type = 'Title'
                elif search_type_text:
                    search_type = 'Text'
                else:
                    sg.popup('Please select a search type!')
                    continue

                search_value = values_search['search_value']

                notes = search_notes(search_type, search_value)
                display_notes_with_pagination(notes)
                window_search.close()
                break

        window_search.close()
    elif event_main == 'View All':
        notes_query = """
        SELECT id, title, content, created_at, updated_at, image
        FROM notes;
        """
        with conn.cursor() as cursor:
            cursor.execute(notes_query)
            notes = cursor.fetchall()
        display_notes_with_pagination(notes)

# Закрытие соединения с базой данных
conn.close()
