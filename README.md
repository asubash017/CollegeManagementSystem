# College Management System

A complete web-based system for managing college operations, built with Django. Handles students, staff, courses, attendance, and results through an easy-to-use interface.

## 🚀 Quick Start

### Installation
```bash
# 1. Clone the project
git clone https://github.com/yourusername/college-management-system.git
cd college-management-system

# 2. Create virtual environment
python -m venv venv

# 3. Activate environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# 4. Install requirements
pip install -r requirements.txt

# 5. Setup database
python manage.py migrate

# 6. Create admin account (HOD)
python manage.py createsuperuser

# 7. Run the application
python manage.py runserver