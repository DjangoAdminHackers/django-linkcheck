
django-linkcheck
===================

.. image:: https://github.com/DjangoAdminHackers/django-linkcheck/workflows/Test/badge.svg
   :target: https://github.com/DjangoAdminHackers/django-linkcheck/actions
   :alt: GitHub Actions

A fairly flexible app that will analyze and report on links in any model that
you register with it.

.. image:: https://github.com/DjangoAdminHackers/django-linkcheck/raw/master/linkcheck.jpg

Links can be bare (urls or image and file fields) or
embedded in HTML (linkcheck handles the parsing). It's fairly easy to override
methods of the Linkcheck object should you need to do anything more
complicated (like generate URLs from slug fields etc).

You should run its management command via cron or similar to check external
links regularly to see if their status changes. All links are checked
automatically when objects are saved. This is handled by signals.

Minimal requirements
--------------------

django-linkchecks requires Python 3 and Django 2.2.

Basic usage
-----------

#. Install app to somewhere on your Python path (e.g. ``pip install
   django-linkcheck``).
   
#. Add ``'linkcheck'`` to your ``settings.INSTALLED_APPS``.

#. Add a file named ``linklists.py`` to every app (see an example in ``examples/linklists.py``) that either:

   #) has models that contain content (e.g. url/image fields, chunks of markup
      or anything that gets transformed into a IMG or HREF when displayed
   #) can be the target of a link - i.e. is addressed by a url - in this case
      make sure it has an instance method named 'get_absolute_url'

#. Run ``./manage.py migrate``.

#. Add to your root url config::

    path('admin/linkcheck/', include('linkcheck.urls'))

#. View ``/admin/linkcheck/`` from your browser.

We are aware that this documentation is on the brief side of things so any
suggestions for elaboration or clarification would be gratefully accepted.

Linklist classes
----------------

The following class attributes can be added to your ``Linklist`` subclasses to
customize the extracted links:

    ``object_filter``: a dictionary which will be passed as a filter argument to
    the ``filter`` applied to the default queryset of the target class. This
    allows you to filter the objects from which the links will be extracted.
    (example: ``{'active': True}``)

    ``object_exclude``: a dictionary which will be passed as a filter argument to
    the ``exclude`` applied to the default queryset of the target class. As with
    ``object_filter``, this allows you to exclude objects from which the links
    will be extracted.

    ``html_fields``: a list of field names which will be searched for links.

    ``url_fields``: a list of ``URLField`` field names whose content will be
    considered as links. If the field content is empty and the field name is
    in ``ignore_empty``, the content is ignored.

    ``ignore_empty``: a list of fields from ``url_fields``. See the explanation
    above. (new in django-linkcheck 1.1)

    ``image_fields``: a list of ``ImageField`` field names whose content will be
    considered as links. Empty ``ImageField`` content is always ignored.

Management commands
-------------------

findlinks
~~~~~~~~~

This command goes through all registered fields and records the URLs it finds.
This command does not validate anything. Typically run just after installing
and configuring django-linkcheck.

checklinks
~~~~~~~~~~

For each recorded URL, check and report the validity of the URL. All internal
links are checked, but only external links that have not been checked during
the last ``LINKCHECK_EXTERNAL_RECHECK_INTERVAL`` minutes are checked. This
interval can be adapted per-invocation by using the ``--externalinterval``
(``-e``) command option (in minutes).

You can also limit the maximum number of links to be checked by passing a number
to the ``--limit`` (``--l``) command option.

Settings
--------

LINKCHECK_DISABLE_LISTENERS
~~~~~~~~~~~~~~~~~~~~~~~~~~~

A setting to totally disable linkcheck, typically when running tests. See also
the context managers below.

LINKCHECK_EXTERNAL_RECHECK_INTERVAL
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: 10080 (1 week in minutes)

Will not recheck any external link that has been checked more recently than this value.

LINKCHECK_EXTERNAL_REGEX_STRING
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: r'^https?://'

A string applied as a regex to a URL to determine whether it's internal or external.

LINKCHECK_MEDIA_PREFIX
~~~~~~~~~~~~~~~~~~~~~~

Default: '/media/'

Currently linkcheck tests whether links to internal static media are correct by wrangling the URL to be a local filesystem path.

It strips MEDIA_PREFIX off the interal link and concatenates the result onto settings.MEDIA_ROOT and tests that using os.path.exists

This 'works for me' but it is probably going to break for other people's setups. Patches welcome.

LINKCHECK_RESULTS_PER_PAGE
~~~~~~~~~~~~~~~~~~~~~~~~~~

Controls pagination.

Pagination is slightly peculiar at the moment due to the way links are grouped by object.


LINKCHECK_MAX_URL_LENGTH
~~~~~~~~~~~~~~~~~~~~~~~~

Default: 255

The length of the URL field. Defaults to 255 for compatibility with MySQL (see http://docs.djangoproject.com/en/dev/ref/databases/#notes-on-specific-fields )


LINKCHECK_CONNECTION_ATTEMPT_TIMEOUT
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default: 10

The timeout in seconds for each connection attempts. Sometimes it is useful to limit check time per connection in order to hold at bay the total check time.


SITE_DOMAIN and LINKCHECK_SITE_DOMAINS
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Linkcheck tests external and internal using differently. Internal links use the Django test client whereas external links are tested using urllib2.

Testing internal links this as if they were external can cause errors in some circumstances so Linkcheck needs to know which external urls are to be treated as internal.

Linkcheck looks for either of the settings above. It only uses SITE_DOMAIN if LINKCHECK_SITE_DOMAINS isn't present


SITE_DOMAIN = "mysite.com"

would tell linkchecker to treat the following as internal links:

mysite.com
www.mysite.com
test.mysite.com

If you instead set LINKCHECK_SITE_DOMAINS to be a list or tuple then you can explicitly list the domains that should be treated as internal.


django-filebrowser integration
------------------------------

If django-filebrowser is present on your path then linkcheck will listen to the post-upload, delete and rename signals and update itself according


Running tests
-------------

Tests can be run standalone by using the runtests.py script in linkcheck root:
    $ python runtests.py

If you want to run linkcheck tests in the context of your project, you should include 'linkcheck.tests.sampleapp' in your INSTALLED_APPS setting.

Linkcheck gives you two context managers to enable or disable listeners in your
own tests. For example:

    def test_something_without_listeners(self):
        with listeners.disable_listeners():
            # Create/update here without linkcheck intervening.

In the case you defined the LINKCHECK_DISABLE_LISTENERS setting, you can
temporarily enable it by:

    def test_something_with_listeners(self):
        with listeners.enable_listeners():
            # Create/update here and see linkcheck activated.
