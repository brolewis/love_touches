'''Initial application settings'''
# Standard Library
import os
# Third Party
import flask
import flask.ext.bootstrap
try:
    import flask.ext.debugtoolbar
except ImportError:
    debugtoolbar = False
else:
    debugtoolbar = True
import flask.ext.mail
import flask.ext.security
import flask.ext.sqlalchemy
import flask.ext.migrate
import raven.contrib.flask

# General Setup
app = flask.Flask(__name__)
app.config['DEBUG'] = str(os.getenv('DEBUG', False)).lower() == 'true'
DEV_SECRET_KEY = 'v=&3w2fsnn+all#(av21nbj9w&w5+$yd71tg*(zng_qwrw=)k*'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', DEV_SECRET_KEY)
app.config['TRACKING_ID'] = os.getenv('TRACKING_ID', '')
# Raven
if not app.debug:
    raven.contrib.flask.Sentry(app)
# SQLAlchemy
DATABASE_URI = os.getenv('DATABASE_URI', 'sqlite:///love_touches.sqlite')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
db = flask.ext.sqlalchemy.SQLAlchemy(app)
migrate = flask.ext.migrate.Migrate(app, db)
# Bootstrap
serve_local = str(os.getenv('BOOTSTRAP_SERVE_LOCAL', False)).lower() == 'true'
app.config['BOOTSTRAP_SERVE_LOCAL'] = serve_local
app.config['BOOTSTRAP_USE_MINIFIED'] = not app.debug
flask.ext.bootstrap.Bootstrap(app)
# Flask-Security
import models
app.config['SECURITY_MSG_LOGIN'] = ('Please log in to access this page.',
                                    'error')
app.config['SECURITY_EMAIL_SENDER'] = 'info@love-touches.org'
app.config['SECURITY_PASSWORD_HASH'] = 'bcrypt'
pw_salt = 'Fa_vX`u`>W52|:+6NFCV_-f+sU#BdUGC:s+!*n'
app.config['SECURITY_PASSWORD_SALT'] = os.getenv('PASSWORD_SALT', pw_salt)
store_salt = 'sCZ;2Hd$n~4;}8<2iG3dqgkr~=HQz b7j-yK@,'
app.config['SECURITY_REMEMBER_SALT'] = os.getenv('REMEMBER_SALT', store_salt)
app.config['SECURITY_TRACKABLE'] = True
app.config['SECURITY_CONFIRMABLE'] = True
app.config['SECURITY_CONFIRM_URL'] = '/confirm_email'
app.config['SECURITY_REGISTERABLE'] = True
app.config['SECURITY_REGISTER_URL'] = '/register_user'
app.config['SECURITY_RECOVERABLE'] = True
app.config['SECURITY_LOGIN_URL'] = '/login-user'
app.config['SECURITY_POST_LOGIN_VIEW'] = 'post_login'
app.config['SECURITY_CHANGEABLE'] = True
user_datastore = flask.ext.security.SQLAlchemyUserDatastore(db, models.User,
                                                            models.Role)
app.security = flask.ext.security.Security(app, user_datastore,
                                           register_blueprint=False)
state = app.security._state
state.login_manager.login_view = 'login'
app.context_processor(flask.ext.security.core._context_processor)
name = 'flask_security.core'
security_blueprint = flask.ext.security.views.create_blueprint(state, name)
app.register_blueprint(security_blueprint)
# Debug Toolbar
if debugtoolbar:
    app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
    flask.ext.debugtoolbar.DebugToolbarExtension(app)
# Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.postmarkapp.com'
user_name = 'a032c02e-a437-472f-b666-6a1dd8db40fe'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', user_name)
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_USERNAME', user_name)
flask.ext.mail.Mail(app)
# Celery
app.config['CELERY_ACCEPT_CONTENT'] = ['json']
app.config['CELERY_TASK_SERIALIZER'] = 'json'


# Local
import views
app.register_blueprint(views.manage.manage)
app.register_blueprint(views.signup.signup)
