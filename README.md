# Student Management System

A full-stack student management system with both backend and frontend components.

## Technical Requirements

### Backend
- Built with Django
- Implemented RESTful API endpoints
- Dbsqlite3 database integration
- Features:
  - Student profile management
  - Subject/Course management
  - Grade tracking system
  - Full CRUD operations for all entities
  - Proper error handling and validation

### Frontend
- Built with HTML, Tailwind and CSS, Javascript
  1. View and manage student profiles
  2. Display list of subjects per student
  3. Show detailed grade breakdown (activities, quizzes, exams)
  4. Add/edit grades
- Implements basic UI/UX practices for navigation and data input

## System Requirements
- RESTfulAPI Integration
- Proper error handling and validation
- Version control (Git)
- Hosted on Render

## Getting Started

### Prerequisites
- Python 3.8 or higher (Download from [python.org](https://www.python.org/downloads/))
- Git installed (Download from [git-scm.com](https://git-scm.com/downloads))
- A text editor (VS Code recommended)

### Installation Steps

1. Clone the repository
```bash
git clone https://github.com/----------/student-management-system.git
cd student-management-system
```

2. Create and activate virtual environment

For Windows:
```bash
python -m venv venv
.\venv\Scripts\activate
```

For macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install required packages
```bash
# Make sure you're in the project directory
pip install -r requirements.txt
```

4. Run the development server
```bash
python manage.py runserver
```

The system will be available at:
- Main site: http://127.0.0.1:8000/
- Django admin panel: http://127.0.0.1:8000/admin/
- RESTful API: http://127.0.0.1:8000/api/

### Common Issues and Solutions

- If `python` command is not found, try using `python3` instead
- If pip install fails, ensure you're using the latest pip version:
  ```bash
  python -m pip install --upgrade pip
  ```
- If the virtual environment isn't activating, ensure you're using the correct path separator for your OS

## License
This project is open-source and available under the MIT License.