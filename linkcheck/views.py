from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

from linkcheck.utils import get_coverage_data


@staff_member_required
def coverage(request):

    coverage_data = get_coverage_data()

    if request.GET.get('config', False):
        # Just render the suggested linklist code
        template = 'linkcheck/suggested_configs.html'
        context = {'coverage_data': [x['suggested_config'] for x in coverage_data]}
    else:
        # Render a nice report
        template = 'linkcheck/coverage.html'
        context = {'coverage_data': coverage_data}

    return render(request, template, context)
