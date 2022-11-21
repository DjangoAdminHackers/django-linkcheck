from django.core.management.base import BaseCommand

from linkcheck.utils import find_all_links


class Command(BaseCommand):

    help = (
        "Goes through all models registered with Linkcheck, records any new links found"
        "and removes all outdated links"
    )

    def handle(self, *args, **options):
        self.stdout.write("Updating all links...")
        return "\n".join(
            [
                f"{model.capitalize()}: {', '.join([f'{count} {label}' for label, count in data.items()])}"
                for model, data in find_all_links().items()
            ]
        )
