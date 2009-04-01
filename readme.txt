Requirements

path.py (included)
Jquery (my base admin template already links to it. If your's doesn't then add it to base_linkcheck.html

Basic usage

1. Install app to somewhere on your path

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

