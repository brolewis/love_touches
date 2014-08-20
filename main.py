'''Initial application settings'''
# Standard Library
import os
# Third Party
import flask
import flask_bootstrap
import flask_debugtoolbar
import flask_mail
import flask_sqlalchemy
import flask.ext.migrate
import raven.contrib.flask

# General Setup
app = flask.Flask(__name__)
app.config['DEBUG'] = str(os.getenv('DEBUG', False)).lower() == 'true'
DEV_SECRET_KEY = 'v=&3w2fsnn+all#(av21nbj9w&w5+$yd71tg*(zng_qwrw=)k*'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', DEV_SECRET_KEY)
# Raven
if not app.debug:
    raven.contrib.flask.Sentry(app)
# SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///love_touches.sqlite'
db = flask_sqlalchemy.SQLAlchemy(app)
migrate = flask.ext.migrate.Migrate(app, db)
# Bootstrap
serve_local = str(os.getenv('BOOTSTRAP_SERVE_LOCAL', False)).lower() == 'true'
app.config['BOOTSTRAP_SERVE_LOCAL'] = serve_local
flask_bootstrap.Bootstrap(app)
# Flask-Security
import models
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
app.config['SECURITY_POST_LOGIN_VIEW'] = 'admin.actions'
app.config['SECURITY_CHANGEABLE'] = True
user_datastore = flask.ext.security.SQLAlchemyUserDatastore(db, models.User,
                                                            models.Role)
app.security = flask.ext.security.Security(app, user_datastore)
# Debug Toolbar
app.config['DEBUG_TB_INTERCEPT_REDIRECTS'] = False
flask_debugtoolbar.DebugToolbarExtension(app)
# Flask-Mail
app.config['MAIL_SERVER'] = 'smtp.postmarkapp.com'
app.config['MAIL_USERNAME'] = 'a032c02e-a437-472f-b666-6a1dd8db40fe'
app.config['MAIL_PASSWORD'] = 'a032c02e-a437-472f-b666-6a1dd8db40fe'
flask_mail.Mail(app)


# Local
import views
app.register_blueprint(views.admin.admin)
