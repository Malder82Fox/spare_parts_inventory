from flask import Blueprint
from flask import render_template, redirect, url_for, request, flash, send_file, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from models import User, Part
from extensions import db, login_manager
from utils import allowed_file, handle_file_upload
from openpyxl import Workbook
import io

main = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
@login_required
def index():
    parts = Part.query.all()
    return render_template('index.html', parts=parts, user=current_user)

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main.index'))
        flash('Invalid username or password')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

#additional for routes

@main.route('/add', methods=['GET', 'POST'])
@login_required
def add_part():
    return render_template('add_part.html')  # пока просто заглушка

@main.route('/edit/<int:part_id>', methods=['GET', 'POST'])
@login_required
def edit_part(part_id):
    return render_template('edit_part.html', part_id=part_id)  # заглушка

@main.route('/part/<int:part_id>')
@login_required
def view_part(part_id):
    return render_template('view_part.html', part_id=part_id)  # заглушка

@main.route('/delete/<int:part_id>', methods=['POST'])
@login_required
def delete_part(part_id):
    flash("Delete is not implemented yet.")
    return redirect(url_for('main.index'))

@main.route('/export')
@login_required
def export():
    flash("Export is not implemented yet.")
    return redirect(url_for('main.index'))

@main.route('/import')
@login_required
def import_parts():
    flash("Import is not implemented yet.")
    return redirect(url_for('main.index'))
