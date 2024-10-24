# Django Record Management System

This is a simple Django application for managing records, built with server-side rendering and Bootstrap for UI styling.

## Features

- Server-side rendered pages using Django templates
- Bootstrap integration for responsive design
- SQLite database for data persistence
- CRUD operations for record types, fields, and roles
- User authentication and authorization
- Form input validation using Django forms

## Setup and Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/django-record-management.git
   cd django-record-management
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

4. Run database migrations:
   ```
   python manage.py migrate
   ```

5. Create a superuser:
   ```
   python manage.py createsuperuser
   ```

6. Start the development server:
   ```
   python manage.py runserver
   ```

7. Access the application at `http://localhost:8000`

## Project Structure

- `app/`: Main Django application directory
  - `models.py`: Database models
  - `views.py`: View functions
  - `urls.py`: URL configurations
  - `forms.py`: Form definitions
- `templates/`: HTML templates
- `static/`: Static files (CSS, JavaScript)

## Usage

1. Log in using the superuser credentials
2. Create record types, fields, and roles
3. Manage records through the web interface

## Contributing

1. Fork the repository
2. Create a new branch (`git checkout -b feature-branch`)
3. Make your changes and commit (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature-branch`)
5. Create a new Pull Request

## License

This project is licensed under the MIT License.
