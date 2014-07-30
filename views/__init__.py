# Third Party
import flask
# Local
import main
import views.admin
import views.security
import views.signup


@main.app.route('/')
def index():
    for key in ('_email_sent', '_phone_sent'):
        if key in flask.session:
            del flask.session[key]
    return flask.render_template('index.html')


@main.app.route('/cancel')
def cancel():
    for key in (x for x in flask.session.keys() if not x.startswith('_')):
        del flask.session[key]
    return flask.redirect(flask.url_for('index'))
