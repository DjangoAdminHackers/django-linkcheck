http://cms.andybak.webfactional.com/media/linkcheck.jpg

A fairly flexible app that will analyze and report on links in any model that you register with it. Links can be bare (urls or image and file fields) or embedded in HTML (linkcheck handles the parsing). It's fairly easy to override methods of the Linkcheck object should you need to do anything more complicated (like generate URLs from slug fields etc).
 
The current version does all the finding and checking of links as a bulk job you can run from cron but it's fairly easy to hook up signals to your model's save and delete to keep the data updated once an initial sweep has been done.

Another future enhancement would be the ability to automatically fix links when the related object is changed. 

This is working code but it currently comes with a few caveats:

  # It's been extracted from my homespun CMS and in some places that still shows.
  # No tests :(
  # Few comments or docstrings :(
  # The documentation was rather a rush job :(

Yes I'm a bad person. I'm putting this out there because doing so might inspire someone - hopefully me - to fix the above issues.

=Requirements=

  # Jquery (my base admin template already links to it. If your's doesn't then add it to base_linkcheck.html

=Basic usage=

1. Install app to somewhere on your Python path

2. Edit examples/linkcheck_config.py to include references to all your models that might contain links.

3. Add something along the lines of linklists.py to every app you referenced in linkcheck_config.py

4. Import linkcheck_config.py from your root urls.

5. Syncdb

6. Run findlinks management command or the utils.find()

7. Run checklinks management command or the utils.check()

8. Add (r'^admin/linkcheck/', include('linkcheck.urls')) to your root url config

9. View /admin/linkcheck/ from your browser

Coming soon:

Signals support to avoid the need to run findlinks or checklinks except for initial setup.



