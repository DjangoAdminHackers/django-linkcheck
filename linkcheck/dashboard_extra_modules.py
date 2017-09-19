from admin_tools.dashboard.modules import LinkList


class PermCheckingLinkList(LinkList):

    def __init__(self, title=None, **kwargs):
        self.required_perms = kwargs.pop('linkcheck.can_change_link', [])
        super(PermCheckingLinkList, self).__init__(title, **kwargs)

    def init_with_context(self, context):
        super(PermCheckingLinkList, self).init_with_context(context)
        if self.required_perms:
            if not context['request'].user.has_perms(self.required_perms):
                self.children = None
                self.pre_content = None
                self.post_content = None