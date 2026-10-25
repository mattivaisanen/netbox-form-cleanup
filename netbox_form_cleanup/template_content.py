from netbox.plugins import PluginTemplateExtension


class MoreFieldsSection(PluginTemplateExtension):
    """
    A small style and script on every page that moves fields marked hidden
    (hooks/forms.py) into a collapsed "More fields" section at the end of
    their form. models=None because head() is only offered for every page;
    the script does nothing on pages without such fields.
    """
    def head(self):
        return self.render('netbox_form_cleanup/inc/head.html')


template_extensions = [MoreFieldsSection]
