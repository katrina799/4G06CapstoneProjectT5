from flask import Blueprint, render_template, current_app

profile_blueprint = Blueprint('profile', __name__)


@profile_blueprint.route('/profile_page', methods=["GET", "POST"])
def profile_page():
    username = current_app.config.get('username', '')
    cGPA = current_app.config.get(
        'cGPA', 
        'None (Please upload your transcript)'
    )
    current_page = current_app.config.get('current_page', 'home')
    
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )
