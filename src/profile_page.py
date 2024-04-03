from flask import Blueprint
forum_blueprint = Blueprint('profile', __name__)
@forum_blueprint.route('/profile')
# Router to user profile pageile
@app.route("/profile_page", methods=["GET", "POST"])
def profile_page():
    global current_page
    current_page = "profile_page"
    # Render the profile page, showing username on pege
    return render_template(
        "profile_page.html",
        username=username,
        current_page=current_page,
        cGPA=cGPA,
    )
