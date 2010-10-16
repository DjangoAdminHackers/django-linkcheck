django-linkcheck
================

.. image:: http://ixxy.co.uk/media/documents/images/linkcheck.jpg

A fairly flexible app that will analyze and report on links in any model that
you register with it. Links can be bare (urls or image and file fields) or
embedded in HTML (linkcheck handles the parsing). It's fairly easy to override
methods of the Linkcheck object should you need to do anything more
complicated (like generate URLs from slug fields etc).
 
You should run it's management command via cron or similar to check external
links regularly to see if their status changes. All links are checked
automatically when objects are saved. This is handled by signals.

Basic usage
-----------

#. Install app to somewhere on your Python path

#. Add something along the lines of ``examples/linklists.py`` to every app that:

  #) either produces content that could contain links or images
  #) can be the target of a link (and if so should provide a get_absolute_url
     method so we can grab it's url)

#. Syncdb

#. Add to your root url config::

    (r'^admin/linkcheck/', include('linkcheck.urls')) 

#. View ``/admin/linkcheck/`` from your browser

#. Tell us about the bugs you've found or to complain how bad the documentation is!
