"""HTTP routes for the spare parts domain."""

from flask import current_app
from flask import render_template, redirect, url_for, request, flash, session
from flask_login import (
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash
from sqlalchemy import or_

from extensions import db, login_manager
from models import User
from modules.spare_parts.models import Part
from permissions import require_role
from utils import allowed_file, handle_file_upload

from . import bp

@login_manager.user_loader
def load_user(user_id: str | None) -> User | UserMixin | None:
    """Resolve a ``User`` instance for Flask-Login sessions."""

    if not user_id:
        return None

    user = db.session.get(User, int(user_id))
    if user is not None:
        return user

    if current_app.config.get("LOGIN_DISABLED"):
        class _TestingUser(UserMixin):
            """Fallback principal used when authentication is disabled."""

            def __init__(self, test_user_id: int) -> None:
                self.id = test_user_id
                self.username = "test-user"
                self.role = "root"

        return _TestingUser(int(user_id))

    return None

@bp.route('/')
@login_required
def index():
    parts = Part.query.all()
    count = Part.query.count()
    return render_template('index.html', parts=parts, user=current_user, count=count)

@bp.route('/login', methods=['GET', 'POST'])
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

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/add', methods=['GET', 'POST'])
@login_required
@require_role('admin','root')
def add_part():
    if request.method == 'POST':
        sap_code = request.form['sap_code']
        part_number = request.form['part_number']
        name = request.form['name']
        description = request.form['description']
        category = request.form['category']
        equipment_code = request.form['equipment_code']
        location = request.form['location']
        manufacturer = request.form['manufacturer']
        analog_group = request.form['analog_group']
        photo = request.files['photo']

        photo_path = None
        if photo and allowed_file(photo.filename):
            photo_path = handle_file_upload(photo, current_app.config['UPLOAD_FOLDER'])

        new_part = Part(
            sap_code=sap_code,
            part_number=part_number,
            name=name,
            description=description,
            category=category,
            equipment_code=equipment_code,
            location=location,
            manufacturer=manufacturer,
            analog_group=analog_group,
            photo_path=photo_path
        )

        db.session.add(new_part)
        db.session.commit()

        flash('✅ Part added successfully.')
        return redirect(url_for('main.index'))

    return render_template('add_part.html')

@bp.route('/edit/<int:part_id>', methods=['GET', 'POST'])
@login_required
@require_role('admin','root')
def edit_part(part_id):
    part = Part.query.get_or_404(part_id)

    if request.method == 'POST':
        part.sap_code = request.form['sap_code']
        part.part_number = request.form['part_number']
        part.name = request.form['name']
        part.description = request.form['description']
        part.category = request.form['category']
        part.equipment_code = request.form['equipment_code']
        part.location = request.form['location']
        part.manufacturer = request.form['manufacturer']
        part.analog_group = request.form['analog_group']
        photo = request.files.get('photo')

        if photo and allowed_file(photo.filename):
            part.photo_path = handle_file_upload(photo, current_app.config['UPLOAD_FOLDER'])

        db.session.commit()
        flash('Part updated successfully.')
        return redirect(url_for('main.view_part', part_id=part.id))

    return render_template('edit_part.html', part=part, user=current_user)

@bp.route('/part/<int:part_id>')
@login_required
def view_part(part_id):
    part = Part.query.get_or_404(part_id)

    analogs = []
    if part.analog_group:
        analogs = Part.query.filter(
            Part.analog_group == part.analog_group,
            Part.id != part.id
        ).all()

    all_ids = [p.id for p in Part.query.order_by(Part.id).all()]
    current_index = all_ids.index(part.id)
    prev_id = all_ids[current_index - 1] if current_index > 0 else None
    next_id = all_ids[current_index + 1] if current_index < len(all_ids) - 1 else None

    return render_template(
        'view_part.html',
        part=part,
        analogs=analogs,
        user=current_user,
        prev_id=prev_id,
        next_id=next_id
    )

@bp.route('/delete/<int:part_id>', methods=['POST'])
@login_required
@require_role('root')
def delete_part(part_id):
    part = Part.query.get_or_404(part_id)
    db.session.delete(part)
    db.session.commit()
    flash('✅ Part deleted successfully.')
    return redirect(url_for('main.index'))

@bp.route('/export')
@login_required
@require_role('admin','root')
def export():
    flash("Export is not implemented yet.")
    return redirect(url_for('main.index'))

@bp.route('/import', methods=['GET', 'POST'])
@login_required
@require_role('admin','root')
def import_parts():
    # свою реализацию импорта оставь/верни, доступ ограничен
    return render_template('import.html')

@bp.route('/search', methods=['GET'])
@login_required
def search():
    keyword = request.args.get('query', '').strip()

    if not keyword:
        flash("Enter a search keyword.")
        return redirect(url_for('main.index'))

    results = Part.query.filter(or_(
        Part.sap_code.ilike(f"%{keyword}%"),
        Part.part_number.ilike(f"%{keyword}%"),
        Part.name.ilike(f"%{keyword}%"),
        Part.category.ilike(f"%{keyword}%"),
        Part.equipment_code.ilike(f"%{keyword}%"),
        Part.location.ilike(f"%{keyword}%"),
        Part.manufacturer.ilike(f"%{keyword}%"),
        Part.analog_group.ilike(f"%{keyword}%"),
        Part.description.ilike(f"%{keyword}%")
    )).all()

    if not results:
        flash("No results found.")
        return redirect(url_for('main.index'))

    session['search_results'] = [p.id for p in results]
    return redirect(url_for('main.search_results', index=0))

@bp.route('/search/results/<int:index>')
@login_required
def search_results(index):
    ids = session.get('search_results', [])
    if not ids:
        flash("No results in session.")
        return redirect(url_for('main.index'))

    if index < 0 or index >= len(ids):
        flash("Index out of range.")
        return redirect(url_for('main.search_results', index=0))

    part = Part.query.get_or_404(ids[index])
    return render_template(
        'search_results.html',
        part=part,
        index=index,
        total=len(ids),
        user=current_user
    )
