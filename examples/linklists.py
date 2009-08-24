from django.db.models import signals as model_signals

from linkcheck import Linklist

from cms.models import Page

class PageLinklist(Linklist):
    model = Page # The model this relates to
    object_filter = {'active':True} # A dict of conditions that get passed thus: your_model.objects.filter(**your_dict)
    html_fields = ['content', 'extra_content'] # fields in the model that contain HTML fragments
    url_fields = [] # fields in the model that contain raw url fields
    image_fields = [] # fields in the model that contain raw image fields

# That's all for now except we assume that all models provide a get_absolute_url and a get_admin_url

# Below is the stub for the next step in the functionality - syncing Link and Url tables when saving or changing models

def page_pre_save(sender, instance, **kwargs):
    pass
    # TODO
    # Compare old and new links and add new ones to db
    # If name has changed then flag up all references to the old name
    
def page_pre_delete(sender, instance, **kwargs):
    pass
    # TODO
    # Check if name is in urls list and if it is then flag up that url

model_signals.pre_save.connect(page_pre_save, sender=Page)
model_signals.pre_delete.connect(page_pre_delete, sender=Page)