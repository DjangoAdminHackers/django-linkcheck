import imp
from importlib import import_module

from django.apps import AppConfig, apps
from django.db.models.signals import post_delete


class AlreadyRegistered(Exception):
    pass


class BaseLinkcheckConfig(AppConfig):
    name = 'linkcheck'
    verbose_name = "Linkcheck"

    all_linklists = {}

    def ready(self):
        self.build_linklists()

    def build_linklists(self):
        """Autodiscovery of linkLists"""
        for app in apps.get_app_configs():
            try:
                imp.find_module('linklists', [app.path])
            except ImportError:
                continue
            the_module = import_module("%s.linklists" % app.name)
            try:
                for k in the_module.linklists.keys():
                    if k in self.all_linklists.keys():
                        raise AlreadyRegistered('The key %s is already registered in all_linklists' % k)

                for l in the_module.linklists.values():
                    for l2 in self.all_linklists.values():
                        if l.model == l2.model:
                            raise AlreadyRegistered('The LinkList %s is already registered in all_linklists' % l)
                self.all_linklists.update(the_module.linklists)
            except AttributeError:
                pass
        # Add a reference to the linklist in the model. This change is for internal hash link,
        # But might also be useful elsewhere in the future
        for key, linklist in self.all_linklists.items():
            setattr(linklist.model, '_linklist', linklist)


class LinkcheckConfig(BaseLinkcheckConfig):
    def ready(self):
        from .linkcheck_settings import DISABLE_LISTENERS
        super(LinkcheckConfig, self).ready()

        if not DISABLE_LISTENERS:
            # This import will register listeners
            from . import listeners

        from .models import Link, link_post_delete
        post_delete.connect(link_post_delete, sender=Link)
