from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.utils.termcolors import make_style

from linkcheck.utils import get_coverage_data, get_suggested_linklist_config


class Command(BaseCommand):

    cyan = staticmethod(make_style(fg='cyan'))

    help = 'Go through all models and check whether they are registered with linkcheck'

    def add_arguments(self, parser):
        parser.add_argument(
            '--model',
            help="Generate the suggested config for this model",
        )

    def handle(self, *args, model, **options):
        if model:
            try:
                model_class = apps.get_model(model)
            except Exception as e:
                raise CommandError(
                    f'Model "{model}" does not exist.'
                ) from e
            self.stdout.write(get_suggested_linklist_config(model_class))
        else:
            covered, uncovered = get_coverage_data()
            self.stdout.write('All covered models:\n')
            self.stdout.write(', '.join(map(self.cyan, covered)))
            for model, suggested_config in uncovered:
                self.stdout.write(f'\nSuggested config for model {model}:')
                self.stdout.write(self.cyan(suggested_config))
