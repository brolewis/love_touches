# Third Party
import flask.ext.admin
import flask.ext.admin.contrib.sqla
import flask.ext.admin.model
import flask.ext.principal
import wtforms
# Local
import main
import models


class AuthBaseView(flask.ext.admin.BaseView):
    def is_accessible(self):
        user = flask.ext.login.current_user
        return user.is_authenticated() and user.has_role('admin')

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            return flask.current_app.login_manager.unauthorized()


class AuthIndexView(flask.ext.admin.AdminIndexView, AuthBaseView):
    pass


class AuthModelView(flask.ext.admin.contrib.sqla.ModelView, AuthBaseView):
    pass


class LogoutView(AuthBaseView):
    @flask.ext.admin.expose('/')
    def logout(self):
        return flask.redirect(flask.url_for('security.logout'))


class UserModelView(AuthModelView):
    can_create = False
    form_columns = ('roles', 'active', 'email', 'phone', 'secret')
    column_list = ('active', 'email', 'phone', 'method', 'confirmed_at',
                   'email_confirmed_at', 'phone_confirmed_at')
    column_searchable_list = ('email', 'phone')

    def scaffold_form(self):
        form_class = super(UserModelView, self).scaffold_form()
        form_class.password2 = wtforms.PasswordField('New Password')
        return form_class

    def on_model_change(self, form, model):
        if len(model.password2):
            passwd = form.password2.data
            model.password = flask.ext.security.utils.encrypt_password(passwd)


class StatusFilter(flask.ext.admin.contrib.sqla.filters.FilterEqual):
    def __init__(self):
        column = models.Action.status_id
        options = [(x.id, x.name) for x in models.Status.query.all()]
        super(StatusFilter, self).__init__(column, 'Status', options=options)


class MethodModelView(AuthModelView):
    column_list = ('name', 'status', 'sections', 'author')
    column_filters = (StatusFilter(),)


class ActionModelView(AuthModelView):
    column_filters = (StatusFilter(),)


class ApproveMethod(AuthBaseView):
    @flask.ext.admin.expose('/')
    def index(self):
        pass


admin = flask.ext.admin.Admin(main.app, 'Love Touches',
                              index_view=AuthIndexView())
admin.add_view(UserModelView(models.User, models.db.session))
admin.add_view(MethodModelView(models.Method, models.db.session))
admin.add_view(ActionModelView(models.Action, models.db.session))
# Logout
admin.add_view(LogoutView(name='Logout'))
