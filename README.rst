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

#. Add something along the lines of ``examples/linklists.py`` to every app that
   either:

  #) has models that contain content (e.g. url/image fields, chunks of markup
     or anything that gets transformed into a IMG or HREF when displayed
  #) can be the target of a link - i.e. is addressed by a url - in this case
     make sure it has an instance method named 'get_absolute_url'

#. Syncdb

#. Add to your root url config::

    (r'^admin/linkcheck/', include('linkcheck.urls')) 

#. View ``/admin/linkcheck/`` from your browser

The file 'notifications.py' is completely optional. It works with
admin-notifications_ to display a notification about broken links as
shown in the screenshot above.
.. _admin-notifications: http://github.com/andybak/django-admin-notifications

We are aware that this documentation is on the brief side of things so any
suggestions for elaboration or clarification would be gratefully accepted.
